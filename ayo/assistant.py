"""Bounded deterministic read plans around the existing source-bound intelligence.

Questions and retrieved records never supply executable code, tool permissions,
business IDs or model/provider routing. History is retained for the user but is
deliberately not sent to providers in this slice.
"""
from datetime import datetime, timezone
import json
import re
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select, update

from ayo.assistant_models import AssistantConversation, AssistantMessage, AssistantToolRun
from ayo.identity import IdentityError, IdentityService, token_hash
from ayo.intelligence import IntelligenceContext, IntelligenceError, IntelligenceResult, SourceEvidence, validate_analysis
from ayo.leads import LeadCandidate
from ayo.merchant_models import BusinessProfile, Task
from ayo.models import Business, Lead, ResearchReportRecord
from ayo.research import ResearchReport

ToolName = Literal['business.profile', 'research.saved', 'opportunities.list', 'leads.saved', 'work.tasks']
TOOL_NAMES = ('business.profile', 'research.saved', 'opportunities.list', 'leads.saved', 'work.tasks')
MAX_MESSAGES = 100
MAX_CONVERSATIONS = 100
PENDING_SECONDS = 120


class ToolModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class ToolCapability(ToolModel):
    name: ToolName
    version: Literal[1] = 1
    read_only: Literal[True] = True
    available: bool
    reason: str = Field(max_length=250)
    record_limit: Literal[3] = 3


class ToolStep(ToolModel):
    name: ToolName
    version: Literal[1] = 1
    reason: str = Field(min_length=1, max_length=160)


class ToolPlan(ToolModel):
    version: Literal['read-plan-v1'] = 'read-plan-v1'
    intent: Literal['workspace_overview', 'business_context', 'research', 'opportunities', 'leads', 'work']
    steps: tuple[ToolStep, ...] = Field(max_length=5)
    external_actions: Literal[False] = False


class ToolItem(ToolModel):
    id: str = Field(max_length=160)
    title: str = Field(max_length=250)
    detail: str = Field(max_length=1000)
    classification: Literal['WORKSPACE_RECORD', 'OWNER_PROVIDED_UNVERIFIED', 'PUBLIC_WEB', 'INFERRED']
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=6)


class ToolResult(ToolModel):
    name: ToolName
    version: Literal[1] = 1
    status: Literal['completed', 'partial', 'empty']
    items: tuple[ToolItem, ...] = Field(max_length=3)
    evidence: tuple[SourceEvidence, ...] = Field(default=(), max_length=6)
    more_available: bool = False
    limitations: tuple[str, ...] = Field(default=(), max_length=4)


def _dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc)


def _source_id(kind, *parts):
    return kind + '-' + token_hash(':'.join(parts))[:40]


def _key(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', value):
        raise IdentityError('invalid_request_id', 'Reload this conversation before sending your question.', 400)
    return token_hash(value)


def _question(value):
    if not isinstance(value, str):
        raise IdentityError('invalid_question', 'Enter a question of 1–1000 characters.', 400)
    value = value.replace('\r\n', '\n').strip()
    if not 1 <= len(value) <= 1000 or len(value.encode('utf-8')) > 4000 or any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise IdentityError('invalid_question', 'Enter a question of 1–1000 characters.', 400)
    return value


class AssistantService:
    def __init__(self, session, clock=time.time):
        self.session, self.clock = session, clock

    def _member(self, user_id, business_id, *, write=False):
        identity = IdentityService(self.session, self.clock)
        identity.require_membership(user_id, business_id)
        if write:
            # These are private notes/read requests, so analysts can use them.
            # Workspace writes and external actions retain their own role gates.
            identity.require_verified_user(user_id)
        return identity

    def list(self, user_id, business_id):
        self._member(user_id, business_id)
        return self.session.scalars(select(AssistantConversation).where(
            AssistantConversation.business_id == business_id, AssistantConversation.user_id == user_id,
        ).order_by(AssistantConversation.updated_at.desc()).limit(50)).all()

    def get(self, user_id, business_id, conversation_id):
        self._member(user_id, business_id)
        row = self.session.scalar(select(AssistantConversation).where(
            AssistantConversation.id == conversation_id, AssistantConversation.business_id == business_id,
            AssistantConversation.user_id == user_id))
        if row is None:
            raise IdentityError('conversation_unavailable', 'Conversation not found.', 404)
        return row

    def messages(self, user_id, business_id, conversation_id):
        self.get(user_id, business_id, conversation_id)
        return self.session.scalars(select(AssistantMessage).where(
            AssistantMessage.conversation_id == conversation_id, AssistantMessage.business_id == business_id,
            AssistantMessage.user_id == user_id,
        ).order_by(AssistantMessage.created_at, AssistantMessage.role.desc()).limit(MAX_MESSAGES)).all()

    def create(self, user_id, business_id, request_id, title='New conversation'):
        identity = self._member(user_id, business_id, write=True)
        key = _key(request_id)
        # Serialize private conversation creation per user on both supported DBs.
        from ayo.models import User
        self.session.execute(update(User).where(User.id == user_id).values(id=User.id))
        existing = self.session.scalar(select(AssistantConversation).where(
            AssistantConversation.user_id == user_id, AssistantConversation.business_id == business_id,
            AssistantConversation.creation_key == key))
        if existing:
            return existing
        title = title.strip() or 'New conversation'
        if len(title) > 160 or any(ord(c) < 32 for c in title):
            raise IdentityError('invalid_title', 'Use a conversation title of at most 160 characters.', 400)
        identity._attempt('assistant-conversation', str(user_id), limit=10, window=3600)
        count = self.session.scalar(select(func.count()).select_from(AssistantConversation).where(
            AssistantConversation.user_id == user_id))
        if count >= MAX_CONVERSATIONS:
            raise IdentityError('conversation_limit', 'The private conversation record limit has been reached.', 429)
        row = AssistantConversation(user_id=user_id, business_id=business_id, creation_key=key,
                                    title=title, created_at=self.clock(), updated_at=self.clock())
        self.session.add(row)
        self.session.flush()
        identity.audit('assistant.conversation_created', user_id=user_id, business_id=business_id,
                       resource_type='assistant_conversation', resource_id=row.id)
        return row

    def expire_pending(self, user_id, business_id, conversation_id):
        conversation = self.get(user_id, business_id, conversation_id)
        if conversation.active_request:
            self.session.execute(update(AssistantConversation).where(
                AssistantConversation.id == conversation_id).values(updated_at=AssistantConversation.updated_at))
            self.session.refresh(conversation)
            stale = self.session.execute(update(AssistantMessage).where(
                AssistantMessage.conversation_id == conversation_id,
                AssistantMessage.request_key == conversation.active_request,
                AssistantMessage.role == 'assistant', AssistantMessage.status == 'pending',
                AssistantMessage.created_at < self.clock() - PENDING_SECONDS,
            ).values(status='uncertain', error_code='analysis_interrupted', finished_at=self.clock())
                .returning(AssistantMessage.request_key)).scalar_one_or_none()
            if stale:
                self.session.execute(update(AssistantConversation).where(
                    AssistantConversation.id == conversation_id, AssistantConversation.active_request == stale,
                ).values(active_request=None))
                self.session.expire(conversation)

    def begin(self, user_id, business_id, conversation_id, request_id, question):
        identity = self._member(user_id, business_id, write=True)
        self.get(user_id, business_id, conversation_id)
        key, question = _key(request_id), _question(question)
        # A write lock serializes checks, counters and the single-flight fence.
        self.session.execute(update(AssistantConversation).where(
            AssistantConversation.id == conversation_id, AssistantConversation.user_id == user_id,
            AssistantConversation.business_id == business_id).values(updated_at=AssistantConversation.updated_at))
        existing = self.session.scalar(select(AssistantMessage).where(
            AssistantMessage.conversation_id == conversation_id, AssistantMessage.request_key == key,
            AssistantMessage.role == 'assistant'))
        if existing:
            original = self.session.scalar(select(AssistantMessage).where(
                AssistantMessage.conversation_id == conversation_id, AssistantMessage.request_key == key,
                AssistantMessage.role == 'user'))
            if original.content != question:
                raise IdentityError('request_conflict', 'This request identifier already belongs to another question.', 409)
            return existing, False
        claimed = self.session.execute(update(AssistantConversation).where(
            AssistantConversation.id == conversation_id, AssistantConversation.active_request.is_(None),
        ).values(active_request=key, updated_at=self.clock()).returning(AssistantConversation.id)).scalar_one_or_none()
        if claimed is None:
            raise IdentityError('conversation_busy', 'A question is already being processed. Reopen this conversation for its status.', 409)
        identity._attempt('assistant-message', str(user_id), limit=20, window=3600)
        count = self.session.scalar(select(func.count()).select_from(AssistantMessage).where(
            AssistantMessage.conversation_id == conversation_id))
        if count >= MAX_MESSAGES:
            raise IdentityError('message_limit', 'Start a new conversation to continue. This conversation has reached its record limit.', 429)
        plan, results = self.read_plan(user_id, business_id, question)
        now = self.clock()
        self.session.add(AssistantMessage(conversation_id=conversation_id, business_id=business_id,
            user_id=user_id, request_key=key, role='user', content=question, status='completed', created_at=now))
        message = AssistantMessage(conversation_id=conversation_id, business_id=business_id,
            user_id=user_id, request_key=key, role='assistant', status='pending',
            plan_json=plan.model_dump_json(), created_at=now + 0.000001)
        self.session.add(message)
        self.session.flush()
        for result in results:
            self.session.add(AssistantToolRun(message_id=message.id, business_id=business_id, user_id=user_id,
                tool_name=result.name, version=result.version, status=result.status, result_json=result.model_dump_json()))
        identity.audit('assistant.question_recorded', user_id=user_id, business_id=business_id,
                       resource_type='assistant_message', resource_id=message.id,
                       details={'plan_version': plan.version, 'tools': [step.name for step in plan.steps]})
        return message, True

    def _reports(self, business_id):
        rows = self.session.scalars(select(ResearchReportRecord).where(
            ResearchReportRecord.business_id == business_id,
            ResearchReportRecord.status.in_(['PARTIAL', 'SUCCEEDED']),
        ).order_by(ResearchReportRecord.created_at.desc()).limit(4)).all()
        valid = []
        for row in rows[:3]:
            try:
                valid.append((row, ResearchReport.model_validate_json(row.report_json)))
            except ValidationError:
                continue
        return valid, len(rows) > 3, len(valid) != min(len(rows), 3)

    def capabilities(self, user_id, business_id):
        self._member(user_id, business_id)
        reports, _, _ = self._reports(business_id)
        available = {'business.profile': True, 'research.saved': bool(reports),
            'opportunities.list': any(report.opportunities or (report.analysis and report.analysis.recommendations)
                                      for _, report in reports),
            'leads.saved': self.session.scalar(select(Lead.id).where(Lead.business_id == business_id).limit(1)) is not None,
            'work.tasks': self.session.scalar(select(Task.id).where(Task.business_id == business_id).limit(1)) is not None}
        return tuple(ToolCapability(name=name, available=available[name],
            reason='Read saved workspace records.' if available[name] else 'No usable saved records in the bounded workspace view.') for name in TOOL_NAMES)

    def read_plan(self, user_id, business_id, question):
        self._member(user_id, business_id)
        # Only the merchant's current question selects among this exact allowlist.
        # Source text and generated model text are never used for tool selection.
        routing = ((r'\b(task|tasks|work|todo|to-do)\b', 'work', 'work.tasks'),
                   (r'\b(lead|leads|prospect|prospects)\b', 'leads', 'leads.saved'),
                   (r'\b(opportunity|opportunities|priority|priorities)\b', 'opportunities', 'opportunities.list'),
                   (r'\b(research|report|reports|website|sources)\b', 'research', 'research.saved'),
                   (r'\b(profile|offer|audience|goal|goals)\b', 'business_context', 'business.profile'))
        selected = [(intent, name) for pattern, intent, name in routing if re.search(pattern, question, re.I)]
        capabilities = self.capabilities(user_id, business_id)
        available = {item.name for item in capabilities if item.available}
        wanted = {name for _, name in selected} if selected else set(TOOL_NAMES)
        wanted.add('business.profile')
        steps = tuple(ToolStep(name=name, reason='Read relevant saved records within the current workspace.')
                      for name in TOOL_NAMES if name in wanted and name in available)
        plan = ToolPlan(intent=selected[0][0] if selected else 'workspace_overview', steps=steps)
        results = tuple(self.run_tool(user_id, business_id, step) for step in plan.steps)
        return plan, results

    def run_tool(self, user_id, business_id, step):
        self._member(user_id, business_id)
        step = ToolStep.model_validate(step.model_dump() if isinstance(step, ToolStep) else step)
        items, sources, limitations, more, partial = [], {}, [], False, False
        business = self.session.get(Business, business_id)
        if step.name == 'business.profile':
            profile = self.session.get(BusinessProfile, business_id)
            detail = f'Workspace name: {business.name}. Selected market: {business.country}. Currency: {business.currency}.'
            if profile:
                detail += ' ' + ' '.join(f'{name}: {getattr(profile, name)[:180]}.' for name in
                                        ('offer', 'products', 'audience', 'location', 'goals') if getattr(profile, name))
            detail = detail[:1000]
            item = ToolItem(id=business_id, title=business.name, detail=detail, classification='OWNER_PROVIDED_UNVERIFIED')
            items.append(item)
            evidence = SourceEvidence(id=_source_id('profile', business_id), business_id=business_id,
                url='workspace:business-profile', excerpt=detail, source_kind='OWNER_PROVIDED_UNVERIFIED',
                observed_at=_timestamp(profile.updated_at if profile else business.created_at))
            sources[evidence.id] = evidence
            limitations.append('Profile facts are owner-provided and have not been independently verified.')
        elif step.name in {'research.saved', 'opportunities.list'}:
            reports, more, partial = self._reports(business_id)
            for row, report in reports:
                if step.name == 'research.saved':
                    items.append(ToolItem(id=row.id, title=row.title, detail=f'Saved {row.status.lower()} research. Inspect the report for coverage and source dates.', classification='WORKSPACE_RECORD'))
                    used = report.source_documents[:2]
                else:
                    used_ids = set()
                    candidates = [(str(index), item.title, item.description, item.evidence_ids)
                                  for index, item in enumerate(report.opportunities)]
                    if report.analysis:
                        candidates.extend(('ai-' + str(index), item.text[:160], item.text, item.evidence_ids)
                                          for index, item in enumerate(report.analysis.recommendations))
                    for locator, title, detail, evidence_ids in candidates:
                        if len(items) >= 3:
                            more = True
                            break
                        namespaced = tuple(_source_id('report', row.id, source_id) for source_id in evidence_ids)
                        if len(set(sources) | {_source_id('report', row.id, source_id) for source_id in used_ids} | set(namespaced)) > 6:
                            more, partial = True, True
                            continue
                        items.append(ToolItem(id=row.id + ':' + locator, title=title,
                            detail=detail, classification='INFERRED', evidence_ids=namespaced))
                        used_ids.update(evidence_ids)
                    used = tuple(source for source in report.source_documents if source.id in used_ids)
                for source in used:
                    evidence = SourceEvidence(id=_source_id('report', row.id, source.id), business_id=business_id,
                        url=source.url, excerpt=source.excerpt, source_kind='PUBLIC_WEB', observed_at=source.retrieved_at)
                    sources[evidence.id] = evidence
            limitations.append('At most three recent reports are retrieved. Sources may be outdated.')
            if step.name == 'opportunities.list':
                limitations.append('Saved opportunities are proposals and inferences, not verified outcomes.')
                limitations.append('The read retains at most three proposals supported by at most six source excerpts.')
            else:
                limitations.append('Research reads retain at most two source excerpts per report.')
        elif step.name == 'leads.saved':
            from ayo.lead_management import LeadManagementService
            lead_service = LeadManagementService(self.session)
            rows = self.session.scalars(select(Lead).where(Lead.business_id == business_id)
                .order_by(Lead.created_at.desc()).limit(4)).all()
            more = len(rows) > 3
            for row in rows[:3]:
                try:
                    lead = LeadCandidate.model_validate_json(row.evidence_json)
                except ValidationError:
                    partial = True
                    continue
                view = lead_service._view(row)
                items.append(ToolItem(id=row.id, title=row.name,
                    detail=f"Saved prospect; evidence-backed recorded stage: {view['status']}. Stage provenance: {view['status_provenance']}. Fit is not buyer intent or a sale.",
                    classification='WORKSPACE_RECORD'))
                evidence = SourceEvidence(id=_source_id('lead', row.id, lead.source_id), business_id=business_id,
                    url=lead.source_url, excerpt=lead.source_excerpt[:600], source_kind='PUBLIC_WEB', observed_at=lead.discovered_at)
                sources[evidence.id] = evidence
            limitations.append('Prospects are not customers. Public contact information is not marketing consent.')
        elif step.name == 'work.tasks':
            rows = self.session.scalars(select(Task).where(Task.business_id == business_id)
                .order_by(Task.updated_at.desc()).limit(4)).all()
            more = len(rows) > 3
            for row in rows[:3]:
                detail = f'Merchant-recorded task: {row.title}. Status: {row.status}. {row.description[:500]}'
                items.append(ToolItem(id=row.id, title=row.title, detail=detail[:1000], classification='OWNER_PROVIDED_UNVERIFIED'))
                evidence = SourceEvidence(id=_source_id('task', row.id), business_id=business_id,
                    url='workspace:task:' + row.id, excerpt=detail[:1000], source_kind='OWNER_PROVIDED_UNVERIFIED', observed_at=_timestamp(row.updated_at))
                sources[evidence.id] = evidence
            limitations.append('Task completion is merchant-recorded; it does not prove a provider action or commercial outcome.')
        return ToolResult(name=step.name, status='partial' if partial else 'completed' if items else 'empty',
            items=tuple(items[:3]), evidence=tuple(sources.values())[:6], more_available=more,
            limitations=tuple(limitations))

    def tool_runs(self, user_id, business_id, message):
        self.get(user_id, business_id, message.conversation_id)
        if message.business_id != business_id or message.user_id != user_id:
            raise IdentityError('conversation_unavailable', 'Conversation not found.', 404)
        return self.session.scalars(select(AssistantToolRun).where(
            AssistantToolRun.message_id == message.id, AssistantToolRun.business_id == business_id,
            AssistantToolRun.user_id == user_id).order_by(AssistantToolRun.tool_name).limit(5)).all()

    def inference_context(self, user_id, business_id, message):
        question = self.session.scalar(select(AssistantMessage.content).where(
            AssistantMessage.conversation_id == message.conversation_id, AssistantMessage.request_key == message.request_key,
            AssistantMessage.role == 'user', AssistantMessage.business_id == business_id,
            AssistantMessage.user_id == user_id))
        evidence = {}
        for run in self.tool_runs(user_id, business_id, message):
            result = ToolResult.model_validate_json(run.result_json)
            for source in result.evidence:
                if source.business_id != business_id:
                    raise IntelligenceError('unsupported_citation', 'Retrieved context does not match this workspace.')
                evidence[source.id] = source
        # No earlier questions or generated answers are included as evidence.
        business = self.session.get(Business, business_id)
        return IntelligenceContext(business_id=business_id, actor_business_id=business_id,
            country=business.country, question=question, evidence=tuple(evidence.values())[:20])

    def finish(self, user_id, business_id, message_id, *, result=None, error_code=None, uncertain=False, failed=False):
        message = self.session.get(AssistantMessage, message_id)
        if message is None:
            raise IdentityError('conversation_unavailable', 'Conversation not found.', 404)
        self.get(user_id, business_id, message.conversation_id)
        if message.business_id != business_id or message.user_id != user_id or message.role != 'assistant':
            raise IdentityError('conversation_unavailable', 'Conversation not found.', 404)
        payload = {}
        if result is not None:
            context = self.inference_context(user_id, business_id, message)
            result = IntelligenceResult.model_validate(result.model_dump())
            validate_analysis(result.model_dump(include={'claims', 'recommendations', 'limitations'}), context)
            payload = result.model_dump(mode='json')
        status = 'completed' if result is not None else 'uncertain' if uncertain else 'failed' if failed else 'blocked'
        # Commit a result only while this exact request still owns the fence.
        owned = self.session.execute(update(AssistantConversation).where(
            AssistantConversation.id == message.conversation_id,
            AssistantConversation.active_request == message.request_key,
        ).values(active_request=None, updated_at=self.clock()).returning(AssistantConversation.id)).scalar_one_or_none()
        if owned:
            self.session.execute(update(AssistantMessage).where(
                AssistantMessage.id == message_id, AssistantMessage.status == 'pending',
            ).values(status=status, result_json=_dump(payload), error_code=error_code, finished_at=self.clock()))
            IdentityService(self.session, self.clock).audit('assistant.analysis_recorded', user_id=user_id,
                business_id=business_id, resource_type='assistant_message', resource_id=message_id,
                details={'status': status, 'error_code': error_code})
        return owned is not None
