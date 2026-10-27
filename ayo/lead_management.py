"""Tenant-scoped prospect library, notes and source-bound review drafts.

All research text is low-trust evidence. There is no model, networking, sending,
contact-permission inference or pipeline mutation in this module.
"""
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import func, or_, select, update

from ayo.identity import IdentityError, IdentityService
from ayo.lead_models import LeadList, LeadListItem, LeadNote, OutreachDraft
from ayo.leads import LeadError, PipelineEvidence, transition_lead
from ayo.models import Business, Lead, LeadEvent, User
from ayo.website_research import SiteInputError, normalize_public_url

WRITE_ROLES = {'owner', 'admin', 'editor'}
STATUSES = ('discovered', 'qualified', 'contacted', 'replied', 'converted')


def text_input(value, name, maximum, *, required=True):
    if not isinstance(value, str):
        raise IdentityError('invalid_input', f'Enter a valid {name}.', 400)
    # Native browser forms serialize textarea line breaks as CRLF. Canonicalize
    # those pairs without accepting lone CR or other control characters.
    value = value.replace('\r\n', '\n').strip()
    if (required and not value) or len(value) > maximum or any(ord(c) < 32 and c not in '\n\t' or ord(c) == 127 for c in value):
        raise IdentityError('invalid_input', f'{name.capitalize()} must contain {"1–" if required else "at most "}{maximum} characters.', 400)
    return value


class LeadManagementService:
    def __init__(self, session):
        self.session = session
        self.identity = IdentityService(session)

    def _member(self, user_id, business_id, *, write=False):
        member = self.identity.require_membership(user_id, business_id, roles=WRITE_ROLES if write else None)
        if write:
            self.identity.require_verified_user(user_id)
        return member

    def _lead(self, business_id, lead_id, *, lock=False):
        query = select(Lead).where(Lead.business_id == business_id, Lead.id == lead_id)
        row = self.session.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise IdentityError('not_found', 'Prospect not found.', 404)
        return row

    def _list(self, business_id, list_id):
        row = self.session.scalar(select(LeadList).where(LeadList.business_id == business_id, LeadList.id == list_id))
        if row is None:
            raise IdentityError('not_found', 'Saved list not found.', 404)
        return row

    def _audit(self, action, user_id, business_id, resource_type, resource_id):
        # Content remains in the private resource, not copied into activity logs.
        self.identity.audit(action, user_id=user_id, business_id=business_id,
                            resource_type=resource_type, resource_id=resource_id)

    def _evidence(self, row):
        try:
            evidence = json.loads(row.evidence_json)
            return evidence if isinstance(evidence, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _events(self, business_id, lead_id):
        return self.session.scalars(select(LeadEvent).where(LeadEvent.business_id == business_id,
            LeadEvent.lead_id == lead_id).order_by(LeadEvent.created_at, LeadEvent.id)).all()

    def _status(self, row, events):
        # Later outcomes must have a valid ordered persisted evidence chain.
        current, provenance = 'discovered', 'discovery_source'
        for event in events:
            if event.to_status == 'discovered':
                continue
            if event.from_status != current:
                continue
            try:
                evidence = PipelineEvidence.model_validate_json(event.evidence_json)
                checked = transition_lead(business_id=row.business_id, actor_business_id=row.business_id,
                    current_status=current, next_status=event.to_status, evidence=evidence)
            except (LeadError, ValidationError, ValueError):
                continue
            current, provenance = checked.status, checked.provenance
        return current, provenance

    def _view(self, row, events=None):
        evidence = self._evidence(row)
        status, provenance = self._status(row, events if events is not None else self._events(row.business_id, row.id))
        def safe_url(value):
            try:
                return normalize_public_url(value)
            except (SiteInputError, TypeError, AttributeError):
                return None
        return {'id': row.id, 'name': row.name, 'url': safe_url(row.url), 'country': row.country,
            'status': status, 'status_provenance': provenance, 'fit_reason': row.fit_reason,
            'can_qualify': row.status == 'discovered' and status == 'discovered',
            'city': evidence.get('city', ''), 'source_id': evidence.get('source_id', ''),
            'source_url': safe_url(evidence.get('source_url', '')),
            'source_excerpt': evidence.get('source_excerpt', ''),
            'discovered_at': evidence.get('discovered_at', ''), 'contact_status': 'unknown'}

    def library(self, user_id, business_id, *, q='', status='', list_id=''):
        member = self._member(user_id, business_id)
        q = text_input(q, 'search', 160, required=False)
        if status and status not in STATUSES:
            raise IdentityError('invalid_filter', 'Choose a valid prospect status.', 400)
        if list_id:
            self._list(business_id, list_id)
        query = select(Lead).where(Lead.business_id == business_id)
        if q:
            escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            pattern = '%' + escaped + '%'
            query = query.where(or_(Lead.name.ilike(pattern, escape='\\'), Lead.fit_reason.ilike(pattern, escape='\\'),
                                    Lead.url.ilike(pattern, escape='\\')))
        if list_id:
            query = query.join(LeadListItem, (LeadListItem.lead_id == Lead.id) & (LeadListItem.business_id == Lead.business_id)).where(LeadListItem.list_id == list_id)
        rows = self.session.scalars(query.order_by(Lead.created_at.desc(), Lead.id)).all()
        events_by_lead = {row.id: [] for row in rows}
        if rows:
            events = self.session.scalars(select(LeadEvent).where(LeadEvent.business_id == business_id,
                LeadEvent.lead_id.in_(events_by_lead)).order_by(LeadEvent.created_at, LeadEvent.id)).all()
            for event in events:
                events_by_lead[event.lead_id].append(event)
        views = [self._view(row, events_by_lead[row.id]) for row in rows]
        if status:
            views = [row for row in views if row['status'] == status]
        lists = self.session.scalars(select(LeadList).where(LeadList.business_id == business_id)
            .order_by(func.lower(LeadList.name), LeadList.id)).all()
        counts = dict(self.session.execute(select(LeadListItem.list_id, func.count()).where(
            LeadListItem.business_id == business_id).group_by(LeadListItem.list_id)).all())
        user = self.session.get(User, user_id)
        return {'leads': views, 'lists': [{'id': item.id, 'name': item.name, 'description': item.description,
            'count': counts.get(item.id, 0)} for item in lists], 'filters': {'q': q, 'status': status, 'list_id': list_id},
            'can_write': member.role in WRITE_ROLES and user.email_verified_at is not None}

    def detail(self, user_id, business_id, lead_id):
        member = self._member(user_id, business_id)
        row = self._lead(business_id, lead_id)
        events = self._events(business_id, lead_id)
        notes = self.session.scalars(select(LeadNote).where(LeadNote.business_id == business_id,
            LeadNote.lead_id == lead_id).order_by(LeadNote.created_at.desc(), LeadNote.id)).all()
        draft = self.session.scalar(select(OutreachDraft).where(OutreachDraft.business_id == business_id,
            OutreachDraft.lead_id == lead_id))
        lists = self.session.scalars(select(LeadList).where(LeadList.business_id == business_id)
            .order_by(func.lower(LeadList.name))).all()
        selected = set(self.session.scalars(select(LeadListItem.list_id).where(
            LeadListItem.business_id == business_id, LeadListItem.lead_id == lead_id)).all())
        from ayo.merchant_work import TaskService
        tasks = [task for task in TaskService(self.session).list(user_id, business_id) if task.source_lead_id == lead_id]
        business = self.session.get(Business, business_id)
        def date(value):
            return datetime.fromtimestamp(value, ZoneInfo(business.timezone)).strftime('%d %b %Y · %H:%M %Z')
        history = []
        for event in events:
            if event.to_status != 'qualified':
                continue
            try:
                evidence = PipelineEvidence.model_validate_json(event.evidence_json)
            except (ValidationError, ValueError):
                continue
            if evidence.kind == 'qualification' and evidence.business_id == business_id:
                history.append({'note': evidence.note, 'reference': evidence.reference, 'date': date(event.created_at)})
        user = self.session.get(User, user_id)
        return {'lead': self._view(row, events), 'notes': [{'body': note.body, 'date': date(note.created_at)} for note in notes],
            'draft': draft, 'lists': lists, 'selected_lists': selected, 'followups': tasks, 'qualification_history': history,
            'can_write': member.role in WRITE_ROLES and user.email_verified_at is not None}

    def create_list(self, user_id, business_id, *, name, description=''):
        self._member(user_id, business_id, write=True)
        row = LeadList(business_id=business_id, name=text_input(name, 'list name', 120),
            description=text_input(description, 'description', 1000, required=False), actor_user_id=user_id)
        self.session.add(row)
        self.session.flush()
        self._audit('lead.list_created', user_id, business_id, 'lead_list', row.id)
        return row

    def add_to_list(self, user_id, business_id, list_id, lead_id):
        self._member(user_id, business_id, write=True)
        self._list(business_id, list_id)
        self._lead(business_id, lead_id, lock=True)
        row = self.session.get(LeadListItem, (business_id, list_id, lead_id))
        if row is None:
            row = LeadListItem(business_id=business_id, list_id=list_id, lead_id=lead_id, actor_user_id=user_id)
            self.session.add(row)
            self._audit('lead.list_item_added', user_id, business_id, 'lead', lead_id)
        return row

    def remove_from_list(self, user_id, business_id, list_id, lead_id):
        self._member(user_id, business_id, write=True)
        self._list(business_id, list_id)
        self._lead(business_id, lead_id, lock=True)
        row = self.session.get(LeadListItem, (business_id, list_id, lead_id))
        if row is None:
            raise IdentityError('not_found', 'Saved list item not found.', 404)
        self.session.delete(row)
        self._audit('lead.list_item_removed', user_id, business_id, 'lead', lead_id)

    def add_note(self, user_id, business_id, lead_id, *, body):
        self._member(user_id, business_id, write=True)
        self._lead(business_id, lead_id)
        row = LeadNote(business_id=business_id, lead_id=lead_id, actor_user_id=user_id,
                       body=text_input(body, 'private note', 4000))
        self.session.add(row)
        self.session.flush()
        self._audit('lead.note_added', user_id, business_id, 'lead_note', row.id)
        return row

    def save_draft(self, user_id, business_id, lead_id, *, offer, source_url, source_excerpt,
                   subject='', body='', draft_id=None, version=None):
        self._member(user_id, business_id, write=True)
        lead = self._lead(business_id, lead_id, lock=True)
        existing = self.session.scalar(select(OutreachDraft).where(OutreachDraft.business_id == business_id,
            OutreachDraft.lead_id == lead_id).with_for_update().execution_options(populate_existing=True))
        if draft_id is not None and (existing is None or existing.id != draft_id):
            raise IdentityError('not_found', 'Draft not found.', 404)
        if existing and (draft_id is None or version != existing.version):
            raise IdentityError('draft_conflict', 'This draft changed. Reopen it before saving your edits.', 409)
        evidence = self._evidence(lead)
        offer = text_input(offer, 'offer', 1000)
        excerpt = text_input(source_excerpt, 'source excerpt', 2000)
        source_url = text_input(source_url, 'source URL', 2048)
        # Exact stored URL and a literal excerpt; a browser cannot invent a citation.
        stored_excerpt, source_id = evidence.get('source_excerpt'), evidence.get('source_id')
        if (source_url != evidence.get('source_url') or not isinstance(stored_excerpt, str)
                or excerpt not in stored_excerpt or not isinstance(source_id, str) or not 1 <= len(source_id) <= 160):
            raise IdentityError('source_mismatch', 'Use the saved discovery source URL and an exact excerpt from its evidence.', 400)
        try:
            normalize_public_url(source_url)
        except SiteInputError:
            raise IdentityError('source_mismatch', 'The discovery source URL is unavailable for drafting.', 400) from None
        subject = text_input(subject, 'subject', 200, required=False)
        body = text_input(body, 'draft', 8000, required=False)
        template = (f'Hello,\n\nI found your business through this public source: {source_url}\n'
                    f'The source says: “{excerpt}”\n\nMy offer: {offer}\n\n'
                    'Would you be open to discussing whether this is relevant to your business?\n\nBest regards')
        origin = 'merchant_edited' if body else 'deterministic_template'
        values = {'offer': offer, 'source_url': source_url, 'source_excerpt': excerpt,
                  'source_id': source_id, 'subject': subject or 'A business introduction',
                  'body': body or template, 'provenance': origin, 'actor_user_id': user_id,
                  'updated_at': time.time()}
        if existing is None:
            existing = OutreachDraft(business_id=business_id, lead_id=lead_id, version=1, **values)
            self.session.add(existing)
        else:
            changed = self.session.execute(update(OutreachDraft).where(OutreachDraft.business_id == business_id,
                OutreachDraft.lead_id == lead_id, OutreachDraft.id == draft_id,
                OutreachDraft.version == version).values(**values, version=version + 1)
                .execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                raise IdentityError('draft_conflict', 'This draft changed. Reopen it before saving your edits.', 409)
            self.session.refresh(existing)
        self.session.flush()
        self._audit('lead.draft_saved', user_id, business_id, 'outreach_draft', existing.id)
        return existing

    def add_followup(self, user_id, business_id, lead_id, *, title, description='', due_date=None):
        self._member(user_id, business_id, write=True)
        self._lead(business_id, lead_id)
        from ayo.merchant_work import TaskService
        return TaskService(self.session).create(user_id, business_id, title=title,
            description=description, due_date=due_date, source_lead_id=lead_id)
