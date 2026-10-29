"""Authenticated, consented merchant-input analysis; providers never fetch a URL."""
import asyncio
import secrets

from fastapi import Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from ayo.assistant import AssistantService
from ayo.identity import IdentityError
from ayo.merchant_analysis import FIELDS, MerchantAnalysisService, analyze_merchant_report, upload_text
from ayo.provider_usage import budget_context
from ayo.research import ResearchReport


def install_routes(mod, protected, guard):
    @mod.app.get('/business-analysis')
    def compose(request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        return mod.render(request, 'merchant_analysis.html', user=user, business=business,
                          active_page='research', fields=FIELDS, request_id=secrets.token_urlsafe(24))

    @mod.app.post('/business-analysis')
    async def submit(request: Request, name: str = Form(''), country: str = Form(''),
                     description: str = Form(''), products: str = Form(''), pricing: str = Form(''),
                     website: str = Form(''), goals: str = Form(''), authorized: bool = Form(False),
                     nonpersonal: bool = Form(False), data_consent: bool = Form(False), csrf: str = Form(...),
                     request_id: str = Form(...),
                     document: UploadFile | None = File(None), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        service = MerchantAnalysisService(sess)
        text = ''
        if document and document.filename:
            try:
                text = upload_text(document.filename, await document.read(4001))
            finally:
                await document.close()
        try:
            row, dispatch = service.stage(user.id, business.id, name=name, country=country,
                values=dict(description=description, products=products, pricing=pricing, website=website, goals=goals),
                document=text, authorized=authorized, nonpersonal=nonpersonal, data_consent=data_consent, request_id=request_id)
            report_id = row.id
            sess.commit()
            if not dispatch:
                return RedirectResponse('/business-analysis/' + report_id, 303)  # Actual stored input is the only permissible model context.
            stored = service.inference_report(user.id, business.id, report_id)
            stored = ResearchReport.model_validate(stored.model_dump())
            sess.commit()
        except IdentityError:
            sess.rollback()
            raise
        try:
            with budget_context(mod.DbSession, scope_id='business:' + business.id,
                                request_id='merchant-report:' + report_id, dispatch_prefix='merchant-report:' + report_id):
                async with asyncio.timeout(45):
                    provider = getattr(mod.app.state, 'merchant_analysis_provider', None)
                    report = await analyze_merchant_report(stored, provider)
        except Exception:
            # Unknown/timeout outcomes never invite an automatic repeat request.
            report = ResearchReport.model_validate({**stored.model_dump(), 'analysis_status': 'unavailable',
                'analysis': None, 'analysis_error_code': 'analysis_interrupted'})
        service.finish(user.id, business.id, report_id, report)
        sess.commit()
        return RedirectResponse('/business-analysis/' + report_id, 303)

    @mod.app.get('/business-analysis/{report_id}')
    def open_analysis(report_id: str, request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        row, report = MerchantAnalysisService(sess).load(user.id, business.id, report_id)
        return mod.render(request, 'merchant_report.html', user=user, business=business,
            active_page='research', report=report, report_record=row)

    @mod.app.post('/business-analysis/{report_id}/conversation')
    def discuss(report_id: str, request: Request, csrf: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        _, report = MerchantAnalysisService(sess).load(user.id, business.id, report_id)
        row = AssistantService(sess).create(user.id, business.id, secrets.token_urlsafe(24),
            title=('Discuss ' + report.business_name)[:160], source_report_id=report_id)
        sess.commit()
        return RedirectResponse('/ayo/conversations/' + row.id, 303)
