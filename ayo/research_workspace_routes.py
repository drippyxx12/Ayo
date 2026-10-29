"""Private saved-evidence views, reviewed refresh and correction requests."""
import secrets
from fastapi import Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from ayo.identity import IdentityError
from ayo.research_workspace import LibraryFilters, ResearchWorkspace
from ayo.research_refresh import RefreshService


def _parameters(request, allowed):
    pairs = list(request.query_params.multi_items())
    names = [name for name, _ in pairs]
    if len(names) != len(set(names)) or set(names) - set(allowed):
        raise IdentityError('invalid_research_query', 'Use each supported research filter once.', 400)
    return dict(pairs)


def install_routes(mod, context, protected, guard):
    """Install before /research/{report_id}, which otherwise captures literals."""
    app = mod.app

    @app.get('/research/library')
    def research_library(request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        filters = LibraryFilters.parse(_parameters(request, LibraryFilters.__dataclass_fields__))
        library = ResearchWorkspace(sess).library(user.id, business.id, filters)
        return mod.render(request, 'research_library.html', user=user, business=business,
                          active_page='research', library=library)

    @app.get('/research/compare')
    def research_compare(request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        values = _parameters(request, {'left', 'right', 'label'})
        comparison = ResearchWorkspace(sess).compare(user.id, business.id,
            values.get('left', ''), values.get('right', ''), values.get('label', ''))
        return mod.render(request, 'research_compare.html', user=user, business=business,
                          active_page='research', comparison=comparison)

    @app.get('/research/library/{report_id}')
    def research_inspect(report_id: str, request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        _parameters(request, set())
        inspection = ResearchWorkspace(sess).inspect(user.id, business.id, report_id)
        if inspection['merchant_provided']:
            from ayo.merchant_analysis import MerchantAnalysisService
            row, report = MerchantAnalysisService(sess).load(user.id, business.id, report_id)
            return mod.render(request, 'merchant_report.html', user=user, business=business,
                active_page='research', report=report, report_record=row)
        return mod.render(request, 'research_inspect.html', user=user, business=business,
                          active_page='research', inspection=inspection)

    @app.get('/research/library/{report_id}/export')
    def research_export(report_id: str, request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        _parameters(request, set())
        payload = ResearchWorkspace(sess).export(user.id, business.id, report_id)
        return JSONResponse(payload, headers={
            'Content-Disposition': 'attachment; filename="ayo-research-' + report_id + '.json"',
            'Cache-Control': 'private, no-store', 'Pragma': 'no-cache',
            'X-Content-Type-Options': 'nosniff',
        })

    @app.get('/research/library/{report_id}/refresh')
    def review_refresh(report_id: str, request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        _parameters(request, set())
        row, report = RefreshService(sess, mod.fernet).original(user.id, business.id, report_id, write=True)
        return mod.render(request, 'research_refresh.html', user=user, business=business, active_page='research',
            original=row, report=report, request_id=secrets.token_urlsafe(24))

    @app.post('/research/library/{report_id}/refresh')
    def start_refresh(report_id: str, request: Request, request_id: str = Form(''),
                      reviewed: bool = Form(False), csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        try:
            job = RefreshService(sess, mod.fernet).request(user.id, business.id, report_id,
                                                        request_id=request_id, reviewed=reviewed)
            sess.commit()
        except IdentityError:
            sess.rollback()
            raise
        return RedirectResponse('/research/library/' + report_id + '/refresh/' + job.id, 303)

    @app.get('/research/library/{report_id}/refresh/{job_id}')
    def refresh_status(report_id: str, job_id: str, request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        _parameters(request, set())
        job = RefreshService(sess, mod.fernet).read(user.id, business.id, report_id, job_id)
        if job.status == 'succeeded' and job.report_id:
            return RedirectResponse('/research/library/' + job.report_id, 303)
        return mod.render(request, 'research_refresh.html', user=user, business=business,
                          active_page='research', job=job, original_id=report_id)

    @app.post('/research/library/{report_id}/corrections')
    def request_correction(report_id: str, request: Request, source_id: str = Form(''),
                           reason: str = Form(''), details: str = Form(''), csrf: str = Form(...),
                           sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        try:
            ResearchWorkspace(sess).request_correction(user.id, business.id, report_id,
                source_id=source_id, reason=reason, details=details)
            sess.commit()
        except IdentityError:
            sess.rollback()
            raise
        return RedirectResponse('/research/library/' + report_id + '#corrections', 303)
