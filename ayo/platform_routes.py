"""Search-first application routes over explicit identity and evidence services."""
import json
import os
import secrets
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ayo.identity import IdentityError, IdentityService
from ayo.intelligence import IntelligenceContext, IntelligenceError, IntelligenceOrchestrator, SourceEvidence
from ayo.leads import LeadError, PipelineEvidence, discover_leads, transition_lead
from ayo.mailer import queue_identity_mail
from ayo.jobs import enqueue, get_job
from ayo.account_deletion import remove_account
from ayo.models import AuditEvent, Business, IntelligenceRun, Lead, LeadEvent, Membership
from ayo.public_research import prepare_public_research
from ayo.report_storage import ReportStore
from ayo.research import ResearchError, ResearchReport, ResearchService
from ayo.website_research import SiteInputError


def install_routes(mod):
    app = mod.app
    app.state.research_factory = ResearchService.from_env
    app.state.intelligence_factory = IntelligenceOrchestrator

    @app.exception_handler(IdentityError)
    async def identity_error(request, exc):
        return JSONResponse({'detail': {'code': exc.code, 'message': str(exc)}}, status_code=exc.status_code,
                            headers={'Retry-After': str(exc.retry_after)} if exc.retry_after else None)

    def client_key(request):
        # Forwarding headers are untrusted. Production proxy trust is configured
        # by the ASGI host, not selected from browser-provided X-Forwarded-For.
        return request.client.host if request.client else 'unknown'

    def context(request, sess):
        user = mod.must_user(request, sess)
        selected = request.session.get('business_id')
        membership = sess.scalar(select(Membership).where(
            Membership.user_id == user.id, Membership.business_id == selected)) if selected else None
        if membership is None:
            membership = sess.scalar(select(Membership).where(Membership.user_id == user.id)
                                     .order_by(Membership.business_id))
        if membership is None:
            return user, None
        return user, sess.get(Business, membership.business_id)

    def protected(request, sess):
        user, business = context(request, sess)
        if business is None:
            raise HTTPException(409, 'Set up a business workspace at /business/setup first.')
        return user, business

    def lead_views(rows):
        return [{**json.loads(row.evidence_json), 'id': row.id, 'status': row.status,
                 'fit_reason': row.fit_reason} for row in rows]

    def guard(request, csrf, sess):
        mod.form_guard(request, csrf)
        if request.session.get('sid') and not IdentityService(sess).validate_csrf(request.session['sid'], csrf):
            raise HTTPException(403, 'This session has expired. Sign in again.')

    def start_session(request, grant):
        pending = {key: request.session[key] for key in ('anonymous_id', 'pending_claim', 'pending_report') if key in request.session}
        request.session.clear()
        request.session.update(pending)
        request.session['sid'], request.session['csrf'] = grant.token, grant.csrf

    def attempt_claim(request, sess, user, business):
        raw = request.session.get('pending_claim')
        if raw and business and user.email_verified_at:
            try:
                ReportStore(sess).claim(raw, request.session.get('anonymous_id'), user.id, business.id)
                sess.commit()
                request.session.pop('pending_claim', None)
                request.session.pop('pending_report', None)
            except IdentityError:
                sess.rollback()

    def dashboard_response(request, sess, error=None, status=200):
        user, business = context(request, sess)
        if business is None:
            return mod.render(request, 'business_setup.html', user=user, error=error)
        reports = ReportStore(sess).for_business(user.id, business.id)
        leads = sess.scalars(select(Lead).where(Lead.business_id == business.id).order_by(Lead.created_at.desc())).all()
        opportunities = []
        for record in reports:
            data = json.loads(record.report_json)
            opportunities.extend({**item, 'report_id': record.id} for item in data.get('opportunities', []))
        activities = sess.scalars(select(AuditEvent).where(AuditEvent.business_id == business.id)
                                 .order_by(AuditEvent.created_at.desc()).limit(20)).all()
        labels = {'report.claimed': 'Research saved to this workspace',
                  'account.registered': 'Your Ayo account was created', 'business.created': 'Business workspace created',
                  'lead.discovered': 'A sourced prospect was discovered', 'lead.qualified': 'A prospect was qualified after review',
                  'intelligence.analyzed': 'Ayo analysis recorded'}
        activities = [{'label': labels.get(event.action, event.action.replace('.', ' · ').replace('_', ' ')),
                       'display_time': datetime.fromtimestamp(event.created_at, ZoneInfo(business.timezone)).strftime('%d %b %Y · %H:%M %Z')}
                      for event in activities]
        latest = sess.scalar(select(IntelligenceRun).where(IntelligenceRun.business_id == business.id)
                             .order_by(IntelligenceRun.created_at.desc()))
        notice = ('Your report is ready to save. Verify your email, then reopen it to save it securely.'
                  if request.session.get('pending_claim') and not user.email_verified_at else None)
        response = mod.render(request, 'app_dashboard.html', user=user, business=business,
            reports=reports, leads=leads, opportunities=opportunities, activities=activities,
            answer=json.loads(latest.result_json) if latest else None,
            founding_slot=IdentityService(sess).entitlement(user.id).founding_slot,
            error=error, notice=notice)
        response.status_code = status
        return response

    @app.get('/signup')
    def signup_page(request: Request):
        return mod.render(request, 'auth.html', mode='signup')

    @app.post('/signup')
    def signup(request: Request, email: str = Form(...), password: str = Form(...),
               business_name: str = Form(''), country: str = Form(''), csrf: str = Form(...), sess=Depends(mod.db)):
        guard(request, csrf, sess)
        try:
            service = IdentityService(sess)
            registration = service.register(email, password, business_name, country, client_key=client_key(request))
            queue_identity_mail(sess, mod.fernet, registration.user, 'verify_email', registration.verification_token, mod.ORIGIN)
            grant = service.create_session(registration.user.id)
            sess.commit()
        except IdentityError as exc:
            sess.commit()  # Persist anti-abuse counters on handled failures.
            response = mod.render(request, 'auth.html', mode='signup', error=str(exc))
            response.status_code = exc.status_code
            return response
        except IntegrityError:
            sess.rollback()
            response = mod.render(request, 'auth.html', mode='signup', error='This account could not be created. Sign in or recover access.')
            response.status_code = 409
            return response
        start_session(request, grant)
        request.session['business_id'] = registration.business.id
        return RedirectResponse('/dashboard', 303)

    @app.get('/login')
    def login_page(request: Request):
        return mod.render(request, 'auth.html', mode='login')

    @app.post('/login')
    def login(request: Request, email: str = Form(...), password: str = Form(...),
              csrf: str = Form(...), sess=Depends(mod.db)):
        guard(request, csrf, sess)
        try:
            grant = IdentityService(sess).login(email, password, client_key=client_key(request))
            sess.commit()
        except IdentityError as exc:
            sess.commit()
            response = mod.render(request, 'auth.html', mode='login', error='Invalid email or password' if exc.code == 'invalid_credentials' else str(exc))
            response.status_code = 429 if exc.status_code == 429 else 200
            return response
        start_session(request, grant)
        user, business = context(request, sess)
        attempt_claim(request, sess, user, business)
        return RedirectResponse('/dashboard', 303)

    @app.post('/logout')
    def logout(request: Request, csrf: str = Form(...), sess=Depends(mod.db)):
        guard(request, csrf, sess)
        IdentityService(sess).revoke_session(request.session.get('sid'))
        sess.commit()
        request.session.clear()
        return RedirectResponse('/', 303)

    @app.get('/dashboard')
    def dashboard(request: Request, sess=Depends(mod.db)):
        if not mod.session_user(request, sess):
            return RedirectResponse('/login', 303)
        return dashboard_response(request, sess)

    @app.get('/business/setup')
    def business_setup(request: Request, sess=Depends(mod.db)):
        return mod.render(request, 'business_setup.html', user=mod.must_user(request, sess))

    @app.post('/business/setup')
    def create_business(request: Request, business_name: str = Form(...), country: str = Form(...),
                        csrf: str = Form(...), sess=Depends(mod.db)):
        user = mod.must_user(request, sess)
        guard(request, csrf, sess)
        try:
            business = IdentityService(sess).create_business(user.id, business_name, country)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            return mod.render(request, 'business_setup.html', user=user, error=str(exc))
        request.session['business_id'] = business.id
        return RedirectResponse('/dashboard', 303)

    @app.post('/business/switch')
    def switch_business(request: Request, business_id: str = Form(...), csrf: str = Form(...), sess=Depends(mod.db)):
        user = mod.must_user(request, sess)
        guard(request, csrf, sess)
        IdentityService(sess).require_membership(user.id, business_id)
        request.session['business_id'] = business_id
        return RedirectResponse('/dashboard', 303)

    async def research_url(request, sess, url, country, business_name=''):
        app.state.research_factory()  # Fail before queueing if configuration is absent.
        anonymous_id = request.session.setdefault('anonymous_id', secrets.token_urlsafe(32))
        IdentityService(sess)._attempt('research-submit', client_key(request), limit=10, window=3600)
        job = enqueue(sess, mod.fernet, url=url, country=country, business_name=business_name,
                      anonymous_id=anonymous_id)
        sess.commit()
        return RedirectResponse('/research/jobs/' + job.id, 303)

    @app.get('/research/jobs/{job_id}')
    def job_status(job_id: str, request: Request, sess=Depends(mod.db)):
        try:
            job = get_job(sess, job_id, request.session.get('anonymous_id'))
        except IdentityError as exc:
            raise HTTPException(exc.status_code, str(exc))
        if job.status == 'succeeded' and job.report_id and job.claim_cipher:
            request.session['pending_claim'] = mod.fernet.decrypt(job.claim_cipher.encode()).decode()
            request.session['pending_report'] = job.report_id
            return RedirectResponse('/research/' + job.report_id, 303)
        return mod.render(request, 'research_job.html', job=job, user=mod.session_user(request, sess))

    @app.post('/research')
    async def research(request: Request, query: str = Form(''), country: str = Form(''), city: str = Form(''),
                       no_website: bool = Form(False), owner_facts: str = Form(''),
                       csrf: str = Form(...), sess=Depends(mod.db)):
        guard(request, csrf, sess)
        try:
            preview = prepare_public_research(query, country, city, no_website, owner_facts)
            if preview.no_website:
                return mod.render(request, 'research.html', preview=preview, user=mod.session_user(request, sess))
            if preview.input_kind == 'url':
                return await research_url(request, sess, preview.query, country)
            IdentityService(sess)._attempt('business-search', client_key(request), limit=20, window=3600)
            sess.commit()
            candidates = await app.state.research_factory().search(preview.query, country=country, city=city)
            return mod.render(request, 'search_results.html', candidates=candidates,
                              query=preview.query, country=country, city=city, user=mod.session_user(request, sess))
        except SiteInputError as exc:
            response = mod.render(request, 'landing.html', values={}, error=str(exc))
            response.status_code = 400
            return response
        except ResearchError as exc:
            sess.commit()  # Preserve bounded request counters on handled failures.
            response = mod.render(request, 'research.html', preview=preview, error=str(exc), user=mod.session_user(request, sess))
            response.status_code = exc.status_code
            return response

    @app.post('/research/select')
    async def select_research(request: Request, url: str = Form(...), country: str = Form(''),
                             business_name: str = Form(''), csrf: str = Form(...), sess=Depends(mod.db)):
        guard(request, csrf, sess)
        try:
            return await research_url(request, sess, url, country, business_name[:240])
        except ResearchError as exc:
            raise HTTPException(exc.status_code, {'code': exc.code, 'message': str(exc)})

    @app.get('/research/{report_id}')
    def open_report(report_id: str, request: Request, sess=Depends(mod.db)):
        user = mod.session_user(request, sess)
        try:
            row = ReportStore(sess).accessible(report_id, user.id if user else None, request.session.get('anonymous_id'))
        except IdentityError as exc:
            raise HTTPException(exc.status_code, str(exc))
        report = ResearchReport.model_validate_json(row.report_json)
        return mod.render(request, 'report.html', report=report, report_record=row, saved=bool(row.business_id),
                          user=user, claim_token=request.session.get('pending_claim') if request.session.get('pending_report') == row.id else None)

    @app.post('/reports/claim')
    def claim_report(request: Request, claim_token: str = Form(...), csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        try:
            report = ReportStore(sess).claim(claim_token, request.session.get('anonymous_id'), user.id, business.id)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            raise HTTPException(exc.status_code, {'code': exc.code, 'message': str(exc)})
        request.session.pop('pending_claim', None)
        request.session.pop('pending_report', None)
        return RedirectResponse('/research/' + report.id, 303)

    @app.get('/leads')
    def leads_page(request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        rows = sess.scalars(select(Lead).where(Lead.business_id == business.id).order_by(Lead.created_at.desc())).all()
        return mod.render(request, 'leads.html', user=user, business=business, leads=lead_views(rows))

    @app.post('/leads/discover')
    async def find_leads(request: Request, query: str = Form(...), country: str = Form(...), city: str = Form(''),
                         csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        identity = IdentityService(sess)
        identity.require_membership(user.id, business.id, roles={'owner', 'admin', 'editor'})
        identity._attempt('lead-discovery', business.id, limit=20, window=3600)
        sess.commit()
        existing = sess.scalars(select(Lead.url).where(Lead.business_id == business.id)).all()
        try:
            candidates = await discover_leads(app.state.research_factory(), query, country, city, existing_urls=tuple(existing))
            for candidate in candidates:
                row = Lead(business_id=business.id, name=candidate.name, url=candidate.url, country=candidate.country,
                           status='discovered', fit_reason=' '.join(candidate.fit_reasons), evidence_json=candidate.model_dump_json())
                sess.add(row)
                sess.flush()
                sess.add(LeadEvent(lead_id=row.id, business_id=business.id, actor_user_id=user.id,
                                   to_status='discovered', evidence_json=candidate.model_dump_json()))
                identity.audit('lead.discovered', user_id=user.id, business_id=business.id, resource_type='lead', resource_id=row.id)
            sess.commit()
        except (ResearchError, LeadError) as exc:
            sess.rollback()
            rows = sess.scalars(select(Lead).where(Lead.business_id == business.id)).all()
            response = mod.render(request, 'leads.html', user=user, business=business, leads=lead_views(rows), error=str(exc))
            response.status_code = getattr(exc, 'status_code', 400)
            return response
        except IntegrityError:
            sess.rollback()
            return RedirectResponse('/leads', 303)
        return RedirectResponse('/leads', 303)

    @app.post('/leads/{lead_id}/qualify')
    def qualify_lead(lead_id: str, request: Request, note: str = Form(...), csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        identity = IdentityService(sess)
        identity.require_membership(user.id, business.id, roles={'owner', 'admin', 'editor'})
        row = sess.scalar(select(Lead).where(Lead.id == lead_id, Lead.business_id == business.id).with_for_update())
        if row is None:
            raise HTTPException(404, 'Lead not found.')
        if not 1 <= len(note.strip()) <= 1000:
            raise HTTPException(400, 'Describe the source-backed fit in at most 1000 characters.')
        source = json.loads(row.evidence_json)
        evidence = PipelineEvidence(business_id=business.id, kind='qualification',
                                    reference=source['source_id'], note=note.strip())
        try:
            event = transition_lead(business_id=business.id, actor_business_id=business.id,
                current_status=row.status, next_status='qualified', evidence=evidence)
        except LeadError as exc:
            raise HTTPException(409, {'code': exc.code, 'message': str(exc)})
        row.status, row.updated_at = event.status, time.time()
        sess.add(LeadEvent(lead_id=row.id, business_id=business.id, actor_user_id=user.id,
                           from_status=event.previous_status, to_status=event.status, evidence_json=evidence.model_dump_json()))
        identity.audit('lead.qualified', user_id=user.id, business_id=business.id, resource_type='lead', resource_id=row.id)
        sess.commit()
        return RedirectResponse('/leads', 303)

    @app.post('/ask')
    async def ask(request: Request, question: str = Form(...), csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        IdentityService(sess)._attempt('intelligence-analysis', business.id, limit=20, window=3600)
        sess.commit()
        records = ReportStore(sess).for_business(user.id, business.id)
        sources = {}
        for row in records:
            for source in ResearchReport.model_validate_json(row.report_json).source_documents:
                excerpt = (source.excerpt + '\n' + source.content[-3000:]
                           if source.product_observations or source.channel_observations else source.excerpt)
                sources[source.id] = SourceEvidence(id=source.id, business_id=business.id, url=source.url,
                                                    excerpt=excerpt, observed_at=source.retrieved_at)
        try:
            evidence = tuple(sources.values())[:20]
            ctx = IntelligenceContext(business_id=business.id, actor_business_id=business.id,
                                      country=business.country, question=question, evidence=evidence)
            result = await app.state.intelligence_factory().analyze(ctx)
            sess.add(IntelligenceRun(business_id=business.id, user_id=user.id, provider=result.provider,
                model=result.model, status=result.status, result_json=result.model_dump_json(),
                source_report_id=records[0].id if records else None))
            IdentityService(sess).audit('intelligence.analyzed', user_id=user.id, business_id=business.id,
                                        resource_type='intelligence', details={'provider': result.provider, 'status': result.status})
            sess.commit()
        except (IntelligenceError, ValidationError) as exc:
            sess.rollback()
            return dashboard_response(request, sess, error=str(exc), status=503 if isinstance(exc, IntelligenceError) else 400)
        return RedirectResponse('/dashboard#ayo', 303)

    @app.get('/settings')
    def settings(request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        providers = {name: 'configured_unverified' if os.getenv(key) else 'not_configured'
                     for name, key in [('research', 'FIRECRAWL_API_KEY'), ('Gemini', 'GEMINI_API_KEY'),
                                       ('Claude', 'ANTHROPIC_API_KEY'), ('email', 'RESEND_API_KEY'), ('Shopify', 'SHOPIFY_CLIENT_ID')]}
        providers['payments'] = 'adapter_contract_only_no_live_connection'
        businesses = sess.scalars(select(Business).join(Membership, Membership.business_id == Business.id)
                                  .where(Membership.user_id == user.id).order_by(Business.created_at)).all()
        return mod.render(request, 'settings.html', user=user, business=business, provider_status=providers,
                          founding_slot=IdentityService(sess).entitlement(user.id).founding_slot, businesses=businesses)

    @app.get('/security')
    def security(request: Request, sess=Depends(mod.db)):
        user, business = context(request, sess)
        return mod.render(request, 'account_security.html', user=user, business=business)

    @app.post('/security/verify')
    def resend_verification(request: Request, csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = context(request, sess)
        guard(request, csrf, sess)
        service = IdentityService(sess)
        try:
            service._attempt('verification-user', str(user.id), limit=3, window=3600)
            if not user.email_verified_at:
                raw = service.issue_token(user.id, 'verify_email')
                queue_identity_mail(sess, mod.fernet, user, 'verify_email', raw, mod.ORIGIN)
            sess.commit()
        except IdentityError as exc:
            sess.commit()
            raise HTTPException(exc.status_code, str(exc))
        return mod.render(request, 'account_security.html', user=user, business=business,
            message='Verification has been queued. Email delivery requires a configured and authorized mail worker.')

    @app.post('/security/delete')
    def delete_account(request: Request, password: str = Form(...), confirmation: str = Form(...),
                       csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = context(request, sess)
        guard(request, csrf, sess)
        IdentityService(sess)._attempt('account-removal', str(user.id), limit=5, window=3600)
        sess.commit()
        try:
            remove_account(sess, user.id, password, confirmation)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            response = mod.render(request, 'account_security.html', user=user, business=business, error=str(exc))
            response.status_code = exc.status_code
            return response
        request.session.clear()
        return RedirectResponse('/login', 303)

    @app.get('/verify-email')
    def verify_email(request: Request, token: str, sess=Depends(mod.db)):
        try:
            user = IdentityService(sess).consume_verification(token)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            raise HTTPException(exc.status_code, str(exc))
        active = mod.session_user(request, sess)
        if active and active.id == user.id:
            _, business = context(request, sess)
            attempt_claim(request, sess, user, business)
            return RedirectResponse('/dashboard', 303)
        return RedirectResponse('/login', 303)

    @app.get('/forgot-password')
    def forgot_page(request: Request):
        return mod.render(request, 'recovery.html', mode='forgot')

    @app.post('/forgot-password')
    def forgot(request: Request, email: str = Form(...), csrf: str = Form(...), sess=Depends(mod.db)):
        guard(request, csrf, sess)
        try:
            result = IdentityService(sess).request_password_reset(email, client_key(request))
            if result:
                user, raw = result
                queue_identity_mail(sess, mod.fernet, user, 'reset_password', raw, mod.ORIGIN)
            sess.commit()
        except IdentityError as exc:
            sess.commit()
            if exc.status_code == 429:
                raise HTTPException(429, str(exc))
        return mod.render(request, 'recovery.html', mode='forgot',
            message='If the account exists, a recovery message has been queued. Delivery requires a configured and authorized email service.')

    @app.get('/reset-password')
    def reset_page(request: Request, token: str):
        return mod.render(request, 'recovery.html', mode='reset', token=token)

    @app.post('/reset-password')
    def reset(request: Request, token: str = Form(...), password: str = Form(...), csrf: str = Form(...), sess=Depends(mod.db)):
        guard(request, csrf, sess)
        try:
            IdentityService(sess).reset_password(token, password)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            response = mod.render(request, 'recovery.html', mode='reset', token=token, error=str(exc))
            response.status_code = exc.status_code
            return response
        request.session.clear()
        return RedirectResponse('/login', 303)
