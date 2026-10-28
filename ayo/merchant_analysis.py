"""Authorized merchant-input reports; no crawl, document execution or public claim."""
from datetime import datetime, timezone
import hashlib
import re
import secrets
import time

from sqlalchemy import select, update

from ayo.identity import IdentityError, IdentityService, token_hash
from ayo.intelligence import IntelligenceError, IntelligenceOrchestrator
from ayo.merchant_evidence import MerchantInputDocument, restricted_input
from ayo.merchant_work import text_value
from ayo.models import ResearchReportRecord
from ayo.research import ResearchReport

FIELDS = ('description', 'products', 'pricing', 'website', 'goals')
# Attestation is required in addition to this conservative detector. No detector
# can certify arbitrary text is nonpersonal or that the merchant owns its rights.



def clean_input(value, field, maximum=2000, minimum=0):
    value = text_value(value, field, maximum, minimum=minimum)
    if restricted_input(value):
        raise IdentityError('restricted_merchant_input', 'Remove contact details, credentials and sensitive information before submitting.', 400)
    return value


def upload_text(filename, data):
    if not filename or not filename.lower().endswith(('.txt', '.md')) or not 1 <= len(data) <= 4000:
        raise IdentityError('invalid_document', 'Upload a UTF-8 .txt or .md document of at most 4,000 bytes.', 400)
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError:
        raise IdentityError('invalid_document', 'The document must be UTF-8 text.', 400) from None
    # Original paths/filenames may identify a person; retain a neutral origin label.
    return clean_input(text, 'uploaded_document', 4000, 1)


class MerchantAnalysisService:
    def __init__(self, session, clock=time.time):
        self.session, self.clock = session, clock

    def stage(self, user_id, business_id, *, name, country, values, document='', authorized=False,
              nonpersonal=False, data_consent=False, request_id=None):
        identity = IdentityService(self.session, self.clock)
        identity.require_verified_user(user_id)
        identity.require_membership(user_id, business_id, roles={'owner', 'admin', 'editor'})
        if not all(flag is True for flag in (authorized, nonpersonal, data_consent)):
            raise IdentityError('merchant_input_consent_required', 'Confirm your authorization, nonpersonal inputs and provider processing consent.', 400)
        if country not in {'NG', 'GH'} or set(values) != set(FIELDS):
            raise IdentityError('invalid_merchant_input', 'Choose Nigeria or Ghana and use the supported input fields.', 400)
        name = clean_input(name, 'business_name', 160, 2)
        provided = {field: clean_input(values[field], field, 2000, 10 if field == 'description' else 0) for field in FIELDS}
        provided = {'description': 'Business name: ' + name + '\n' + provided['description'],
                    **{k: v for k, v in provided.items() if k != 'description'}, 'market': country}
        if document:
            provided['uploaded_document'] = clean_input(document, 'uploaded_document', 4000, 1)
        if sum(len(value.encode()) for value in provided.values()) > 12000:
            raise IdentityError('merchant_input_too_large', 'Combined inputs must be at most 12,000 UTF-8 bytes.', 400)
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', request_id):
            raise IdentityError('invalid_request_id', 'Reload the form before submitting.', 400)
        record_id = token_hash('merchant-report:' + str(user_id) + ':' + business_id + ':' + request_id)
        existing = self.session.get(ResearchReportRecord, record_id)
        if existing:
            old = ResearchReport.model_validate_json(existing.report_json)
            old_inputs = {source.input_field: source.content for source in old.source_documents}
            if old.business_name != name or old.country != country or old_inputs != {k: v for k, v in provided.items() if v}:
                raise IdentityError('request_conflict', 'This form was already submitted with different inputs.', 409)
            return existing, False
        identity._attempt('merchant-analysis', business_id, limit=5, window=3600)
        now, reference = datetime.fromtimestamp(self.clock(), timezone.utc), secrets.token_urlsafe(24)
        sources = tuple(MerchantInputDocument(id='input-' + reference + '-' + field,
            url='workspace:input:' + secrets.token_urlsafe(24), retrieved_at=now,
            source_hash=hashlib.sha256(value.encode()).hexdigest(), title=field.replace('_', ' ').title(),
            excerpt=value[:600], content=value, provider_receipt_id=reference,
            origin='merchant_upload' if field == 'uploaded_document' else 'merchant_form', input_field=field)
            for field, value in provided.items() if value)
        report = ResearchReport(origin='merchant_provided', business_name=name,
            target_url='workspace:merchant:' + reference, country=country, status='PARTIAL',
            source_documents=sources, claims=(), opportunities=(), created_at=now, analysis_status='pending',
            limitations=('All supplied information is OWNER_PROVIDED_UNVERIFIED; no independent acquisition occurred.',
                         'Prices are merchant-stated, not independently checked offers or sales.',
                         'No website was fetched, ownership verified, contacts discovered or commercial outcome measured.',
                         'Input authorization and nonpersonal/provider-processing consent were attested by the submitting merchant.'))
        row = ResearchReportRecord(id=record_id, business_id=business_id, owner_user_id=user_id, title=name,
            target_url=report.target_url, country=country, status='PENDING_ANALYSIS', report_json=report.model_dump_json(),
            expires_at=None, anonymous_session_hash=None, created_at=self.clock())
        self.session.add(row)
        self.session.flush()
        identity.audit('merchant_analysis.inputs_saved', user_id=user_id, business_id=business_id,
            resource_type='research_report', resource_id=row.id, details={
                'input_ids': [source.id for source in sources], 'classification': 'OWNER_PROVIDED_UNVERIFIED',
                'authorized': True, 'nonpersonal_attested': True, 'data_consent': True})
        return row, True

    def load(self, user_id, business_id, report_id):
        IdentityService(self.session, self.clock).require_membership(user_id, business_id)
        row = self.session.scalar(select(ResearchReportRecord).where(ResearchReportRecord.id == report_id,
            ResearchReportRecord.business_id == business_id, ResearchReportRecord.owner_user_id.is_not(None)))
        if row is None:
            raise IdentityError('report_unavailable', 'Merchant report not found in this workspace.', 404)
        report = ResearchReport.model_validate_json(row.report_json)
        if report.origin != 'merchant_provided':
            raise IdentityError('report_unavailable', 'Merchant report not found in this workspace.', 404)
        return row, report

    def inference_report(self, user_id, business_id, report_id):
        identity = IdentityService(self.session, self.clock)
        identity.require_verified_user(user_id)
        identity.require_membership(user_id, business_id, roles={'owner', 'admin', 'editor'})
        row, report = self.load(user_id, business_id, report_id)
        if row.status != 'PENDING_ANALYSIS':
            raise IdentityError('analysis_already_finalized', 'The report will not be sent again.', 409)
        return report

    def finish(self, user_id, business_id, report_id, report):
        identity = IdentityService(self.session, self.clock)
        identity.require_verified_user(user_id)
        identity.require_membership(user_id, business_id, roles={'owner', 'admin', 'editor'})
        row, original = self.load(user_id, business_id, report_id)
        report = ResearchReport.model_validate(report.model_dump())
        mutable = {'analysis', 'analysis_status', 'analysis_error_code', 'status', 'opportunities'}
        if original.model_dump(exclude=mutable) != report.model_dump(exclude=mutable) or report.analysis_status == 'pending':
            raise IdentityError('report_changed', 'Analysis cannot change its supplied inputs.', 409)
        result = self.session.execute(update(ResearchReportRecord).where(ResearchReportRecord.id == row.id,
            ResearchReportRecord.business_id == business_id, ResearchReportRecord.status == 'PENDING_ANALYSIS')
            .values(report_json=report.model_dump_json(), status='PARTIAL'))
        if result.rowcount != 1:
            raise IdentityError('analysis_already_finalized', 'This analysis was already finalized; it will not be sent again.', 409)
        identity.audit('merchant_analysis.recorded', user_id=user_id, business_id=business_id,
            resource_type='research_report', resource_id=row.id, details={'analysis_status': report.analysis_status,
                'error_code': report.analysis_error_code, 'independently_verified': False})


async def analyze_merchant_report(report, provider=None):
    try:
        result = await IntelligenceOrchestrator(provider).analyze_merchant(report.merchant_analysis_context())
        inferred = [claim for claim in result.claims if claim.kind == 'INFERRED']
        if not inferred or not result.recommendations:
            raise IntelligenceError('invalid_model_output', 'A report needs sourced findings and recommendations.')
        return ResearchReport.model_validate({**report.model_dump(), 'analysis_status': 'completed',
            'analysis': result, 'analysis_error_code': None,
            'opportunities': [{'title': claim.text[:160], 'description': claim.text,
                'evidence_ids': claim.evidence_ids, 'next_step': 'Review this hypothesis against the supplied inputs before deciding.'}
                for claim in inferred[:5]]})
    except IntelligenceError as exc:
        code = exc.code if re.fullmatch(r'[a-z_]{1,80}', exc.code) else 'model_unavailable'
        return ResearchReport.model_validate({**report.model_dump(), 'analysis_status': 'unavailable',
            'analysis': None, 'analysis_error_code': code})
