"""Private merchant profile and internal work screens."""
import json

from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from ayo.identity import IdentityError, IdentityService
from ayo.merchant_work import ProfileService, TASK_STATUSES, TaskService
from ayo.models import Lead, ResearchReportRecord


def install_routes(mod, context, protected, guard):
    app = mod.app

    def permissions(sess, user, business, roles):
        member = IdentityService(sess).require_membership(user.id, business.id)
        return bool(user.email_verified_at and member.role in roles)

    def profile_response(request, sess, *, error=None, status=200, values=None):
        user, business = protected(request, sess)
        profile = ProfileService(sess).get(user.id, business.id)
        response = mod.render(request, 'business_profile.html', user=user, business=business, profile=profile,
            values=values, error=error, saved=request.query_params.get('saved') == '1',
            can_edit=permissions(sess, user, business, {'owner', 'admin'}))
        response.status_code = status
        return response

    @app.get('/business')
    def business_profile(request: Request, sess=Depends(mod.db)):
        return profile_response(request, sess)

    @app.post('/business')
    def save_business_profile(request: Request, business_name: str = Form(''), country: str = Form(''),
                             offer: str = Form(''), products: str = Form(''), audience: str = Form(''),
                             location: str = Form(''), goals: str = Form(''), version: int = Form(...),
                             csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        values = dict(business_name=business_name, country=country, offer=offer, products=products,
                      audience=audience, location=location, goals=goals)
        try:
            ProfileService(sess).save(user.id, business.id, name=business_name, country=country, offer=offer,
                products=products, audience=audience, location=location, goals=goals, version=version)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            return profile_response(request, sess, error=str(exc), status=exc.status_code,
                                    values=None if exc.code == 'stale_profile' else values)
        return RedirectResponse('/business?saved=1', 303)

    def work_response(request, sess, *, error=None, status=200, values=None):
        user, business = protected(request, sess)
        service = TaskService(sess)
        selected_status = request.query_params.get('status', '')
        tasks = service.list(user.id, business.id, selected_status)
        defaults = {'title': '', 'description': '', 'due_date': '', 'source_report_id': '', 'source_lead_id': ''}
        source_report, source_lead = None, None
        if values is not None:
            defaults.update(values)
        else:
            report_id = request.query_params.get('source_report_id', '')
            lead_id = request.query_params.get('source_lead_id', '')
            if report_id:
                service._source(ResearchReportRecord, report_id, business.id, 'report')
                source_report = sess.get(ResearchReportRecord, report_id)
                defaults['source_report_id'] = report_id
                opportunity = request.query_params.get('opportunity')
                if opportunity is not None:
                    try:
                        index = int(opportunity)
                        if index < 0:
                            raise ValueError
                        item = json.loads(source_report.report_json).get('opportunities', [])[index]
                        defaults['title'] = item['title'][:200]
                        defaults['description'] = (item.get('description') or item.get('text') or item.get('next_step') or '')[:5000]
                    except (ValueError, TypeError, KeyError, IndexError):
                        raise IdentityError('opportunity_not_found', 'This opportunity is not available in the saved report.', 404) from None
            if lead_id:
                service._source(Lead, lead_id, business.id, 'lead')
                source_lead = sess.get(Lead, lead_id)
                defaults.update(source_lead_id=lead_id, title='Review follow-up for ' + source_lead.name[:170])
        # Only the current workspace's source titles are available to templates.
        reports = {row.id: row.title for row in sess.scalars(select(ResearchReportRecord).where(
            ResearchReportRecord.business_id == business.id)).all()}
        leads = {row.id: row.name for row in sess.scalars(select(Lead).where(Lead.business_id == business.id)).all()}
        response = mod.render(request, 'work.html', user=user, business=business, tasks=tasks, values=defaults,
            statuses=TASK_STATUSES, selected_status=selected_status, error=error, source_report=source_report,
            source_lead=source_lead, source_reports=reports, source_leads=leads,
            can_edit=permissions(sess, user, business, {'owner', 'admin', 'editor'}),
            created=request.query_params.get('created') == '1', updated=request.query_params.get('updated') == '1')
        response.status_code = status
        return response

    @app.get('/work')
    def work(request: Request, sess=Depends(mod.db)):
        return work_response(request, sess)

    @app.post('/work/tasks')
    def create_task(request: Request, title: str = Form(''), description: str = Form(''), due_date: str = Form(''),
                    source_report_id: str = Form(''), source_lead_id: str = Form(''), csrf: str = Form(...),
                    sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        values = dict(title=title, description=description, due_date=due_date,
                      source_report_id=source_report_id, source_lead_id=source_lead_id)
        try:
            TaskService(sess).create(user.id, business.id, **values)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            # A forbidden source ID is not reflected into the page or exposed.
            if exc.code == 'source_not_found':
                values.update(source_report_id='', source_lead_id='')
            return work_response(request, sess, error=str(exc), status=exc.status_code, values=values)
        return RedirectResponse('/work?created=1', 303)

    @app.post('/work/tasks/{task_id}')
    def update_task(task_id: str, request: Request, version: int = Form(...), title: str = Form(''),
                    description: str = Form(''), status: str = Form(...), due_date: str = Form(''),
                    csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        try:
            TaskService(sess).update(user.id, business.id, task_id, version=version, title=title,
                                    description=description, status=status, due_date=due_date)
            sess.commit()
        except IdentityError as exc:
            sess.rollback()
            return work_response(request, sess, error=str(exc), status=exc.status_code)
        return RedirectResponse('/work?updated=1', 303)
