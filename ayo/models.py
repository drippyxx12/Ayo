"""Canonical relational models. Schema changes are applied through Alembic.

Public research, account identity, merchant membership and provider grants remain
separate authorization boundaries. Importing this module does not access a DB.
"""
import time

from sqlalchemy import BigInteger, CheckConstraint, Column, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from ayo.model_base import Base, opaque_id


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(300), nullable=False)
    joined = Column(Float, default=time.time, nullable=False)
    email_verified_at = Column(Float, nullable=True)
    disabled_at = Column(Float, nullable=True)


class Shop(Base):
    __tablename__ = 'shops'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True, index=True)
    domain = Column(String(255), unique=True, nullable=False)
    token_cipher = Column(Text, nullable=False)
    refresh_cipher = Column(Text, nullable=True)
    token_expires_at = Column(Float, nullable=True)
    refresh_expires_at = Column(Float, nullable=True)
    linked_at = Column(Float, default=time.time)
    granted_scopes = Column(Text, nullable=False, default='')


class Snapshot(Base):
    __tablename__ = 'snapshots'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True, index=True)
    domain = Column(String(255), nullable=False)
    currency = Column(String(10), nullable=False)
    shop_name = Column(String(255), nullable=False)
    product_count = Column(Integer, nullable=False)
    paid_order_count = Column(Integer, nullable=False)
    paid_order_value_minor = Column(BigInteger, nullable=False)
    paid_order_days = Column(Text, nullable=False)
    products_json = Column(Text, nullable=False)
    orders_limited = Column(Integer, nullable=False)
    products_limited = Column(Integer, nullable=False)
    synced_at = Column(Float, nullable=False)


class Business(Base):
    __tablename__ = 'businesses'
    __table_args__ = (
        CheckConstraint("country IN ('NG', 'GH')", name='ck_business_country'),
        CheckConstraint("(country = 'NG' AND currency = 'NGN') OR (country = 'GH' AND currency = 'GHS')", name='ck_business_currency'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    name = Column(String(250), nullable=False)
    country = Column(String(2), nullable=False)
    currency = Column(String(3), nullable=False)
    timezone = Column(String(50), nullable=False)
    created_at = Column(Float, default=time.time, nullable=False)


class Membership(Base):
    __tablename__ = 'memberships'
    __table_args__ = (CheckConstraint("role IN ('owner', 'admin', 'editor', 'analyst')", name='ck_membership_role'),)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, index=True)
    role = Column(String(20), nullable=False)


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    expires_at = Column(Float, nullable=False, index=True)
    revoked_at = Column(Float, nullable=True)
    csrf = Column(String(128), nullable=False)
    flash_json = Column(Text, nullable=True)
    oauth_state_hash = Column(String(64), nullable=True)
    oauth_shop = Column(String(255), nullable=True)
    oauth_started_at = Column(Float, nullable=True)


class IdentityToken(Base):
    __tablename__ = 'identity_tokens'
    __table_args__ = (CheckConstraint("purpose IN ('verify_email', 'reset_password')", name='ck_identity_token_purpose'),)
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    purpose = Column(String(30), nullable=False)
    expires_at = Column(Float, nullable=False, index=True)
    consumed_at = Column(Float, nullable=True)


class FoundingGrant(Base):
    __tablename__ = 'founding_grants'
    __table_args__ = (CheckConstraint('slot >= 1 AND slot <= 500', name='ck_founding_slot'),)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    slot = Column(Integer, nullable=False, unique=True)
    awarded_at = Column(Float, default=time.time, nullable=False)


class CohortCounter(Base):
    __tablename__ = 'cohort_counters'
    __table_args__ = (CheckConstraint('id = 1 AND next_slot >= 1 AND next_slot <= 501', name='ck_cohort_counter'),)
    id = Column(Integer, primary_key=True)
    next_slot = Column(Integer, nullable=False, default=1)


class AuthAttempt(Base):
    __tablename__ = 'auth_attempts'
    key_hash = Column(String(64), primary_key=True)
    window_started = Column(Float, nullable=False)
    count = Column(Integer, nullable=False, default=0)


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id = Column(Integer, primary_key=True)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='SET NULL'), nullable=True, index=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(128), nullable=True)
    details_json = Column(Text, nullable=False, default='{}')
    created_at = Column(Float, default=time.time, nullable=False, index=True)


class ResearchReportRecord(Base):
    __tablename__ = 'research_reports'
    id = Column(String(64), primary_key=True, default=opaque_id)
    owner_user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=True, index=True)
    title = Column(String(250), nullable=False)
    status = Column(String(40), nullable=False)
    target_url = Column(String(2048), nullable=True)
    country = Column(String(2), nullable=False, default='')
    report_json = Column(Text, nullable=False)
    created_at = Column(Float, default=time.time, nullable=False, index=True)
    expires_at = Column(Float, nullable=True, index=True)
    anonymous_session_hash = Column(String(64), nullable=True)


class ReportClaim(Base):
    __tablename__ = 'report_claims'
    token_hash = Column(String(64), primary_key=True)
    report_id = Column(String(64), ForeignKey('research_reports.id', ondelete='CASCADE'), nullable=False, unique=True)
    anonymous_session_hash = Column(String(64), nullable=False)
    expires_at = Column(Float, nullable=False)
    consumed_at = Column(Float, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)


class IntelligenceRun(Base):
    __tablename__ = 'intelligence_runs'
    id = Column(String(64), primary_key=True, default=opaque_id)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    source_report_id = Column(String(64), ForeignKey('research_reports.id', ondelete='SET NULL'), nullable=True)
    provider = Column(String(40), nullable=False)
    model = Column(String(100), nullable=False)
    status = Column(String(40), nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(Float, default=time.time, nullable=False, index=True)


class Lead(Base):
    __tablename__ = 'leads'
    __table_args__ = (
        UniqueConstraint('business_id', 'url', name='uq_lead_business_url'),
        Index('uq_lead_business_id', 'business_id', 'id', unique=True),
        CheckConstraint("status IN ('discovered', 'qualified', 'contacted', 'replied', 'converted')", name='ck_lead_status'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(250), nullable=False)
    url = Column(String(2048), nullable=False)
    country = Column(String(2), nullable=False)
    status = Column(String(20), nullable=False, default='discovered')
    fit_reason = Column(Text, nullable=False)
    evidence_json = Column(Text, nullable=False)
    created_at = Column(Float, default=time.time, nullable=False)
    updated_at = Column(Float, default=time.time, nullable=False)


class LeadEvent(Base):
    __tablename__ = 'lead_events'
    id = Column(Integer, primary_key=True)
    lead_id = Column(String(64), ForeignKey('leads.id', ondelete='CASCADE'), nullable=False, index=True)
    business_id = Column(String(64), ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    evidence_json = Column(Text, nullable=False)
    created_at = Column(Float, default=time.time, nullable=False)


class MailOutbox(Base):
    __tablename__ = 'mail_outbox'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    kind = Column(String(30), nullable=False)
    recipient = Column(String(320), nullable=False)
    payload_cipher = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default='pending')
    created_at = Column(Float, default=time.time, nullable=False)


class ResearchJob(Base):
    __tablename__ = 'research_jobs'
    __table_args__ = (CheckConstraint("status IN ('queued','running','succeeded','failed')", name='ck_research_job_status'),)
    id = Column(String(64), primary_key=True, default=opaque_id)
    anonymous_session_hash = Column(String(64), nullable=False, index=True)
    payload_cipher = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='queued', index=True)
    attempts = Column(Integer, nullable=False, default=0)
    lease_until = Column(Float, nullable=True)
    report_id = Column(String(64), ForeignKey('research_reports.id', ondelete='SET NULL'), nullable=True)
    claim_cipher = Column(Text, nullable=True)
    error_code = Column(String(80), nullable=True)
    created_at = Column(Float, nullable=False, default=time.time)
    finished_at = Column(Float, nullable=True)


class ProviderBudgetLock(Base):
    """One database lock serializes cross-provider budget reservations."""
    __tablename__ = 'provider_budget_lock'
    __table_args__ = (CheckConstraint('id = 1', name='ck_provider_budget_lock'),)
    id = Column(Integer, primary_key=True)


class ProviderBudgetAccount(Base):
    """Hashed bucket keys carry no URLs, names, emails or provider secrets."""
    __tablename__ = 'provider_budget_accounts'
    __table_args__ = (
        CheckConstraint('reserved_microusd >= 0 AND calls >= 0', name='ck_budget_account_nonnegative'),
        CheckConstraint('limit_microusd > 0 AND call_limit > 0', name='ck_budget_account_limits'),
        CheckConstraint('reserved_microusd <= limit_microusd AND calls <= call_limit', name='ck_budget_account_capacity'),
    )
    key_hash = Column(String(64), primary_key=True)
    kind = Column(String(30), nullable=False)
    window_day = Column(Integer, nullable=False)
    limit_microusd = Column(BigInteger, nullable=False)
    call_limit = Column(Integer, nullable=False)
    reserved_microusd = Column(BigInteger, nullable=False, default=0)
    calls = Column(Integer, nullable=False, default=0)
    updated_at = Column(Float, nullable=False)


class ProviderUsageReservation(Base):
    """Conservative authorization debit; never mislabeled as invoiced spend."""
    __tablename__ = 'provider_usage_reservations'
    __table_args__ = (
        UniqueConstraint('dispatch_hash', name='uq_provider_usage_dispatch'),
        CheckConstraint('reserved_microusd > 0', name='ck_provider_usage_reservation'),
        CheckConstraint("outcome IN ('reserved','succeeded','failed','uncertain')", name='ck_provider_usage_outcome'),
    )
    id = Column(String(64), primary_key=True, default=opaque_id)
    dispatch_hash = Column(String(64), nullable=False)
    scope_hash = Column(String(64), nullable=False, index=True)
    request_hash = Column(String(64), nullable=False, index=True)
    provider = Column(String(30), nullable=False)
    operation = Column(String(30), nullable=False)
    policy_version = Column(String(100), nullable=False)
    policy_hash = Column(String(64), nullable=False)
    reserved_microusd = Column(BigInteger, nullable=False)
    outcome = Column(String(20), nullable=False, default='reserved')
    usage_json = Column(Text, nullable=False, default='{}')
    created_at = Column(Float, nullable=False, index=True)
    settled_at = Column(Float, nullable=True)


# All domains share one migration registry; individual modules import model_base.
from ayo.merchant_models import BusinessProfile, Task  # noqa: E402,F401
from ayo.lead_models import LeadList, LeadListItem, LeadNote, OutreachDraft  # noqa: E402,F401
from ayo.assistant_models import AssistantConversation, AssistantMessage, AssistantToolRun  # noqa: E402,F401
