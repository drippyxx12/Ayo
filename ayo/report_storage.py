"""Tenant-scoped evidence reports and atomic, session-bound preview claims."""
import secrets
import time

from sqlalchemy import select, update

from ayo.identity import IdentityError, IdentityService, token_hash
from ayo.models import Membership, ResearchReportRecord, ReportClaim
from ayo.research import ResearchReport


class ReportStore:
    def __init__(self, session, clock=time.time):
        self.session, self.clock = session, clock

    def save_preview(self, report: ResearchReport, anonymous_id: str):
        if not anonymous_id or len(anonymous_id) < 32:
            raise IdentityError('invalid_session', 'Start a new business search.', 403)
        # Validate again at the persistence boundary; never store caller-asserted
        # evidence booleans or unvalidated generated citations.
        report = ResearchReport.model_validate(report.model_dump())
        now = self.clock()
        row = ResearchReportRecord(
            title=report.business_name, status=report.status,
            target_url=report.target_url, country=report.country,
            report_json=report.model_dump_json(), created_at=now,
            expires_at=now + 86400, anonymous_session_hash=token_hash(anonymous_id),
        )
        self.session.add(row)
        self.session.flush()
        raw = secrets.token_urlsafe(48)
        self.session.add(ReportClaim(
            token_hash=token_hash(raw), report_id=row.id,
            anonymous_session_hash=token_hash(anonymous_id), expires_at=now + 1800,
        ))
        return row, raw

    def accessible(self, report_id, user_id=None, anonymous_id=None):
        row = self.session.get(ResearchReportRecord, report_id)
        if row is None:
            raise IdentityError('report_unavailable', 'Report not found.', 404)
        if row.business_id:
            if user_id is None:
                raise IdentityError('report_unavailable', 'Report not found.', 404)
            try:
                IdentityService(self.session, self.clock).require_membership(user_id, row.business_id)
            except IdentityError:
                raise IdentityError('report_unavailable', 'Report not found.', 404)
        elif (not anonymous_id or not row.anonymous_session_hash or
              not secrets.compare_digest(token_hash(anonymous_id), row.anonymous_session_hash) or
              row.expires_at is None or row.expires_at <= self.clock()):
            raise IdentityError('report_unavailable', 'Report not found.', 404)
        return row

    def claim(self, raw_token, anonymous_id, user_id, business_id):
        identity = IdentityService(self.session, self.clock)
        identity.require_verified_user(user_id)
        identity.require_membership(user_id, business_id, roles={'owner', 'admin', 'editor'})
        if not isinstance(raw_token, str) or not 32 <= len(raw_token) <= 200 or not anonymous_id:
            raise IdentityError('claim_unavailable', 'This report claim is invalid or expired.', 403)
        now = self.clock()
        report_id = self.session.execute(update(ReportClaim).where(
            ReportClaim.token_hash == token_hash(raw_token),
            ReportClaim.anonymous_session_hash == token_hash(anonymous_id),
            ReportClaim.consumed_at.is_(None), ReportClaim.expires_at > now,
        ).values(consumed_at=now, user_id=user_id).returning(ReportClaim.report_id)).scalar_one_or_none()
        if report_id is None:
            raise IdentityError('claim_unavailable', 'This report claim is invalid or expired.', 403)
        claimed = self.session.execute(update(ResearchReportRecord).where(
            ResearchReportRecord.id == report_id, ResearchReportRecord.business_id.is_(None),
            ResearchReportRecord.owner_user_id.is_(None), ResearchReportRecord.expires_at > now,
        ).values(owner_user_id=user_id, business_id=business_id, expires_at=None,
                 anonymous_session_hash=None).returning(ResearchReportRecord.id)).scalar_one_or_none()
        if claimed is None:
            raise IdentityError('claim_unavailable', 'This report has already been saved or expired.', 409)
        identity.audit('report.claimed', user_id=user_id, business_id=business_id,
                       resource_type='research_report', resource_id=claimed)
        self.session.flush()
        return self.session.get(ResearchReportRecord, claimed, populate_existing=True)

    def for_business(self, user_id, business_id):
        IdentityService(self.session, self.clock).require_membership(user_id, business_id)
        return self.session.scalars(select(ResearchReportRecord).where(
            ResearchReportRecord.business_id == business_id,
        ).order_by(ResearchReportRecord.created_at.desc())).all()
