"""Durable identity boundaries and founding-user allocation, without providers."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import secrets
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from ayo.identity import IdentityError, IdentityService, password_hash, password_verify, token_hash
from ayo.models import (
    AuditEvent, AuthAttempt, AuthSession, Base, CohortCounter, FoundingGrant,
    IdentityToken, Membership, User,
)


PASSWORD = 'FixturePasswordOnly123!'


@pytest.fixture
def identities(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "identity.db"}',
                           connect_args={'check_same_thread': False, 'timeout': 30})
    Base.metadata.create_all(engine)
    clock = SimpleNamespace(now=1_800_000_000.0)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as session:
        service = IdentityService(session, lambda: clock.now)
        yield SimpleNamespace(engine=engine, sessions=sessions, service=service,
                              session=session, clock=clock)
    engine.dispose()


def register(service, email='merchant@example.test', country='NG'):
    return service.register(email, PASSWORD, 'Fixture online merchant', country)


def test_registration_is_durable_and_country_explicit(identities):
    registration = register(identities.service, '  Merchant@Example.test ', 'GH')
    assert registration.user.email == 'merchant@example.test'
    assert registration.business.country == 'GH'
    assert registration.business.currency == 'GHS'
    assert registration.business.timezone == 'Africa/Accra'
    assert registration.user.email_verified_at is None
    assert registration.founding_slot == 1
    identities.session.commit()
    with identities.sessions() as reopened:
        user = reopened.scalar(select(User).where(User.email == 'merchant@example.test'))
        member = IdentityService(reopened).require_membership(user.id, registration.business.id)
        assert member.role == 'owner'
        assert reopened.scalar(select(FoundingGrant.slot).where(FoundingGrant.user_id == user.id)) == 1
        assert reopened.scalar(select(func.count()).select_from(AuditEvent)) >= 3


def test_compatible_scrypt_and_password_size_bounds():
    encoded = password_hash(PASSWORD)
    assert password_verify(PASSWORD, encoded)
    assert not password_verify('DifferentPassword123!', encoded)
    assert not password_verify(PASSWORD, encoded.replace('scrypt$', 'unsupported$', 1))
    assert not password_verify(PASSWORD, 'broken')
    for password in ['short', 'x' * 201]:
        with pytest.raises(IdentityError, match='between 12 and 200'):
            password_hash(password)
        assert not password_verify(password, encoded)


@pytest.mark.parametrize('email,country', [
    ('broken', 'NG'), ('with space@example.test', 'GH'), ('merchant@example.test', ''),
    ('merchant@example.test', 'US'), ('x' * 321, 'NG'),
])
def test_invalid_identity_input_creates_no_user_or_grant(identities, email, country):
    with pytest.raises(IdentityError):
        register(identities.service, email, country)
    assert identities.session.scalar(select(func.count()).select_from(User)) == 0
    assert identities.session.scalar(select(func.count()).select_from(FoundingGrant)) == 0


def test_normalized_duplicate_email_does_not_consume_another_slot(identities):
    register(identities.service)
    identities.session.commit()
    with pytest.raises(IdentityError) as exc:
        register(identities.service, 'MERCHANT@example.test')
    assert exc.value.code == 'account_exists'
    assert identities.session.scalar(select(CohortCounter.next_slot)) == 2


def test_each_user_keeps_one_free_grant_across_workspaces_and_future_features(identities):
    registration = register(identities.service)
    business2 = identities.service.create_business(registration.user.id, 'Another workspace', 'GH')
    assert identities.service.claim_founding(registration.user.id) == 1
    assert identities.service.entitlement(registration.user.id).includes_future_features is True
    assert identities.service.entitlement(registration.user.id).automatic_expiry is None
    assert identities.session.scalar(select(func.count()).select_from(FoundingGrant)) == 1
    assert identities.session.scalar(select(CohortCounter.next_slot)) == 2
    for feature in ['research', 'leads', 'future_feature_never_seen_before']:
        assert identities.service.feature_access(registration.user.id, feature).allowed
        assert not identities.service.feature_access(registration.user.id, feature).requires_payment
    assert identities.service.require_membership(registration.user.id, business2.id).role == 'owner'
    assert identities.service.feature_access(registration.user.id, 'write', authorized=False).reason == 'permission_required'
    assert identities.service.feature_access(registration.user.id, 'write', implemented=False).reason == 'not_implemented'
    assert identities.service.feature_access(registration.user.id, 'write', country_supported=False).reason == 'country_not_supported'


def test_founding_boundary_499_500_and_501(identities):
    identities.session.add(CohortCounter(id=1, next_slot=499))
    identities.session.commit()
    registrations = [register(identities.service, f'boundary-{i}@example.test') for i in range(3)]
    identities.session.commit()
    assert [r.founding_slot for r in registrations] == [499, 500, None]
    assert identities.session.scalar(select(CohortCounter.next_slot)) == 501
    last = identities.service.entitlement(registrations[-1].user.id)
    assert not last.all_features_free
    assert not last.requires_payment
    assert last.later_user_pricing == 'founder_decision_pending'
    assert len({r.user.id for r in registrations}) == 3


def test_failed_registration_transaction_rolls_back_cohort_award(identities):
    register(identities.service)
    identities.session.rollback()
    assert identities.session.scalar(select(func.count()).select_from(User)) == 0
    assert register(identities.service, 'next@example.test').founding_slot == 1


def test_session_token_is_hashed_persistent_and_replay_revocable(identities):
    registered = register(identities.service)
    grant = identities.service.login(registered.user.email, PASSWORD, 'fixture-device')
    identities.session.commit()
    record = identities.session.get(AuthSession, token_hash(grant.token))
    assert record and record.token_hash != grant.token
    assert grant.token not in repr(grant)
    assert grant.csrf not in repr(grant)
    assert identities.service.resolve_session(grant.token).id == registered.user.id
    assert identities.service.validate_csrf(grant.token, grant.csrf)
    assert not identities.service.validate_csrf(grant.token, 'wrong')
    assert not identities.service.validate_csrf(grant.token, '')
    assert not identities.service.validate_csrf(grant.token, 'incorrect-☃')
    identities.service.revoke_session(grant.token)
    identities.session.commit()
    with identities.sessions() as reopened:
        assert IdentityService(reopened, lambda: identities.clock.now).resolve_session(grant.token) is None


def test_expired_forged_and_disabled_account_sessions_fail_closed(identities):
    registration = register(identities.service)
    grant = identities.service.create_session(registration.user.id)
    identities.session.commit()
    for token in [None, '', 'bad', 'x' * 300, secrets.token_urlsafe(48)]:
        assert identities.service.resolve_session(token) is None
    identities.clock.now = grant.expires_at
    assert identities.service.resolve_session(grant.token) is None
    identities.clock.now -= 100
    registration.user.disabled_at = identities.clock.now
    identities.session.flush()
    assert identities.service.resolve_session(grant.token) is None
    assert not identities.service.feature_access(registration.user.id, 'anything').allowed


def test_memberships_deny_other_users_and_roles(identities):
    owner = register(identities.service)
    other = register(identities.service, 'other@example.test', 'GH')
    with pytest.raises(IdentityError) as exc:
        identities.service.require_membership(other.user.id, owner.business.id)
    assert exc.value.code == 'forbidden_tenant'
    member = identities.service.require_membership(owner.user.id, owner.business.id, ['owner'])
    member.role = 'analyst'
    identities.session.flush()
    with pytest.raises(IdentityError, match='not available'):
        identities.service.require_membership(owner.user.id, owner.business.id, ['owner', 'admin'])
    assert identities.session.scalar(select(func.count()).select_from(Membership)) == 2


def test_verification_tokens_are_hashed_purpose_scoped_expiring_and_one_use(identities):
    registration = register(identities.service)
    raw = registration.verification_token
    assert raw not in repr(registration)
    assert identities.session.get(IdentityToken, token_hash(raw)).purpose == 'verify_email'
    with pytest.raises(IdentityError):
        identities.service.require_verified_user(registration.user.id)
    with pytest.raises(IdentityError):
        identities.service.reset_password(raw, 'DifferentPassword123!')
    verified = identities.service.consume_verification(raw)
    identities.session.commit()
    assert verified.email_verified_at == identities.clock.now
    assert identities.service.require_verified_user(verified.id).id == verified.id
    with pytest.raises(IdentityError):
        identities.service.consume_verification(raw)
    another = identities.service.issue_token(verified.id, 'verify_email')
    identities.session.flush()
    identities.clock.now += 24 * 60 * 60
    with pytest.raises(IdentityError):
        identities.service.consume_verification(another)


def test_issuing_a_new_token_revokes_the_earlier_link(identities):
    registration = register(identities.service)
    new = identities.service.issue_token(registration.user.id, 'verify_email')
    identities.session.flush()
    with pytest.raises(IdentityError):
        identities.service.consume_verification(registration.verification_token)
    assert identities.service.consume_verification(new).id == registration.user.id


def test_password_reset_is_one_time_and_revokes_every_existing_session(identities):
    registration = register(identities.service)
    grants = [identities.service.create_session(registration.user.id) for _ in range(2)]
    requested = identities.service.request_password_reset(registration.user.email)
    assert requested is not None
    reset_user, raw = requested
    assert reset_user.id == registration.user.id
    identities.session.commit()
    identities.service.reset_password(raw, 'ChangedPassword123!')
    identities.session.commit()
    assert all(identities.service.resolve_session(grant.token) is None for grant in grants)
    assert not password_verify(PASSWORD, registration.user.password_hash)
    assert password_verify('ChangedPassword123!', registration.user.password_hash)
    with pytest.raises(IdentityError):
        identities.service.reset_password(raw, 'OneMorePassword123!')
    assert identities.service.request_password_reset('unknown@example.test') is None
    assert identities.service.request_password_reset('not-an-email') is None


def test_persistent_failed_login_throttles_across_service_instances(identities):
    registration = register(identities.service)
    identities.session.commit()
    for _ in range(8):
        with identities.sessions() as session:
            with pytest.raises(IdentityError) as exc:
                IdentityService(session, lambda: identities.clock.now).login(registration.user.email, 'WrongPassword123!', 'same-client')
            assert exc.value.code == 'invalid_credentials'
            session.commit()  # Route contract: persist failure counters.
    with identities.sessions() as session:
        service = IdentityService(session, lambda: identities.clock.now)
        with pytest.raises(IdentityError) as exc:
            service.login(registration.user.email, PASSWORD, 'same-client')
        assert exc.value.code == 'rate_limited'
        assert exc.value.status_code == 429
        assert exc.value.retry_after == 900
        session.commit()
    identities.clock.now += 901
    with identities.sessions() as session:
        service = IdentityService(session, lambda: identities.clock.now)
        assert service.login(registration.user.email, PASSWORD, 'same-client').user.id == registration.user.id


def test_audit_and_rate_limit_records_never_contain_raw_bearer_tokens(identities):
    registration = register(identities.service)
    grant = identities.service.login(registration.user.email, PASSWORD, 'client-address-fixture')
    identities.session.flush()
    events = identities.session.scalars(select(AuditEvent)).all()
    serialized = json.dumps([{'action': e.action, 'details': e.details_json} for e in events])
    for raw in [PASSWORD, registration.verification_token, grant.token, 'client-address-fixture']:
        assert raw not in serialized
    attempts = identities.session.scalars(select(AuthAttempt)).all()
    assert all(len(a.key_hash) == 64 for a in attempts)


def _concurrent_boundary(engine):
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as session:
        session.add(CohortCounter(id=1, next_slot=499))
        session.commit()

    def signup(index):
        with sessions() as session:
            result = register(IdentityService(session), f'concurrent-{index}@example.test')
            session.commit()
            return result.founding_slot

    with ThreadPoolExecutor(max_workers=6) as executor:
        slots = list(executor.map(signup, range(8)))
    assert sorted(s for s in slots if s is not None) == [499, 500]
    assert slots.count(None) == 6
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 8
        assert session.scalar(select(CohortCounter.next_slot)) == 501
        assert session.scalar(select(func.count()).select_from(FoundingGrant)) == 2


def test_sqlite_concurrent_signups_do_not_overissue(identities):
    _concurrent_boundary(identities.engine)


@pytest.mark.skipif(not os.getenv('AYO_TEST_POSTGRES_URL'), reason='Local PostgreSQL integration URL not configured')
def test_postgres_concurrent_signups_do_not_overissue():
    """Use a disposable schema, never drop or mutate a shared application schema."""
    admin = create_engine(os.environ['AYO_TEST_POSTGRES_URL'])
    schema = 'identity_test_' + secrets.token_hex(8)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = admin.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(engine)
        _concurrent_boundary(engine)
    finally:
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
