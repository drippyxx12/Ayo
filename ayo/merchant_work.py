"""Tenant-checked local profile and task operations. Callers own transactions.

Completing a task records the merchant's statement, never a provider execution,
delivered message, customer response, sale or independently measured outcome.
"""
from datetime import date, datetime
import re
import time

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ayo.identity import IdentityError, IdentityService
from ayo.markets import MARKETS
from ayo.merchant_models import BusinessProfile, Task
from ayo.models import Business, Lead, ResearchReportRecord

TASK_STATUSES = ('open', 'in_progress', 'done', 'cancelled')
UNSET = object()


def text_value(value, field, maximum, *, minimum=0):
    if not isinstance(value, str):
        raise IdentityError('invalid_' + field, f'Enter valid {field.replace("_", " ")}.')
    value = value.replace('\r\n', '\n').strip()
    if not minimum <= len(value) <= maximum or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        raise IdentityError('invalid_' + field,
            f'{field.replace("_", " ").capitalize()} must contain {minimum}–{maximum} characters without control characters.')
    return value


def date_value(value):
    if value is None or value == '':
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise IdentityError('invalid_due_date', 'Choose a valid due date in YYYY-MM-DD format.')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise IdentityError('invalid_due_date', 'Choose a valid due date in YYYY-MM-DD format.') from None


def version_value(value, *, allow_zero=False):
    if (isinstance(value, bool) or not isinstance(value, int)
            or not (0 if allow_zero else 1) <= value <= 2_147_483_646):
        raise IdentityError('invalid_version', 'Reload this page before saving your changes.', 409)
    return value


class ProfileService:
    def __init__(self, session, clock=time.time):
        self.session, self.clock = session, clock
        self.identity = IdentityService(session)

    def get(self, user_id, business_id):
        self.identity.require_membership(user_id, business_id)
        return self.session.get(BusinessProfile, business_id)

    def save(self, user_id, business_id, *, name, country, offer='', products='', audience='', location='', goals='', version=0):
        self.identity.require_verified_user(user_id)
        self.identity.require_membership(user_id, business_id, roles={'owner', 'admin'})
        name = text_value(name, 'business_name', 160, minimum=2)
        if country not in MARKETS:
            raise IdentityError('invalid_country', 'Choose Nigeria or Ghana as your business market.')
        values = {field: text_value(value, field, 250 if field == 'location' else 3000)
                  for field, value in dict(offer=offer, products=products, audience=audience, location=location, goals=goals).items()}
        version_value(version, allow_zero=True)
        business = self.session.scalar(select(Business).where(Business.id == business_id).with_for_update())
        row = self.session.get(BusinessProfile, business_id)
        if (row.version if row else 0) != version:
            raise IdentityError('stale_profile', 'This business profile changed. Reload the page and review the latest version.', 409)
        now = self.clock()
        changed_fields = [field for field, value in values.items() if row is None or getattr(row, field) != value]
        if business.name != name:
            changed_fields.append('name')
        if business.country != country:
            changed_fields.append('country')
        if row:
            result = self.session.execute(update(BusinessProfile).where(
                BusinessProfile.business_id == business_id, BusinessProfile.version == version).values(
                    **values, updated_by=user_id, updated_at=now, version=version + 1),
                execution_options={'synchronize_session': False})
            if result.rowcount != 1:
                raise IdentityError('stale_profile', 'This business profile changed. Reload the page before saving.', 409)
            self.session.expire(row)
        else:
            row = BusinessProfile(business_id=business_id, **values, updated_by=user_id, created_at=now,
                                  updated_at=now, version=1, source_classification='OWNER_PROVIDED_UNVERIFIED')
            # The unique workspace key also rejects simultaneous first saves on SQLite.
            try:
                self.session.add(row)
                self.session.flush()
            except IntegrityError:
                raise IdentityError('stale_profile', 'This business profile changed. Reload the page before saving.', 409) from None
        market = MARKETS[country]
        business.name, business.country = name, country
        business.currency, business.timezone = market['currency'], market['timezone']
        self.identity.audit('business.profile_updated', user_id=user_id, business_id=business_id,
            resource_type='business_profile', resource_id=business_id,
            details={'changed_fields': changed_fields, 'from_version': version, 'to_version': version + 1,
                     'source_classification': 'OWNER_PROVIDED_UNVERIFIED', 'ownership_verified': False})
        self.session.flush()
        return row


class TaskService:
    def __init__(self, session, clock=time.time):
        self.session, self.clock = session, clock
        self.identity = IdentityService(session)

    def _write_access(self, user_id, business_id):
        self.identity.require_verified_user(user_id)
        self.identity.require_membership(user_id, business_id, roles={'owner', 'admin', 'editor'})

    def _source(self, model, source_id, business_id, label):
        if not source_id:
            return None
        source_id = text_value(source_id, 'source_id', 64, minimum=1)
        if self.session.scalar(select(model.id).where(model.id == source_id, model.business_id == business_id)) is None:
            raise IdentityError('source_not_found', f'The source {label} is not available in this workspace.', 404)
        return source_id

    def list(self, user_id, business_id, status=None):
        self.identity.require_membership(user_id, business_id)
        query = select(Task).where(Task.business_id == business_id)
        if status:
            if status not in TASK_STATUSES:
                raise IdentityError('invalid_task_status', 'Choose an available task status.')
            query = query.where(Task.status == status)
        return self.session.scalars(query.order_by(Task.created_at.desc(), Task.id)).all()

    def get(self, user_id, business_id, task_id):
        self.identity.require_membership(user_id, business_id)
        row = self.session.scalar(select(Task).where(Task.id == task_id, Task.business_id == business_id)
                                  .execution_options(populate_existing=True))
        if row is None:
            raise IdentityError('task_not_found', 'Task not found in this workspace.', 404)
        return row

    def create(self, user_id, business_id, *, title, description='', due_date=None, source_report_id=None, source_lead_id=None):
        self._write_access(user_id, business_id)
        title, description = text_value(title, 'title', 200, minimum=1), text_value(description, 'description', 5000)
        due_date = date_value(due_date)
        report_id = self._source(ResearchReportRecord, source_report_id, business_id, 'report')
        lead_id = self._source(Lead, source_lead_id, business_id, 'lead')
        now = self.clock()
        row = Task(business_id=business_id, title=title, description=description, due_date=due_date,
                   source_report_id=report_id, source_lead_id=lead_id, status='open', created_by=user_id,
                   created_at=now, updated_at=now, version=1)
        self.session.add(row)
        self.session.flush()
        self.identity.audit('task.created', user_id=user_id, business_id=business_id, resource_type='task', resource_id=row.id,
            details={'status': 'open', 'version': 1, 'source_report_id': report_id, 'source_lead_id': lead_id})
        return row

    def update(self, user_id, business_id, task_id, *, version, title=None, description=None, status=None, due_date=UNSET):
        self._write_access(user_id, business_id)
        version_value(version)
        row = self.get(user_id, business_id, task_id)
        if row.version != version:
            raise IdentityError('stale_task', 'This task changed. Reload the page and review the latest version before saving.', 409)
        values = {}
        if title is not None:
            values['title'] = text_value(title, 'title', 200, minimum=1)
        if description is not None:
            values['description'] = text_value(description, 'description', 5000)
        if status is not None:
            if status not in TASK_STATUSES:
                raise IdentityError('invalid_task_status', 'Choose an available task status.')
            values['status'] = status
        if due_date is not UNSET:
            values['due_date'] = date_value(due_date)
        old_status = row.status
        values.update(version=version + 1, updated_at=self.clock())
        result = self.session.execute(update(Task).where(Task.id == task_id, Task.business_id == business_id,
            Task.version == version).values(**values), execution_options={'synchronize_session': False})
        if result.rowcount != 1:
            raise IdentityError('stale_task', 'This task changed. Reload the page and review the latest version before saving.', 409)
        details = {'from_status': old_status, 'to_status': values.get('status', old_status),
                   'from_version': version, 'to_version': version + 1,
                   'changed_fields': sorted(set(values) - {'version', 'updated_at'})}
        if values.get('status') == 'done':
            details['completion_classification'] = 'MERCHANT_RECORDED_TASK_COMPLETION'
            details['external_outcome_verified'] = False
        self.identity.audit('task.updated', user_id=user_id, business_id=business_id, resource_type='task',
                            resource_id=task_id, details=details)
        self.session.expire(row)
        self.session.flush()
        return row
