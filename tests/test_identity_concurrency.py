"""Real database races between authentication, private records and account removal.

Every worker owns its Session. Cached identities survive a committed request
context, and bounded database waits keep a failed serialization check from
hanging the suite. These tests use only synthetic, disposable local records.
"""
import secrets
import threading
import time

import pytest
from sqlalchemy import event, func, select

from ayo.account_deletion import remove_account
from ayo.account_management import change_password
from ayo.assistant import AssistantService
from ayo.assistant_models import AssistantConversation
from ayo.identity import IdentityError, IdentityService, password_verify
from ayo.models import AuthSession, IdentityToken, Membership, User
from test_platform_flow import platform  # noqa: F401


OLD_PASSWORD = 'FixturePassword123!'
NEW_PASSWORD = 'RotatedFixturePassword!'


def account(factory, *, shared=False):
    with factory() as session:
        identity = IdentityService(session)
        registration = identity.register('race-owner@example.org', OLD_PASSWORD, 'Fixture business', 'GH')
        registration.user.email_verified_at = time.time()
        reset_token = identity.issue_token(registration.user.id, 'reset_password')
        if shared:
            other = identity.register('race-coowner@example.org', OLD_PASSWORD, 'Other business', 'NG')
            session.add(Membership(user_id=other.user.id, business_id=registration.business.id, role='owner'))
        session.commit()
        return registration.user.id, registration.business.id, reset_token


class CachedRequest:
    """A request waiting to run after retaining its context's identity map."""

    def __init__(self, factory, user_id, operation):
        self.ready = threading.Event()
        self.begin = threading.Event()
        self.attempted = threading.Event()
        self.finished = threading.Event()
        self.outcome = None
        self.error = None

        def run():
            try:
                with factory() as session:
                    cached = session.get(User, user_id)
                    session.commit()
                    self.ready.set()
                    if not self.begin.wait(5):
                        raise AssertionError('The competing request was never released.')
                    connection = session.connection()
                    if connection.dialect.name == 'postgresql':
                        connection.exec_driver_sql("SET LOCAL lock_timeout = '3s'")
                        connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
                    else:
                        connection.exec_driver_sql('PRAGMA busy_timeout=3000')

                    def attempted(*_args):
                        self.attempted.set()

                    event.listen(connection, 'before_cursor_execute', attempted)
                    try:
                        self.outcome = ('completed', operation(session))
                        session.commit()
                    except IdentityError as exc:
                        session.rollback()
                        self.outcome = (exc.code, None)
                    finally:
                        event.remove(connection, 'before_cursor_execute', attempted)
                    # Keep the original User strongly referenced until completion.
                    assert cached.id == user_id
            except BaseException as exc:
                self.error = exc
            finally:
                self.finished.set()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert self.ready.wait(3), 'The request did not cache its identity.'

    def assert_waiting(self):
        self.begin.set()
        assert self.attempted.wait(3), 'The request did not reach the database.'
        assert not self.finished.wait(.15), 'The competing request bypassed the held account lock.'

    def result(self):
        self.begin.set()
        assert self.finished.wait(8), 'The request exceeded its database deadline.'
        self.thread.join(timeout=.2)
        if self.error:
            raise self.error
        return self.outcome


def test_cached_login_waits_for_rotation_and_rejects_old_password(platform):
    user_id, _, _ = account(platform.factory)
    request = CachedRequest(platform.factory, user_id, lambda session:
        IdentityService(session).login('race-owner@example.org', OLD_PASSWORD))
    with platform.factory() as rotating:
        try:
            change_password(rotating, user_id, OLD_PASSWORD, NEW_PASSWORD)
            request.assert_waiting()
            rotating.commit()
        finally:
            rotating.rollback()
            outcome = request.result()
    assert outcome[0] == 'invalid_credentials'
    with platform.factory() as session:
        assert password_verify(NEW_PASSWORD, session.get(User, user_id).password_hash)
        assert session.scalar(select(func.count()).select_from(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))) == 1


@pytest.mark.parametrize('change', ['rotate', 'remove'])
def test_login_issuance_is_serialized_and_its_grant_is_revoked(platform, change):
    user_id, _, _ = account(platform.factory)
    verified, release_login = threading.Event(), threading.Event()

    def login(session):
        identity = IdentityService(session)
        create_session = identity.create_session

        def after_password_check(target_user_id):
            verified.set()
            assert release_login.wait(5), 'Login was not released after verification.'
            return create_session(target_user_id)

        identity.create_session = after_password_check
        return identity.login('race-owner@example.org', OLD_PASSWORD).token

    logging_in = CachedRequest(platform.factory, user_id, login)

    def competing_change(session):
        if change == 'rotate':
            return change_password(session, user_id, OLD_PASSWORD, NEW_PASSWORD).token
        remove_account(session, user_id, OLD_PASSWORD, 'DELETE')

    changing = CachedRequest(platform.factory, user_id, competing_change)
    try:
        logging_in.begin.set()
        assert verified.wait(3), 'Login never verified the password.'
        changing.assert_waiting()
    finally:
        release_login.set()
        login_outcome = logging_in.result()
        change_outcome = changing.result()
    assert login_outcome[0] == change_outcome[0] == 'completed'
    with platform.factory() as session:
        identity = IdentityService(session)
        assert identity.resolve_session(login_outcome[1]) is None
        if change == 'rotate':
            assert identity.resolve_session(change_outcome[1]).id == user_id
        else:
            assert session.get(User, user_id).disabled_at is not None


@pytest.mark.parametrize('operation', ['login', 'session', 'conversation', 'reset_token', 'reset_password'])
def test_cached_authentication_and_private_writes_cannot_repopulate_removed_account(platform, operation):
    user_id, business_id, reset_token = account(platform.factory, shared=True)

    def mutate(session):
        identity = IdentityService(session)
        if operation == 'login':
            return identity.login('race-owner@example.org', OLD_PASSWORD)
        if operation == 'session':
            return identity.create_session(user_id)
        if operation == 'conversation':
            return AssistantService(session).create(user_id, business_id, secrets.token_urlsafe(24))
        if operation == 'reset_token':
            return identity.issue_token(user_id, 'reset_password')
        return identity.reset_password(reset_token, NEW_PASSWORD)

    request = CachedRequest(platform.factory, user_id, mutate)
    with platform.factory() as removing:
        try:
            remove_account(removing, user_id, OLD_PASSWORD, 'DELETE')
            request.assert_waiting()
            removing.commit()
        finally:
            removing.rollback()
            outcome = request.result()
    assert outcome[0] in {'authentication_required', 'forbidden_tenant', 'invalid_token', 'invalid_credentials'}
    with platform.factory() as session:
        user = session.get(User, user_id)
        assert user.disabled_at is not None
        assert not password_verify(NEW_PASSWORD, user.password_hash)
        assert session.scalar(select(func.count()).select_from(Membership).where(Membership.user_id == user_id)) == 0
        for model in (AuthSession, IdentityToken, AssistantConversation):
            assert session.scalar(select(func.count()).select_from(model).where(model.user_id == user_id)) == 0
