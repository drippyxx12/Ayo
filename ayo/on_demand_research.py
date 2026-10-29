"""Optional bounded worker host for an existing PostgreSQL queued command.

This is an explicit POST worker command, never a status-read side effect or an
after-response background task. The normal standalone worker remains supported.
"""
import asyncio
import os

from ayo.identity import IdentityError, IdentityService
from ayo.jobs import process_one


def available(session):
    return (os.getenv('AYO_ON_DEMAND_RESEARCH') == '1'
        and os.getenv('AYO_PROVIDER_SPEND_AUTHORIZED') == '0'
        and os.getenv('AYO_RESEARCH_SOURCE', 'direct_public_web') == 'direct_public_web'
        and session.get_bind().dialect.name == 'postgresql')


async def dispatch(mod, session, job):
    """Caller authorizes the exact job and CSRF before reaching this host."""
    if not available(session):
        raise IdentityError('worker_unavailable', 'This worker host is unavailable. A configured research worker is required.', 503)
    if job.status != 'queued' or job.attempts:
        session.commit()
        return False
    IdentityService(session)._attempt('on-demand-worker', job.anonymous_session_hash, limit=10, window=3600)
    selected = job.id
    session.commit()  # No web/read transaction spans worker network I/O.
    try:
        async with asyncio.timeout(100):
            return await process_one(mod.DbSession, mod.fernet, mod.app.state.research_factory,
                selected_job_id=selected,
                source_only=os.getenv('AYO_ON_DEMAND_GEMINI_AUTHORIZED', '0') != '1')
    except TimeoutError:
        # A lost response never triggers an automatic second source/model call.
        # Existing lease/checkpoint/uncertain-dispatch recovery stays authoritative.
        raise IdentityError('worker_deadline', 'The worker reached its time limit. Check saved progress before retrying.', 504) from None
