"""Reviewed private research refreshes over the existing encrypted job queue.

The encrypted scope binds requester, workspace, original report and its exact
JSON hash. Fresh permissions are checked at dispatch and publication. Audit
events link versions for review/cleanup; they do not grant access by themselves.
"""
import hashlib
import json
import re
import secrets
import time

from sqlalchemy import select

from ayo.identity import IdentityError, IdentityService, token_hash
from ayo.models import AuditEvent, Membership, ResearchJob, ResearchReportRecord
from ayo.research import ResearchReport, _same_research_target
from ayo.research_workspace import ResearchWorkspace


class RefreshService:
    def __init__(self, session, fernet, clock=time.time):
        self.session, self.fernet, self.clock = session, fernet, clock

    def original(self, user_id, business_id, report_id, *, write=False):
        identity = IdentityService(self.session, self.clock)
        if write:
            identity.require_verified_user(user_id)
            identity.require_membership(user_id, business_id, roles={'owner', 'admin', 'editor'})
            member = self.session.scalar(select(Membership).where(Membership.user_id == user_id,
                Membership.business_id == business_id, Membership.role.in_({'owner', 'admin', 'editor'})).with_for_update())
            if member is None:
                raise IdentityError('forbidden_tenant', 'This workspace no longer permits the refresh.', 403)
        row, report = ResearchWorkspace(self.session, self.clock)._load(user_id, business_id, report_id)
        if report.origin != 'public_web':
            raise IdentityError('refresh_not_supported', 'Owner-supplied inputs must be revised through business analysis, not crawled.', 400)
        return row, report

    def request(self, user_id, business_id, report_id, *, request_id, reviewed=False):
        row, report = self.original(user_id, business_id, report_id, write=True)
        if reviewed is not True or not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', request_id):
            raise IdentityError('refresh_review_required', 'Review the refresh scope and reload the form before submitting.', 400)
        scope = {'user_id': user_id, 'business_id': business_id, 'source_report_id': row.id,
                 'source_hash': hashlib.sha256(row.report_json.encode()).hexdigest()}
        job_id = token_hash('reviewed-refresh:' + str(user_id) + ':' + business_id + ':' + row.id + ':' + request_id)
        existing = self.session.get(ResearchJob, job_id)
        if existing is not None:
            if self.context(existing) != scope:
                raise IdentityError('request_conflict', 'This refresh request no longer matches its original report.', 409)
            return existing
        retired = self.session.scalar(select(AuditEvent.id).where(AuditEvent.action == 'research.refresh_requested',
            AuditEvent.resource_type == 'research_job', AuditEvent.resource_id == job_id))
        if retired is not None:
            raise IdentityError('refresh_expired', 'This refresh receipt expired. Review a new refresh instead of resubmitting the old form.', 409)
        identity = IdentityService(self.session, self.clock)
        identity._attempt('research-refresh', business_id, limit=3, window=3600)
        from ayo.jobs import enqueue
        job = enqueue(self.session, self.fernet, url=report.target_url, country=report.country,
            business_name=report.business_name, anonymous_id=secrets.token_urlsafe(48),
            request_id='refresh:' + job_id, job_id=job_id, refresh_scope=scope)
        identity.audit('research.refresh_requested', user_id=user_id, business_id=business_id,
            resource_type='research_job', resource_id=job.id, details={**scope, 'reviewed': True,
                'scope': 'current_bounded_public_research', 'ownership_verified': False})
        self.session.flush()
        return job

    def context(self, job):
        try:
            payload = json.loads(self.fernet.decrypt(job.payload_cipher.encode()))
            scope = payload['refresh']
            if (set(scope) != {'user_id', 'business_id', 'source_report_id', 'source_hash'} or
                    type(scope['user_id']) is not int or scope['user_id'] < 1 or
                    any(not isinstance(scope[key], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', scope[key])
                        for key in ('business_id', 'source_report_id')) or
                    not isinstance(scope['source_hash'], str) or not re.fullmatch(r'[0-9a-f]{64}', scope['source_hash'])):
                raise ValueError()
        except Exception:
            raise IdentityError('refresh_unavailable', 'Refresh request not found.', 404) from None
        return scope

    def validate(self, job):
        scope = self.context(job)
        row, original = self.original(scope['user_id'], scope['business_id'], scope['source_report_id'], write=True)
        payload = json.loads(self.fernet.decrypt(job.payload_cipher.encode()))
        if (hashlib.sha256(row.report_json.encode()).hexdigest() != scope['source_hash'] or
                payload['url'] != original.target_url or payload['country'] != original.country or
                payload['business_name'] != original.business_name):
            raise IdentityError('refresh_changed', 'The refresh no longer matches its reviewed source report.', 409)
        return scope, original

    def read(self, user_id, business_id, report_id, job_id):
        self.original(user_id, business_id, report_id)
        job = self.session.get(ResearchJob, job_id)
        if job is None:
            raise IdentityError('refresh_unavailable', 'Refresh request not found; saved versions remain in your research history.', 404)
        scope = self.context(job)
        if (scope['user_id'], scope['business_id'], scope['source_report_id']) != (user_id, business_id, report_id):
            raise IdentityError('refresh_unavailable', 'Refresh request not found.', 404)
        return job

    def stage(self, job, report):
        scope, original = self.validate(job)
        report = ResearchReport.model_validate(report.model_dump())
        if (report.origin != 'public_web' or report.country != original.country or
                report.business_name != original.business_name or
                not _same_research_target(original.target_url, report.target_url)):
            raise IdentityError('refresh_changed', 'New evidence must match the reviewed public research target.', 409)
        pending = ResearchReport.model_validate({**report.model_dump(), 'target_url': original.target_url,
                                               'analysis_status': 'pending',
                                               'analysis': None, 'analysis_error_code': None})
        row = ResearchReportRecord(business_id=scope['business_id'], owner_user_id=scope['user_id'],
            title=report.business_name, target_url=report.target_url, country=report.country,
            status='PENDING_ANALYSIS', report_json=pending.model_dump_json(), created_at=self.clock(),
            expires_at=None, anonymous_session_hash=None)
        self.session.add(row)
        self.session.flush()
        return row

    def pending(self, job):
        scope, _ = self.validate(job)
        row = self.session.get(ResearchReportRecord, job.report_id)
        if (row is None or row.id == scope['source_report_id'] or row.business_id != scope['business_id'] or
                row.owner_user_id != scope['user_id'] or row.status != 'PENDING_ANALYSIS'):
            raise IdentityError('refresh_unavailable', 'Pending refresh evidence not found.', 404)
        return row, ResearchReport.model_validate_json(row.report_json)

    def publish(self, job, report):
        row, pending = self.pending(job)
        report = ResearchReport.model_validate(report.model_dump())
        mutable = {'analysis', 'analysis_status', 'analysis_error_code', 'status'}
        if (pending.model_dump(exclude=mutable) != report.model_dump(exclude=mutable) or
                report.analysis_status == 'pending' or report.status != 'PARTIAL'):
            raise IdentityError('refresh_changed', 'Analysis cannot replace the refreshed source evidence.', 409)
        row.report_json, row.status = report.model_dump_json(), report.status
        scope = self.context(job)
        IdentityService(self.session, self.clock).audit('research.refresh_published',
            user_id=scope['user_id'], business_id=scope['business_id'], resource_type='research_report',
            resource_id=row.id, details={'source_report_id': scope['source_report_id'],
                'source_hash': scope['source_hash'], 'job_id': job.id, 'analysis_status': report.analysis_status,
                'ownership_verified': False})
        return row

    def discard_pending(self, job):
        """Remove only this job's unpublished temporary row after a failure."""
        try:
            scope = self.context(job)
        except IdentityError:
            return
        row = self.session.get(ResearchReportRecord, job.report_id) if job.report_id else None
        if (row is not None and row.id != scope['source_report_id'] and row.status == 'PENDING_ANALYSIS'
                and row.business_id == scope['business_id'] and row.owner_user_id == scope['user_id']):
            job.report_id = None
            self.session.delete(row)
