"""Durable leased research jobs; browser requests never run a crawl."""
import json
import time
from datetime import datetime, timezone

from sqlalchemy import or_, select

from ayo.identity import IdentityError, token_hash
from ayo.models import AuditEvent, ResearchJob
from ayo.report_storage import ReportStore
from ayo.research import ResearchError, ResearchService, _public_url
from ayo.public_intelligence import enrich_report
from ayo.budgets import BudgetError
from ayo.provider_usage import budget_context


PROGRESS_LABELS = {
    'queued': 'Research queued',
    'fetching': 'Retrieving permitted public evidence',
    'resuming': 'Resuming committed evidence',
    'evidence_stored': 'Public evidence saved securely',
    'analyzing': 'Checking source-backed Gemini analysis',
    'retry_scheduled': 'Provider temporarily unavailable; bounded retry scheduled',
    'completed': 'Source-backed report published',
    'partial': 'Partial report published; review its limitations',
    'failed': 'Research stopped without a published report',
}
RETRYABLE_SOURCE_ERRORS = frozenset({'provider_rate_limited', 'provider_service_unavailable'})
SAFE_ERRORS = frozenset({
    'invalid_input', 'invalid_url', 'provider_not_configured', 'provider_spend_not_authorized',
    'provider_authorization_failed', 'provider_rate_limited', 'provider_service_unavailable',
    'provider_failure', 'provider_response_too_large', 'provider_malformed',
    'research_egress_not_verified', 'source_policy_not_approved', 'source_unavailable',
    'research_timeout', 'provider_unsafe_redirect', 'insufficient_evidence',
    'evidence_unavailable', 'job_expired', 'research_failed',
    'budget_not_configured', 'budget_policy_expired', 'budget_exceeded',
    'budget_policy_changed', 'dispatch_already_reserved',
    'source_outcome_uncertain', 'provider_timeout', 'provider_budget_exhausted',
    'budget_storage_unavailable',
    'source_access_restricted',
})


def _progress(session, job, stage, now, *, reason=None, retry_at=None, analysis_status=None):
    """Persist only server-defined milestones, never source text or capabilities."""
    details = {'stage': stage, 'attempt': job.attempts}
    if reason in SAFE_ERRORS:
        details['reason'] = reason
    if retry_at is not None:
        details['retry_at'] = retry_at
    if analysis_status in {'not_requested', 'pending', 'completed', 'unavailable', 'rejected'}:
        details['analysis_status'] = analysis_status
    session.add(AuditEvent(action='research_job.' + stage, resource_type='research_job',
        resource_id=job.id, details_json=json.dumps(details, sort_keys=True), created_at=now))


def enqueue(session, fernet, *, url, country, business_name, anonymous_id, request_id=None):
    url = _public_url(url)
    if country not in ('', 'NG', 'GH') or len(business_name) > 240:
        raise ResearchError('invalid_input', 'Choose a supported market and business name.', 400)
    payload = {'url': url, 'country': country, 'business_name': business_name, 'anonymous_id': anonymous_id}
    if request_id is not None:
        payload['request_id'] = request_id
    row = ResearchJob(anonymous_session_hash=token_hash(anonymous_id),
                      payload_cipher=fernet.encrypt(json.dumps(payload).encode()).decode())
    session.add(row)
    session.flush()
    _progress(session, row, 'queued', row.created_at)
    return row


def get_job(session, job_id, anonymous_id):
    row = session.get(ResearchJob, job_id)
    if not row or not anonymous_id or row.anonymous_session_hash != token_hash(anonymous_id):
        raise IdentityError('job_unavailable', 'Research job not found.', 404)
    return row


def job_progress(session, job_id, anonymous_id):
    """Return bounded, allowlisted progress only to the job's browser capability.

    Audit metadata is not trusted as presentation content. Unknown stages,
    malformed rows and unrecognized details are omitted rather than rendered.
    """
    get_job(session, job_id, anonymous_id)
    events = session.scalars(select(AuditEvent).where(
        AuditEvent.resource_type == 'research_job', AuditEvent.resource_id == job_id,
        AuditEvent.action.in_(['research_job.' + stage for stage in PROGRESS_LABELS]),
    ).order_by(AuditEvent.id.desc()).limit(24)).all()
    result = []
    for event in reversed(events):
        stage = event.action.removeprefix('research_job.')
        try:
            details = json.loads(event.details_json)
            if not isinstance(details, dict) or details.get('stage') != stage:
                continue
            attempt = details.get('attempt')
            if type(attempt) is not int or not 0 <= attempt <= 3:
                continue
            at = datetime.fromtimestamp(event.created_at, timezone.utc)
            item = {'stage': stage, 'label': PROGRESS_LABELS[stage], 'attempt': attempt,
                    'datetime': at.isoformat(), 'display_time': at.strftime('%d %b %Y · %H:%M:%S UTC')}
            retry_at = details.get('retry_at')
            if stage == 'retry_scheduled' and type(retry_at) in (int, float) and retry_at > event.created_at:
                item['retry_at'] = datetime.fromtimestamp(retry_at, timezone.utc).strftime('%H:%M:%S UTC')
            result.append(item)
        except (ValueError, TypeError, OverflowError, OSError):
            continue
    return result


async def process_one(factory, fernet, research_factory=ResearchService.from_env, clock=time.time, *, analysis_provider=None):
    """A lease fences stale workers; failed work never produces success/report data."""
    now = clock()
    with factory() as session:
        row = session.scalar(select(ResearchJob).where(or_(
            (ResearchJob.status == 'queued') & or_(ResearchJob.lease_until.is_(None), ResearchJob.lease_until <= now),
            (ResearchJob.status == 'running') & (ResearchJob.lease_until <= now),
        )).order_by(ResearchJob.created_at).with_for_update(skip_locked=True))
        if row is None:
            return False
        if row.attempts >= 3 or row.created_at + 86400 <= now:
            row.status, row.error_code, row.finished_at = 'failed', 'job_expired', now
            row.lease_until = None
            _progress(session, row, 'failed', now, reason='job_expired')
            session.commit()
            return True
        if row.status == 'running' and row.attempts > 0 and row.report_id is None:
            # A lost worker may have submitted a billed crawl before it could
            # checkpoint. Without a recoverable receipt, never recrawl silently.
            row.status, row.error_code, row.finished_at = 'failed', 'source_outcome_uncertain', now
            row.lease_until = None
            _progress(session, row, 'failed', now, reason='source_outcome_uncertain')
            session.commit()
            return True
        row.status, row.attempts, row.lease_until = 'running', row.attempts + 1, now + 120
        row.error_code, row.finished_at = None, None
        job_id, attempt, cipher, report_id = row.id, row.attempts, row.payload_cipher, row.report_id
        anonymous_hash = row.anonymous_session_hash
        _progress(session, row, 'resuming' if report_id else 'fetching', now)
        session.commit()

    def current(row):
        return (row is not None and row.status == 'running' and row.attempts == attempt and
                row.lease_until is not None and row.lease_until > clock())

    report, error = None, None
    try:
        payload = json.loads(fernet.decrypt(cipher.encode()))
        usage_scope = {'scope_id': 'anonymous:' + anonymous_hash,
                       'request_id': payload.get('request_id') or job_id, 'dispatch_prefix': f'{job_id}:{attempt}'}
        if report_id is None:
            with budget_context(factory, **usage_scope):
                evidence_report = await research_factory().research(payload['url'], country=payload['country'], business_name=payload['business_name'])
            with factory() as session:
                row = session.scalar(select(ResearchJob).where(ResearchJob.id == job_id).with_for_update())
                if not current(row):
                    return True
                checkpoint = ReportStore(session, clock).stage_preview(evidence_report, payload['anonymous_id'])
                report_id, row.report_id = checkpoint.id, checkpoint.id
                row.lease_until = clock() + 60
                _progress(session, row, 'evidence_stored', clock())
                session.commit()  # Immutable sources exist durably BEFORE inference.
        with factory() as session:
            row = session.scalar(select(ResearchJob).where(ResearchJob.id == job_id).with_for_update())
            if not current(row):
                return True
            evidence_report = ReportStore(session, clock).pending_preview(report_id, payload['anonymous_id'])
            row.lease_until = clock() + 60
            _progress(session, row, 'analyzing', clock())
            session.commit()
        # No database transaction spans the model HTTP request. A crash resumes
        # the committed evidence checkpoint instead of re-fetching the business.
        # Stable across attempts: an interrupted billed model dispatch must not
        # be silently repeated. The durable ledger refuses duplicate dispatch.
        with budget_context(factory, **{**usage_scope, 'dispatch_prefix': job_id}):
            report = await enrich_report(evidence_report, analysis_provider)
    except BudgetError as exc:
        error = exc.code if exc.code in SAFE_ERRORS else 'research_failed'
    except ResearchError as exc:
        error = exc.code if exc.code in SAFE_ERRORS else 'research_failed'
    except IdentityError:
        error = 'evidence_unavailable'
    except Exception:
        # The UI and logs never receive provider bodies, keys, raw HTML or PII.
        error = 'research_failed'
    with factory() as session:
        row = session.scalar(select(ResearchJob).where(ResearchJob.id == job_id).with_for_update())
        if not current(row):
            return True
        if report is None:
            if report_id is None and error in RETRYABLE_SOURCE_ERRORS and attempt < 3:
                # Only definitive provider rejection is retryable. Timeouts,
                # disconnects and interrupted inference may already be billed.
                retry_at = clock() + 15 * (2 ** (attempt - 1))
                row.status, row.error_code, row.lease_until = 'queued', error, retry_at
                _progress(session, row, 'retry_scheduled', clock(), reason=error, retry_at=retry_at)
                session.commit()
                return True
            row.status, row.error_code = 'failed', error
            _progress(session, row, 'failed', clock(), reason=error)
        else:
            record, claim = ReportStore(session, clock).finalize_preview(report_id, report, payload['anonymous_id'])
            row.status, row.report_id = 'succeeded', record.id
            row.claim_cipher = fernet.encrypt(claim.encode()).decode()
            _progress(session, row, 'partial' if report.status == 'PARTIAL' else 'completed',
                      clock(), analysis_status=report.analysis_status)
        row.finished_at, row.lease_until = clock(), None
        session.commit()
    return True
