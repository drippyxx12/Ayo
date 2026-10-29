"""Bounded deletion of expired anonymous/security artifacts, never user grants."""
import time
from sqlalchemy import delete, or_, select, update
from ayo.site_control import schema_ready
from ayo.site_control_models import SiteControlClaim
from ayo.models import AuditEvent, AuthAttempt, AuthSession, IdentityToken, MailOutbox, ReportClaim, ResearchJob, ResearchReportRecord


def cleanup_expired(session, now=None):
    now = time.time() if now is None else now
    queries = [
        # Only unpublished job checkpoints expire here. Saved report versions
        # remain private history after their short-lived job receipt expires.
        delete(ResearchReportRecord).where(ResearchReportRecord.status == 'PENDING_ANALYSIS',
            ResearchReportRecord.id.in_(select(ResearchJob.report_id).where(ResearchJob.created_at <= now - 86400))),
        delete(AuditEvent).where(AuditEvent.resource_type == 'research_job',
                                 AuditEvent.business_id.is_(None), AuditEvent.created_at <= now - 86400),
        delete(ResearchJob).where(ResearchJob.created_at <= now - 86400),
        delete(ReportClaim).where(ReportClaim.expires_at <= now),
        delete(ResearchReportRecord).where(ResearchReportRecord.business_id.is_(None),
                                          ResearchReportRecord.expires_at <= now),
        delete(AuthSession).where(AuthSession.expires_at <= now),
        delete(IdentityToken).where(IdentityToken.expires_at <= now),
        delete(AuthAttempt).where(AuthAttempt.window_started <= now - 86400),
        delete(MailOutbox).where(MailOutbox.created_at <= now - 86400),
    ]
    count = sum(session.execute(query).rowcount for query in queries)
    if schema_ready(session):
        count += session.execute(update(SiteControlClaim).where(or_(
            (SiteControlClaim.status.in_(['pending', 'failed', 'checking'])) & (SiteControlClaim.expires_at <= now),
            (SiteControlClaim.status == 'verified') & (SiteControlClaim.verified_until <= now),
        )).values(status='expired', token_cipher=None, lease_hash=None, lease_until=None)).rowcount
    return count
