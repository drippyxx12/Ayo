"""Local account-data removal with shared-workspace ownership protection."""
import secrets
import time
from sqlalchemy import delete, func, select, update
from ayo.identity import IdentityError, IdentityService, password_hash, password_verify, token_hash
from ayo.models import (AuditEvent, AuthAttempt, AuthSession, Business, IdentityToken, IntelligenceRun,
                        Lead, LeadEvent, MailOutbox, Membership, ReportClaim, ResearchJob,
                        ResearchReportRecord, Shop, Snapshot, User)
from ayo.merchant_models import BusinessProfile, Task
from ayo.lead_models import LeadList, LeadListItem, LeadNote, OutreachDraft
from ayo.assistant_models import AssistantConversation, AssistantMessage, AssistantToolRun


def remove_account(session, user_id, password, confirmation):
    user = IdentityService(session).lock_user(user_id)
    if not user or user.disabled_at is not None:
        raise IdentityError('authentication_required', 'Sign in required.', 401)
    if confirmation != 'DELETE' or not password_verify(password, user.password_hash):
        raise IdentityError('confirmation_required', 'Enter your password and DELETE to confirm local account removal.', 403)
    owned = session.scalars(select(Membership).where(Membership.user_id == user_id, Membership.role == 'owner')
                            .order_by(Membership.business_id)).all()
    exclusive = []
    for membership in owned:
        session.scalar(select(Business).where(Business.id == membership.business_id).with_for_update())
        others = session.scalar(select(func.count()).select_from(Membership).where(
            Membership.business_id == membership.business_id, Membership.user_id != user_id))
        other_owners = session.scalar(select(func.count()).select_from(Membership).where(
            Membership.business_id == membership.business_id, Membership.user_id != user_id, Membership.role == 'owner'))
        if others and not other_owners:
            raise IdentityError('ownership_transfer_required', 'Transfer shared-workspace ownership before removing this account.', 409)
        if not others:
            exclusive.append(membership.business_id)
    # Validate ownership transfers before making any deletion. Conversations are
    # personal to an account even in a shared business.
    for model in (AssistantToolRun, AssistantMessage, AssistantConversation):
        session.execute(delete(model).where(model.user_id == user_id))
    if exclusive:
        reports = select(ResearchReportRecord.id).where(ResearchReportRecord.business_id.in_(exclusive))
        jobs = select(ResearchJob.id).where(ResearchJob.report_id.in_(reports))
        session.execute(delete(AuditEvent).where(AuditEvent.resource_type == 'research_job', AuditEvent.resource_id.in_(jobs)))
        session.execute(delete(ResearchJob).where(ResearchJob.report_id.in_(reports)))
        session.execute(delete(ReportClaim).where(ReportClaim.report_id.in_(reports)))
        for model in (Task, BusinessProfile, OutreachDraft, LeadNote, LeadListItem, LeadList,
                      LeadEvent, Lead, IntelligenceRun, ResearchReportRecord, Membership):
            session.execute(delete(model).where(model.business_id.in_(exclusive)))
        session.execute(update(AuditEvent).where(AuditEvent.business_id.in_(exclusive)).values(business_id=None))
        session.execute(delete(Business).where(Business.id.in_(exclusive)))
    for model in (AuthSession, IdentityToken, MailOutbox, Shop, Snapshot, Membership):
        session.execute(delete(model).where(model.user_id == user_id))
    # Shared business work remains with its workspace, with account attribution removed.
    session.execute(update(BusinessProfile).where(BusinessProfile.updated_by == user_id).values(updated_by=None))
    session.execute(update(Task).where(Task.created_by == user_id).values(created_by=None))
    for model in (LeadList, LeadListItem, LeadNote, OutreachDraft):
        session.execute(update(model).where(model.actor_user_id == user_id).values(actor_user_id=None))
    for purpose in ('login-account', 'reset-account'):
        session.execute(delete(AuthAttempt).where(AuthAttempt.key_hash == token_hash(purpose + '\0' + user.email)))
    # Keep the non-reusable founding ordinal attached to a disabled pseudonymous
    # ledger row; remove the real email and password rather than recycle slots.
    user.email = 'deleted-' + secrets.token_hex(20) + '@account.invalid'
    user.password_hash = password_hash(secrets.token_urlsafe(48))
    user.email_verified_at, user.disabled_at = None, time.time()
    IdentityService(session).audit('account.local_data_removed', resource_type='user', resource_id=user_id)
