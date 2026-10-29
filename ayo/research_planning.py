"""Reviewed, source-linked internal work from an immutable saved report.

No model/network request, external execution, invented priority or outcome.
Task identities are stable across repeat reviews and different team members.
"""
import hashlib
import json
import re
import time

from sqlalchemy import select

from ayo.identity import IdentityError, IdentityService, token_hash
from ayo.merchant_models import Task
from ayo.models import Business, Membership
from ayo.research_workspace import ResearchWorkspace, report_freshness


class ResearchPlanning:
    def __init__(self, session, clock=time.time):
        self.session, self.clock = session, clock

    def review(self, user_id, business_id, report_id):
        row, report = ResearchWorkspace(self.session, self.clock)._load(user_id, business_id, report_id)
        digest = hashlib.sha256(row.report_json.encode()).hexdigest()
        sources = {source.id: source for source in report.source_documents}
        choices = []

        def append(title, text, ids, origin):
            # Recommendations with missing references never become executable work.
            if not ids or any(value not in sources for value in ids):
                return
            key = hashlib.sha256(json.dumps([title, text, list(ids), origin],
                ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()[:24]
            if any(item['key'] == key for item in choices):
                return
            task_id = token_hash('research-plan:v1:' + business_id + ':' + row.id + ':' + digest + ':' + key)
            task = self.session.get(Task, task_id)
            if task and (task.business_id != business_id or task.source_report_id != row.id):
                raise IdentityError('plan_unavailable', 'This plan is unavailable.', 409)
            choices.append({'key': key, 'title': title, 'text': text, 'origin': origin,
                'sources': [sources[value] for value in dict.fromkeys(ids)],
                'task_id': task_id, 'task': task})

        if report.analysis_status == 'completed' and report.analysis:
            for item in report.analysis.recommendations:
                append('Review: ' + item.text[:175], item.text, item.evidence_ids, 'AI proposal')
        for item in report.opportunities:
            append(item.title, item.description + '\n\nSuggested next step: ' + item.next_step,
                   item.evidence_ids, 'Research proposal')
        member = IdentityService(self.session).require_membership(user_id, business_id)
        from ayo.models import User
        user = self.session.get(User, user_id)
        return {'record': row, 'report': report, 'report_hash': digest, 'choices': choices[:8],
            'freshness': report_freshness(report, self.clock()),
            'owner_provided': report.origin == 'merchant_provided',
            'can_edit': bool(user.email_verified_at and member.role in {'owner', 'admin', 'editor'})}

    def create(self, user_id, business_id, report_id, *, report_hash, selected, reviewed):
        identity = IdentityService(self.session, self.clock)
        identity.require_verified_user(user_id)  # User lock also serializes account removal.
        identity.require_membership(user_id, business_id, roles={'owner', 'admin', 'editor'})
        self.session.scalar(select(Membership).where(Membership.user_id == user_id,
            Membership.business_id == business_id).with_for_update().execution_options(populate_existing=True))
        # Team members reviewing the same evidence serialize on the business row.
        self.session.scalar(select(Business).where(Business.id == business_id).with_for_update())
        identity.require_membership(user_id, business_id, roles={'owner', 'admin', 'editor'})
        plan = self.review(user_id, business_id, report_id)
        if reviewed is not True:
            raise IdentityError('plan_review_required', 'Review the selected work before creating tasks.', 400)
        if not isinstance(report_hash, str) or not re.fullmatch(r'[a-f0-9]{64}', report_hash):
            raise IdentityError('invalid_plan', 'Reload this report and review the plan again.', 400)
        if report_hash != plan['report_hash']:
            raise IdentityError('stale_plan', 'The saved evidence changed. Review the current report before planning.', 409)
        if (not isinstance(selected, (list, tuple)) or not 1 <= len(selected) <= 8
                or any(not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{24}', key) for key in selected)
                or len(set(selected)) != len(selected)):
            raise IdentityError('invalid_plan', 'Choose between one and eight listed next steps.', 400)
        available = {item['key']: item for item in plan['choices']}
        if set(selected) - available.keys():
            raise IdentityError('invalid_plan', 'Choose only next steps from this saved report.', 400)
        created, task_ids = [], []
        for key in selected:
            item = available[key]
            task_ids.append(item['task_id'])
            if item['task']:
                continue
            provenance = '\n'.join('Source ' + source.id + '\nCaptured: ' +
                source.retrieved_at.isoformat() + '\nSHA-256: ' + source.source_hash for source in item['sources'])
            description = (item['origin'] + ' · review required\n\n' + item['text'] +
                '\n\nSupporting saved inputs (full URLs and content remain in the linked report):\n' + provenance + '\n\nEvidence classification: ' +
                ('OWNER_PROVIDED_UNVERIFIED' if plan['owner_provided'] else 'PUBLIC_SOURCE_STATEMENTS_UNVERIFIED') +
                '\nNo external action has been performed. Completion will be merchant-recorded, not a verified business outcome.')
            now = self.clock()
            self.session.add(Task(id=item['task_id'], business_id=business_id,
                title=item['title'], description=description, source_report_id=report_id,
                created_by=user_id, status='open', created_at=now, updated_at=now, version=1))
            identity.audit('task.created', user_id=user_id, business_id=business_id,
                resource_type='task', resource_id=item['task_id'], details={'status': 'open',
                    'version': 1, 'source_report_id': report_id, 'origin': 'reviewed_research_plan',
                    'report_hash': report_hash, 'suggestion_key': key, 'external_action': False})
            created.append(item['task_id'])
        if created:
            identity.audit('research.plan_created', user_id=user_id, business_id=business_id,
                resource_type='research_report', resource_id=report_id,
                details={'report_hash': report_hash, 'task_ids': created, 'external_action': False})
        self.session.flush()
        return task_ids
