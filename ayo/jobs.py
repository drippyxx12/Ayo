"""Durable leased research jobs; browser requests never run a crawl."""
import json
import time

from sqlalchemy import or_, select

from ayo.identity import IdentityError, token_hash
from ayo.models import ResearchJob
from ayo.report_storage import ReportStore
from ayo.research import ResearchError, ResearchService, _public_url


def enqueue(session, fernet, *, url, country, business_name, anonymous_id):
    url = _public_url(url)
    if country not in ('', 'NG', 'GH') or len(business_name) > 240:
        raise ResearchError('invalid_input', 'Choose a supported market and business name.', 400)
    payload = {'url': url, 'country': country, 'business_name': business_name, 'anonymous_id': anonymous_id}
    row = ResearchJob(anonymous_session_hash=token_hash(anonymous_id),
                      payload_cipher=fernet.encrypt(json.dumps(payload).encode()).decode())
    session.add(row)
    session.flush()
    return row


def get_job(session, job_id, anonymous_id):
    row = session.get(ResearchJob, job_id)
    if not row or not anonymous_id or row.anonymous_session_hash != token_hash(anonymous_id):
        raise IdentityError('job_unavailable', 'Research job not found.', 404)
    return row


async def process_one(factory, fernet, research_factory=ResearchService.from_env, clock=time.time):
    """A lease fences stale workers; failed work never produces success/report data."""
    now = clock()
    with factory() as session:
        row = session.scalar(select(ResearchJob).where(or_(
            ResearchJob.status == 'queued',
            (ResearchJob.status == 'running') & (ResearchJob.lease_until <= now),
        )).order_by(ResearchJob.created_at).with_for_update(skip_locked=True))
        if row is None:
            return False
        if row.attempts >= 3 or row.created_at + 86400 <= now:
            row.status, row.error_code, row.finished_at = 'failed', 'job_expired', now
            session.commit()
            return True
        row.status, row.attempts, row.lease_until = 'running', row.attempts + 1, now + 120
        job_id, attempt, cipher = row.id, row.attempts, row.payload_cipher
        session.commit()
    report, error = None, None
    try:
        payload = json.loads(fernet.decrypt(cipher.encode()))
        report = await research_factory().research(payload['url'], country=payload['country'], business_name=payload['business_name'])
    except ResearchError as exc:
        error = exc.code
    except Exception:
        # The UI and logs never receive provider bodies, keys, raw HTML or PII.
        error = 'research_failed'
    with factory() as session:
        row = session.scalar(select(ResearchJob).where(ResearchJob.id == job_id).with_for_update())
        if row.status != 'running' or row.attempts != attempt:
            return True
        if report is None:
            row.status, row.error_code = 'failed', error
        else:
            record, claim = ReportStore(session, clock).save_preview(report, payload['anonymous_id'])
            row.status, row.report_id = 'succeeded', record.id
            row.claim_cipher = fernet.encrypt(claim.encode()).decode()
        row.finished_at, row.lease_until = clock(), None
        session.commit()
    return True
