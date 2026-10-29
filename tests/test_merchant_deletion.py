"""Local removal covers the new private records and encrypted research payloads."""
import secrets

import pytest
from sqlalchemy import func, select

from ayo import app as mod
from ayo.account_deletion import remove_account
from ayo.account_management import change_password
from ayo.assistant import AssistantService
from ayo.assistant_models import AssistantConversation, AssistantMessage, AssistantToolRun
from ayo.identity import IdentityError, IdentityService
from ayo.jobs import enqueue
from ayo.lead_management import LeadManagementService
from ayo.lead_models import LeadList, LeadListItem, LeadNote, OutreachDraft
from ayo.merchant_models import BusinessProfile, Task
from ayo.merchant_work import ProfileService
from ayo.models import AuditEvent, Business, FoundingGrant, Lead, Membership, ResearchJob, ResearchReportRecord, User
from test_lead_management import draft_data, setup_prospects
from test_platform_flow import platform  # noqa: F401


def populate(platform):
    lead_id, business_id, user_id = setup_prospects(platform)
    data = draft_data(platform, lead_id)
    with platform.factory() as session:
        service = LeadManagementService(session)
        saved_list = service.create_list(user_id, business_id, name='Private shortlist')
        service.add_to_list(user_id, business_id, saved_list.id, lead_id)
        service.add_note(user_id, business_id, lead_id, body='Private merchant review note.')
        service.save_draft(user_id, business_id, lead_id, **data)
        service.add_followup(user_id, business_id, lead_id, title='Review source')
        ProfileService(session).save(user_id, business_id, name='Private business', country='GH', offer='Private offer')
        assistant = AssistantService(session)
        conversation = assistant.create(user_id, business_id, secrets.token_urlsafe(24))
        assistant.begin(user_id, business_id, conversation.id, secrets.token_urlsafe(24), 'Review my tasks and leads')
        session.commit()
    return lead_id, business_id, user_id


def test_exclusive_account_removal_erases_new_records_and_linked_job_payload(platform):
    _, business_id, user_id = populate(platform)
    with platform.factory() as session:
        report = ResearchReportRecord(business_id=business_id, owner_user_id=user_id,
            title='Synthetic saved report', status='PARTIAL', report_json='{}')
        session.add(report)
        session.flush()
        job = enqueue(session, mod.fernet, url='https://fixture-business.org/', country='GH',
            business_name='Synthetic private identity', anonymous_id=secrets.token_urlsafe(32))
        job.report_id = report.id
        session.commit()
        job_id = job.id
        slot = session.scalar(select(FoundingGrant.slot).where(FoundingGrant.user_id == user_id))
        remove_account(session, user_id, 'FixturePassword123!', 'DELETE')
        session.commit()
    with platform.factory() as session:
        assert session.get(ResearchJob, job_id) is None
        for model in (AssistantToolRun, AssistantMessage, AssistantConversation, BusinessProfile, Task,
                      LeadListItem, LeadList, LeadNote, OutreachDraft, Lead, ResearchReportRecord, Business):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.scalar(select(AuditEvent).where(AuditEvent.resource_type == 'research_job', AuditEvent.resource_id == job_id)) is None
        assert session.get(User, user_id).disabled_at is not None
        assert session.scalar(select(FoundingGrant.slot).where(FoundingGrant.user_id == user_id)) == slot


def test_shared_business_work_retained_anonymized_and_private_conversations_removed(platform):
    _, business_id, user_id = populate(platform)
    with platform.factory() as session:
        second = IdentityService(session).register('second-owner@example.org', 'FixturePassword123!', 'Separate', 'NG')
        session.add(Membership(user_id=second.user.id, business_id=business_id, role='owner'))
        session.commit()
        remove_account(session, user_id, 'FixturePassword123!', 'DELETE')
        session.commit()
    with platform.factory() as session:
        assert session.get(Business, business_id) is not None
        assert session.scalar(select(func.count()).select_from(AssistantConversation)) == 0
        assert session.scalar(select(Task)).created_by is None
        assert session.get(BusinessProfile, business_id).updated_by is None
        assert session.scalar(select(LeadNote)).actor_user_id is None
        assert session.scalar(select(OutreachDraft)).actor_user_id is None
        assert session.scalar(select(LeadListItem)).actor_user_id is None


def test_failed_ownership_transfer_does_not_delete_personal_conversations(platform):
    _, business_id, user_id = populate(platform)
    with platform.factory() as session:
        second = IdentityService(session).register('shared-editor@example.org', 'FixturePassword123!', 'Separate', 'NG')
        session.add(Membership(user_id=second.user.id, business_id=business_id, role='editor'))
        session.commit()
        with pytest.raises(IdentityError, match='Transfer shared-workspace ownership'):
            remove_account(session, user_id, 'FixturePassword123!', 'DELETE')
        session.commit()  # No deletion may precede the ownership precondition.
        assert session.scalar(select(func.count()).select_from(AssistantConversation)) == 1
        assert session.get(User, user_id).disabled_at is None


def test_cached_account_removal_rejects_superseded_password(platform):
    _, _, user_id = populate(platform)
    with platform.factory() as stale, platform.factory() as fresh:
        cached = stale.get(User, user_id)
        stale.commit()
        change_password(fresh, user_id, 'FixturePassword123!', 'RotatedBeforeRemoval!')
        fresh.commit()
        with pytest.raises(IdentityError, match='Enter your password'):
            remove_account(stale, cached.id, 'FixturePassword123!', 'DELETE')
        stale.rollback()
        assert stale.get(User, user_id).disabled_at is None
