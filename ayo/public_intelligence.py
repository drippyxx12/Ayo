"""Gemini synthesis over committed public research evidence; no tenant or writes.

The job worker persists and re-reads evidence before calling this service. No
source URL is fetched here and no model gets credentials, sessions or private
workspace data. Missing/rejected inference leaves explicit partial research.
"""
import asyncio

from ayo.intelligence import IntelligenceError, IntelligenceOrchestrator, ModelProvider
from ayo.research import ResearchReport


async def enrich_report(report: ResearchReport, provider: ModelProvider | None = None, *, timeout_seconds: float = 40) -> ResearchReport:
    if not 0 < timeout_seconds <= 45:
        raise ValueError('Public inference deadline must be positive and below the worker lease')
    report = ResearchReport.model_validate(report.model_dump())
    try:
        async with asyncio.timeout(timeout_seconds):
            result = await IntelligenceOrchestrator(provider).analyze_public(report.public_analysis_context())
        if not result.claims and not result.recommendations:
            raise IntelligenceError('insufficient_model_findings', 'No useful source-backed findings were returned.')
        changes = {'analysis_status': 'completed', 'analysis': result, 'analysis_error_code': None}
        # Revalidate at this boundary rather than trusting model_copy.
        return ResearchReport.model_validate({**report.model_dump(), **changes})
    except TimeoutError:
        return ResearchReport.model_validate({**report.model_dump(), 'status': 'PARTIAL',
            'analysis_status': 'unavailable', 'analysis': None, 'analysis_error_code': 'model_timeout'})
    except IntelligenceError as exc:
        rejected = exc.code in {'invalid_model_output', 'unsupported_citation', 'unsupported_observation',
            'missing_citation', 'invalid_unknown', 'unverified_owner_claim', 'unsupported_financial_claim',
            'unauthorized_action_claim', 'insufficient_model_findings'}
        code = 'model_output_rejected' if rejected else {
            'provider_not_configured': 'model_not_configured',
            'provider_spend_not_authorized': 'model_spend_not_authorized',
            'provider_rate_limited': 'model_rate_limited',
            'provider_timeout': 'model_timeout',
            'provider_authorization_failed': 'model_authorization_failed',
            'provider_data_policy_not_reviewed': 'model_data_policy_not_reviewed',
            'model_safety_blocked': 'model_safety_blocked',
            'budget_not_configured': 'model_budget_not_configured',
            'budget_policy_expired': 'model_budget_policy_expired',
            'budget_exceeded': 'model_budget_exceeded',
            'budget_policy_changed': 'model_budget_policy_changed',
            'budget_storage_unavailable': 'model_budget_storage_unavailable',
            'dispatch_already_reserved': 'model_dispatch_already_reserved',
        }.get(exc.code, 'model_unavailable')
        return ResearchReport.model_validate({**report.model_dump(), 'status': 'PARTIAL',
            'analysis_status': 'rejected' if rejected else 'unavailable',
            'analysis': None, 'analysis_error_code': code})
