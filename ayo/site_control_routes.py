"""Explicit merchant-initiated HTTPS file checks; page reads never fetch a site."""
from datetime import datetime, timezone
import secrets
import time

from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse

from ayo.identity import IdentityError, IdentityService
from ayo.research import ResearchError
from ayo.site_control import ERRORS, SiteControlService, effective_status, schema_ready
from ayo.site_control_reader import PROOF_PATH, SiteFileReader


def install_routes(mod, protected, guard):
    app = mod.app
    app.state.site_file_reader_factory = SiteFileReader

    def page(request, sess, claim_id=None, *, error=None, status=200):
        user, business = protected(request, sess)
        ready = schema_ready(sess)
        member = IdentityService(sess).require_membership(user.id, business.id)
        can_manage = bool(user.email_verified_at and member.role in {'owner', 'admin'})
        service = SiteControlService(sess, mod.fernet)
        claims, selected, text = [], None, None
        if ready:
            claims = service.list(user.id, business.id)
            if claim_id:
                selected = service.get(user.id, business.id, claim_id)
                if can_manage:
                    text = service.challenge_text(user.id, business.id, claim_id)
        now = time.time()
        def stamp(value):
            return datetime.fromtimestamp(value, timezone.utc).strftime('%d %b %Y · %H:%M UTC') if value else '—'
        response = mod.render(request, 'business_sites.html', user=user, business=business,
            ready=ready, can_manage=can_manage, claims=claims, selected=selected, challenge_text=text,
            nonce=secrets.token_urlsafe(24), effective_status=lambda row: effective_status(row, now),
            stamp=stamp, proof_path=PROOF_PATH, errors=ERRORS, error=error)
        response.status_code = status if ready else 503
        return response

    @app.get('/business/sites')
    def sites(request: Request, sess=Depends(mod.db)):
        return page(request, sess)

    @app.get('/business/sites/{claim_id}')
    def site_detail(request: Request, claim_id: str, sess=Depends(mod.db)):
        return page(request, sess, claim_id)

    @app.post('/business/sites')
    def create_site(request: Request, host: str = Form(''), nonce: str = Form(''),
                    csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        try:
            row = SiteControlService(sess, mod.fernet).create(user.id, business.id, host, nonce)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            return page(request, sess, error=str(exc), status=exc.status_code)
        return RedirectResponse('/business/sites/' + row.id, 303)

    @app.post('/business/sites/{claim_id}/check')
    async def check_site(request: Request, claim_id: str, csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        user_id, business_id = user.id, business.id
        guard(request, csrf, sess)
        try:
            lease = SiteControlService(sess, mod.fernet).begin_check(user_id, business_id, claim_id)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            return page(request, sess, claim_id, error=str(exc), status=exc.status_code)
        # No database lock is held during network I/O. Only this explicit POST
        # checks the two fixed URLs; GET/reopen never launches a retry.
        proof, error = None, None
        try:
            proof = await app.state.site_file_reader_factory().read(lease.host)
        except ResearchError as exc:
            error = exc.code
        except Exception:
            # Provider exception text may contain private headers or bodies.
            error = 'verification_fetch_failed'
        sess.expire_all()
        try:
            guard(request, csrf, sess)
            SiteControlService(sess, mod.fernet).finish_check(user_id, business_id, lease, proof, error)
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        return RedirectResponse('/business/sites/' + claim_id, 303)

    @app.post('/business/sites/{claim_id}/revoke')
    def revoke_site(request: Request, claim_id: str, csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        try:
            row = SiteControlService(sess, mod.fernet).revoke(user.id, business.id, claim_id)
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        return RedirectResponse('/business/sites/' + row.id, 303)
