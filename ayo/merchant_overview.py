"""Merchant overview uses persisted workspace records, never sample commerce data."""
import time

from sqlalchemy import func, select

from ayo.identity import IdentityService
from ayo.models import AuditEvent, Lead, ResearchReportRecord
from ayo.merchant_models import Task

ACTIVITY_LABELS = {
    'report.claimed': 'Research saved to this workspace',
    'business.created': 'Business workspace created',
    'business.profile_updated': 'Business profile updated',
    'lead.discovered': 'A sourced prospect was discovered',
    'lead.qualified': 'A prospect was qualified after review',
    'intelligence.analyzed': 'Ayo analysis recorded',
}


def overview(session, user_id, business_id):
    IdentityService(session).require_membership(user_id, business_id)
    def count(model, *criteria):
        return session.scalar(select(func.count()).select_from(model).where(model.business_id == business_id, *criteria))
    return {
        'report_count': count(ResearchReportRecord, ResearchReportRecord.status.in_(['PARTIAL', 'SUCCEEDED'])),
        'partial_count': count(ResearchReportRecord, ResearchReportRecord.status == 'PARTIAL'),
        'lead_count': count(Lead),
        'qualified_count': count(Lead, Lead.status == 'qualified'),
        'open_task_count': count(Task, Task.status.in_(['open', 'in_progress'])),
        'completed_task_count': count(Task, Task.status == 'done'),
        'tasks': session.scalars(select(Task).where(Task.business_id == business_id,
            Task.status.in_(['open', 'in_progress'])).order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc()).limit(5)).all(),
    }


def activity_page(session, user_id, business_id, page=1):
    IdentityService(session).require_membership(user_id, business_id)
    page = max(1, min(page, 10_000))
    total = session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.business_id == business_id))
    rows = session.scalars(select(AuditEvent).where(AuditEvent.business_id == business_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).offset((page - 1) * 30).limit(30)).all()
    return {'events': rows, 'page': page, 'has_next': page * 30 < total, 'total': total,
            'generated_at': time.time()}
