"""Password-confirmed account controls against real persistent test databases."""
import json

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from ayo import app as mod
from ayo.account_management import change_password, revoke_other_sessions
from ayo.identity import IdentityError, IdentityService
from ayo.models import AuditEvent, AuthSession, Business, FoundingGrant, User
from test_platform_flow import csrf, platform, register, verify_latest


def signed_in(platform):
    register(platform.client, 'security-owner@example.org')
    verify_latest(platform.client, platform.factory)


def login(client, password='FixturePassword123!'):
    return client.post('/login', data={'csrf': csrf(client, '/login'),
        'email': 'security-owner@example.org', 'password': password})


def test_revoke_other_sessions_is_account_scoped_and_requires_password(platform):
    signed_in(platform)
    client = platform.client
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as other_session:
        assert login(other_session).status_code == 303
        with platform.factory() as session:
            stranger = IdentityService(session).register('independent@example.org', 'FixturePassword123!', 'Separate', 'NG')
            unrelated = IdentityService(session).create_session(stranger.user.id)
            session.commit()
        assert client.get('/security').text.count('Another signed-in session') == 1
        failed = client.post('/security/sessions/revoke-others', data={'csrf': csrf(client, '/security'), 'password': 'IncorrectPassword!'})
        assert failed.status_code == 403
        assert other_session.get('/dashboard').status_code == 200
        result = client.post('/security/sessions/revoke-others', data={'csrf': csrf(client, '/security'), 'password': 'FixturePassword123!'})
        assert result.status_code == 303
        assert client.get('/dashboard').status_code == 200
        assert other_session.get('/dashboard').status_code == 303
        with platform.factory() as session:
            assert IdentityService(session).resolve_session(unrelated.token).id == stranger.user.id
            assert session.scalar(select(AuditEvent).where(AuditEvent.action == 'account.other_sessions_revoked'))
        page = client.get('/security')
        assert 'Another signed-in session' not in page.text
        assert unrelated.token not in page.text
        with platform.factory() as session:
            for record in session.scalars(select(AuthSession)):
                assert record.token_hash not in page.text


def test_change_password_rotates_current_session_preserves_workspace_and_entitlement(platform):
    signed_in(platform)
    client = platform.client
    with platform.factory() as session:
        user = session.scalar(select(User))
        next_business = IdentityService(session).create_business(user.id, 'Second workspace', 'NG')
        old_session = IdentityService(session).create_session(user.id)
        old_reset = IdentityService(session).issue_token(user.id, 'reset_password')
        session.commit()
        slot = session.scalar(select(FoundingGrant.slot))
    assert client.post('/business/switch', data={'csrf': csrf(client, '/settings'), 'business_id': next_business.id}).status_code == 303
    old_csrf = csrf(client, '/security')
    result = client.post('/security/password', data={'csrf': old_csrf, 'current_password': 'FixturePassword123!',
        'new_password': 'NewFixturePassword456!'})
    assert result.status_code == 303
    assert 'Second workspace' in client.get('/dashboard').text
    assert csrf(client, '/security') != old_csrf
    with platform.factory() as session:
        assert IdentityService(session).resolve_session(old_session.token) is None
        with pytest.raises(IdentityError):
            IdentityService(session).reset_password(old_reset, 'StolenResetPassword!')
        assert session.scalar(select(FoundingGrant.slot)) == slot
        assert session.scalar(select(func.count()).select_from(FoundingGrant)) == 1
        assert session.scalar(select(AuditEvent).where(AuditEvent.action == 'account.password_changed'))
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as fresh:
        assert login(fresh).status_code == 200  # Old password no longer signs in.
        assert login(fresh, 'NewFixturePassword456!').status_code == 303
        assert fresh.get('/dashboard').status_code == 200


def test_password_validation_csrf_and_failed_confirmation_leave_access_intact(platform):
    signed_in(platform)
    client = platform.client
    for new_password, expected in [('short', 400), ('FixturePassword123!', 400)]:
        response = client.post('/security/password', data={'csrf': csrf(client, '/security'),
            'current_password': 'FixturePassword123!', 'new_password': new_password})
        assert response.status_code == expected
        assert client.get('/dashboard').status_code == 200
    assert client.post('/security/password', data={'csrf': 'wrong', 'current_password': 'FixturePassword123!',
        'new_password': 'NewFixturePassword456!'}).status_code == 403
    assert client.post('/security/sessions/revoke-others', data={'csrf': 'wrong', 'password': 'FixturePassword123!'}).status_code == 403
    with platform.factory() as session:
        assert session.scalar(select(AuditEvent).where(AuditEvent.action == 'account.password_changed')) is None


def test_security_rate_limit_persists_failed_password_confirmations(platform):
    signed_in(platform)
    client = platform.client
    token = csrf(client, '/security')
    for _ in range(10):
        assert client.post('/security/sessions/revoke-others', data={
            'csrf': token, 'password': 'WrongFixturePassword!'}).status_code == 403
    assert client.post('/security/password', data={'csrf': token,
        'current_password': 'FixturePassword123!', 'new_password': 'NewFixturePassword456!'}).status_code == 429
    assert client.get('/dashboard').status_code == 200


def test_overview_and_activity_show_only_actual_selected_workspace_records(platform):
    signed_in(platform)
    client = platform.client
    assert client.post('/work/tasks', data={'csrf': csrf(client, '/work'), 'title': 'Review delivery policy'}).status_code == 303
    home = client.get('/dashboard')
    assert 'Review delivery policy' in home.text
    assert 'no business-scoped commerce records' in home.text
    assert 'Sales, revenue and customer metrics' in home.text
    with platform.factory() as session:
        business = session.scalar(select(Business))
        event = AuditEvent(business_id=business.id, action='task.created', resource_type='task', details_json=json.dumps({'secret_internal_detail': 'not for list rendering'}))
        session.add(event)
        for index in range(35):
            session.add(AuditEvent(business_id=business.id, action='fixture.recorded', resource_type='fixture', created_at=1000 + index))
        user = session.scalar(select(User))
        separate = IdentityService(session).create_business(user.id, 'Clean workspace', 'NG')
        session.commit()
    activity = client.get('/activity')
    assert 'task · created' in activity.text and 'Older events' in activity.text
    assert 'not for list rendering' not in activity.text
    assert 'Newer events' in client.get('/activity?page=2').text
    client.post('/business/switch', data={'csrf': csrf(client, '/settings'), 'business_id': separate.id})
    assert 'Review delivery policy' not in client.get('/dashboard').text
    assert 'task · created' not in client.get('/activity').text
    assert client.get('/help').status_code == 200


def test_cached_account_cannot_use_superseded_password_during_rotation(platform):
    signed_in(platform)
    with platform.factory() as stale, platform.factory() as fresh:
        cached_user = stale.scalar(select(User))
        stale.commit()  # Match route context with expire_on_commit=False.
        change_password(fresh, cached_user.id, 'FixturePassword123!', 'RotatedFixturePassword!')
        fresh.commit()
        with pytest.raises(IdentityError, match='could not be confirmed'):
            change_password(stale, cached_user.id, 'FixturePassword123!', 'OutdatedRequestPassword!')
        stale.rollback()
        with pytest.raises(IdentityError, match='could not be confirmed'):
            revoke_other_sessions(stale, cached_user.id, 'irrelevant-session-token', 'FixturePassword123!')
