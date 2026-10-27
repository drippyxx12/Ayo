"""Transactional account, session, membership and founding-user services.

Callers own the SQLAlchemy transaction and must commit successful use cases.
Authentication failures also record rate-limit/audit state: commit that state
when returning a handled IdentityError rather than rolling it back. Raw session
and one-time tokens are returned to the trusted HTTP/mail layer only; the
database contains their SHA-256 digests, never bearer credentials.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import secrets
import time
from typing import Callable, Iterable

from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ayo.models import (
    AuditEvent, AuthAttempt, AuthSession, Business, CohortCounter, FoundingGrant,
    IdentityToken, Membership, User,
)


COUNTRIES = {
    'NG': {'currency': 'NGN', 'timezone': 'Africa/Lagos'},
    'GH': {'currency': 'GHS', 'timezone': 'Africa/Accra'},
}
SESSION_TTL = 7 * 24 * 60 * 60
TOKEN_TTL = {'verify_email': 24 * 60 * 60, 'reset_password': 30 * 60}
AUTH_WINDOW = 15 * 60


class IdentityError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400, retry_after: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass(frozen=True)
class Registration:
    user: User
    business: Business
    founding_slot: int | None
    verification_token: str = field(repr=False)


@dataclass(frozen=True)
class SessionGrant:
    user: User
    token: str = field(repr=False)
    csrf: str = field(repr=False)
    expires_at: float


@dataclass(frozen=True)
class Entitlement:
    founding_slot: int | None
    all_features_free: bool
    includes_future_features: bool
    requires_payment: bool = False
    automatic_expiry: None = None
    later_user_pricing: str = 'founder_decision_pending'


@dataclass(frozen=True)
class FeatureAccess:
    allowed: bool
    reason: str
    requires_payment: bool = False


def normalize_email(email: str) -> str:
    if not isinstance(email, str) or len(email) > 320:
        raise IdentityError('invalid_email', 'Enter a valid email address.')
    email = email.strip().lower()
    if not re.fullmatch(r'[^@\s\x00-\x1f\x7f]+@[^@\s\x00-\x1f\x7f]+\.[^@\s\x00-\x1f\x7f]+', email):
        raise IdentityError('invalid_email', 'Enter a valid email address.')
    return email


def validate_password(password: str) -> None:
    if not isinstance(password, str) or not 12 <= len(password) <= 200:
        raise IdentityError('invalid_password', 'Use a password between 12 and 200 characters.')


def password_hash(password: str) -> str:
    validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1)
    return 'scrypt$' + salt.hex() + '$' + digest.hex()


def password_verify(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or not 12 <= len(password) <= 200:
        return False
    try:
        algorithm, salt_hex, digest_hex = encoded.split('$')
        if algorithm != 'scrypt' or len(salt_hex) != 32 or len(digest_hex) != 128:
            return False
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
        digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**14, r=8, p=1)
        return secrets.compare_digest(digest, expected)
    except (AttributeError, TypeError, ValueError):
        return False


_DUMMY_HASH = password_hash(secrets.token_urlsafe(32))


def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _valid_token(raw: str | None) -> bool:
    return isinstance(raw, str) and 32 <= len(raw) <= 200 and raw.isascii()


class IdentityService:
    def __init__(self, session: Session, clock: Callable[[], float] = time.time):
        self.session = session
        self.clock = clock

    def _insert(self, model):
        dialect = self.session.get_bind().dialect.name
        if dialect == 'postgresql':
            return pg_insert(model)
        if dialect == 'sqlite':
            return sqlite_insert(model)
        raise RuntimeError('Identity requires PostgreSQL or SQLite for transactional upserts.')

    def audit(self, action: str, *, user_id=None, business_id=None,
              resource_type: str = 'identity', resource_id=None, details: dict | None = None) -> None:
        self.session.add(AuditEvent(
            actor_user_id=user_id, business_id=business_id, action=action,
            resource_type=resource_type, resource_id=str(resource_id) if resource_id is not None else None,
            details_json=json.dumps(details or {}, sort_keys=True), created_at=self.clock(),
        ))

    def _attempt(self, purpose: str, subject: str, *, limit: int, window: int = AUTH_WINDOW) -> None:
        now = self.clock()
        digest = token_hash(purpose + '\0' + subject[:512])
        expired = AuthAttempt.window_started <= now - window
        query = self._insert(AuthAttempt).values(key_hash=digest, window_started=now, count=1)
        query = query.on_conflict_do_update(index_elements=['key_hash'], set_={
            'window_started': case((expired, now), else_=AuthAttempt.window_started),
            'count': case((expired, 1), else_=AuthAttempt.count + 1),
        }).returning(AuthAttempt.count, AuthAttempt.window_started)
        count, started = self.session.execute(query).one()
        if count > limit:
            raise IdentityError('rate_limited', 'Too many attempts. Try again later.', 429,
                                max(1, math.ceil(started + window - now)))

    def register(self, email: str, password: str, business_name: str,
                 country: str, *, client_key: str = '') -> Registration:
        email = normalize_email(email)
        validate_password(password)
        business_name = business_name.strip() if isinstance(business_name, str) else ''
        if not 2 <= len(business_name) <= 160 or any(ord(c) < 32 or ord(c) == 127 for c in business_name):
            raise IdentityError('invalid_business', 'Enter a business name between 2 and 160 characters.')
        if country not in COUNTRIES:
            raise IdentityError('invalid_country', 'Choose Nigeria or Ghana for your business.')
        if client_key:
            self._attempt('signup-client', client_key, limit=5, window=60 * 60)
        if self.session.scalar(select(User.id).where(User.email == email)) is not None:
            raise IdentityError('account_exists', 'An account already exists. Sign in or recover access.', 409)
        now = self.clock()
        user = User(email=email, password_hash=password_hash(password), joined=now)
        self.session.add(user)
        self.session.flush()
        business = self.create_business(user.id, business_name, country)
        slot = self.claim_founding(user.id)
        verification = self.issue_token(user.id, 'verify_email')
        self.audit('account.registered', user_id=user.id, business_id=business.id,
                   resource_type='user', resource_id=user.id,
                   details={'founding_slot': slot, 'email_verified': False})
        return Registration(user, business, slot, verification)

    def create_business(self, user_id, name: str, country: str) -> Business:
        user = self.session.get(User, user_id)
        if not user or user.disabled_at is not None:
            raise IdentityError('authentication_required', 'Sign in required.', 401)
        name = name.strip() if isinstance(name, str) else ''
        if not 2 <= len(name) <= 160 or any(ord(c) < 32 or ord(c) == 127 for c in name):
            raise IdentityError('invalid_business', 'Enter a business name between 2 and 160 characters.')
        if country not in COUNTRIES:
            raise IdentityError('invalid_country', 'Choose Nigeria or Ghana for your business.')
        business = Business(name=name, country=country, created_at=self.clock(), **COUNTRIES[country])
        self.session.add(business)
        self.session.flush()
        self.session.add(Membership(user_id=user_id, business_id=business.id, role='owner'))
        self.session.flush()
        self.audit('business.created', user_id=user_id, business_id=business.id,
                   resource_type='business', resource_id=business.id, details={'country': country})
        return business

    def claim_founding(self, user_id) -> int | None:
        """Allocate once per account, serialized independently of workspace count.

        Taking a user write lock before checking its grant makes idempotent
        retries safe on PostgreSQL and SQLite. The allocator's conditional
        UPDATE serializes concurrent signups and cannot issue position 501.
        """
        locked = self.session.execute(update(User).where(User.id == user_id, User.disabled_at.is_(None)).values(id=User.id).returning(User.id)).scalar_one_or_none()
        if locked is None:
            raise IdentityError('authentication_required', 'Account not found.', 401)
        existing = self.session.scalar(select(FoundingGrant.slot).where(FoundingGrant.user_id == user_id))
        if existing is not None:
            return existing
        self.session.execute(self._insert(CohortCounter).values(id=1, next_slot=1).on_conflict_do_nothing(index_elements=['id']))
        allocated = self.session.execute(update(CohortCounter).where(
            CohortCounter.id == 1, CohortCounter.next_slot <= 500,
        ).values(next_slot=CohortCounter.next_slot + 1).returning(CohortCounter.next_slot)).scalar_one_or_none()
        if allocated is None:
            return None
        slot = allocated - 1
        self.session.add(FoundingGrant(user_id=user_id, slot=slot, awarded_at=self.clock()))
        self.session.flush()
        self.audit('founding.awarded', user_id=user_id, resource_type='founding_grant',
                   resource_id=user_id, details={'slot': slot, 'all_features_free': True})
        return slot

    def entitlement(self, user_id) -> Entitlement:
        slot = self.session.scalar(select(FoundingGrant.slot).where(FoundingGrant.user_id == user_id))
        return Entitlement(slot, slot is not None, slot is not None)

    def feature_access(self, user_id, feature_key: str, *, implemented: bool = True,
                       country_supported: bool = True, authorized: bool = True) -> FeatureAccess:
        user = self.session.get(User, user_id)
        if not user or user.disabled_at is not None:
            return FeatureAccess(False, 'authentication_required')
        if not implemented:
            return FeatureAccess(False, 'not_implemented')
        if not country_supported:
            return FeatureAccess(False, 'country_not_supported')
        if not authorized:
            return FeatureAccess(False, 'permission_required')
        # All feature keys, including future releases, inherit the same grant.
        # Later-user pricing has not been authorized, so do not invent billing.
        grant = self.entitlement(user_id)
        return FeatureAccess(True, 'founding_all_features_free' if grant.all_features_free else 'later_user_pricing_pending')

    def login(self, email: str, password: str, client_key: str = '') -> SessionGrant:
        try:
            email = normalize_email(email)
        except IdentityError:
            email = ''
        user = self.session.scalar(select(User).where(User.email == email)) if email else None
        if user:
            # Serialize password verification and session issuance with password
            # changes/removal; a cached hash must not issue a post-revocation grant.
            user = self.lock_user(user.id)
        self._attempt('login-account', email or 'invalid', limit=8)
        if client_key:
            self._attempt('login-client', client_key, limit=40)
        valid = password_verify(password, user.password_hash if user else _DUMMY_HASH)
        if not user or not valid or user.disabled_at is not None:
            self.audit('account.login_failed')
            raise IdentityError('invalid_credentials', 'Invalid email or password.', 401)
        self.session.execute(delete(AuthAttempt).where(AuthAttempt.key_hash == token_hash('login-account\0' + email)))
        return self.create_session(user.id)

    def create_session(self, user_id) -> SessionGrant:
        user = self.lock_user(user_id)
        if not user or user.disabled_at is not None:
            raise IdentityError('authentication_required', 'Sign in required.', 401)
        raw = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(32)
        expires = self.clock() + SESSION_TTL
        self.session.add(AuthSession(token_hash=token_hash(raw), user_id=user.id,
                                     expires_at=expires, csrf=csrf))
        self.audit('account.session_created', user_id=user.id)
        return SessionGrant(user, raw, csrf, expires)

    def lock_user(self, user_id):
        """Fresh account state held until caller commit on both supported DBs.

        SQLite ignores FOR UPDATE, so take its write lock before reading. All
        authenticated account/token writes follow User → token/session order.
        """
        self.session.execute(update(User).where(User.id == user_id).values(id=User.id))
        return self.session.scalar(select(User).where(User.id == user_id).with_for_update()
                                   .execution_options(populate_existing=True))

    def session_record(self, raw: str | None) -> AuthSession | None:
        if not _valid_token(raw):
            return None
        return self.session.scalar(select(AuthSession).join(User, AuthSession.user_id == User.id).where(
            AuthSession.token_hash == token_hash(raw), AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > self.clock(), User.disabled_at.is_(None),
        ))

    def resolve_session(self, raw: str | None) -> User | None:
        record = self.session_record(raw)
        return self.session.get(User, record.user_id) if record else None

    def validate_csrf(self, raw: str | None, supplied: str | None) -> bool:
        record = self.session_record(raw)
        return bool(record and isinstance(supplied, str) and supplied and
                    secrets.compare_digest(record.csrf.encode(), supplied.encode()))

    def revoke_session(self, raw: str | None) -> None:
        if not _valid_token(raw):
            return
        user_id = self.session.execute(update(AuthSession).where(
            AuthSession.token_hash == token_hash(raw), AuthSession.revoked_at.is_(None),
        ).values(revoked_at=self.clock()).returning(AuthSession.user_id)).scalar_one_or_none()
        if user_id is not None:
            self.audit('account.session_revoked', user_id=user_id)

    def issue_token(self, user_id, purpose: str) -> str:
        if purpose not in TOKEN_TTL:
            raise IdentityError('invalid_purpose', 'Unsupported identity token purpose.')
        user = self.lock_user(user_id)
        if not user or user.disabled_at is not None:
            raise IdentityError('authentication_required', 'Account not found.', 401)
        now = self.clock()
        self.session.execute(update(IdentityToken).where(
            IdentityToken.user_id == user_id, IdentityToken.purpose == purpose,
            IdentityToken.consumed_at.is_(None),
        ).values(consumed_at=now))
        raw = secrets.token_urlsafe(48)
        self.session.add(IdentityToken(token_hash=token_hash(raw), user_id=user_id,
                                       purpose=purpose, expires_at=now + TOKEN_TTL[purpose]))
        self.audit('identity.token_issued', user_id=user_id, details={'purpose': purpose})
        return raw

    def _consume_token(self, raw: str, purpose: str):
        if not _valid_token(raw):
            raise IdentityError('invalid_token', 'This link is invalid or expired.', 400)
        user_id = self.session.scalar(select(IdentityToken.user_id).where(
            IdentityToken.token_hash == token_hash(raw), IdentityToken.purpose == purpose,
            IdentityToken.consumed_at.is_(None), IdentityToken.expires_at > self.clock()))
        user = self.lock_user(user_id) if user_id is not None else None
        if not user or user.disabled_at is not None:
            raise IdentityError('invalid_token', 'This link is invalid or expired.', 400)
        claimed_user_id = self.session.execute(update(IdentityToken).where(
            IdentityToken.token_hash == token_hash(raw), IdentityToken.purpose == purpose,
            IdentityToken.consumed_at.is_(None), IdentityToken.expires_at > self.clock(),
        ).values(consumed_at=self.clock()).returning(IdentityToken.user_id)).scalar_one_or_none()
        if claimed_user_id != user_id:
            raise IdentityError('invalid_token', 'This link is invalid or expired.', 400)
        return user

    def consume_verification(self, raw: str) -> User:
        user = self._consume_token(raw, 'verify_email')
        if user.email_verified_at is None:
            user.email_verified_at = self.clock()
        self.audit('account.email_verified', user_id=user.id)
        return user

    def request_password_reset(self, email: str, client_key: str = '') -> tuple[User, str] | None:
        if client_key:
            self._attempt('reset-client', client_key, limit=5, window=60 * 60)
        try:
            email = normalize_email(email)
        except IdentityError:
            return None
        user = self.session.scalar(select(User).where(User.email == email, User.disabled_at.is_(None)))
        if user:
            user = self.lock_user(user.id)
        self._attempt('reset-account', email, limit=3, window=60 * 60)
        if not user or user.disabled_at is not None:
            return None
        return user, self.issue_token(user.id, 'reset_password')

    def reset_password(self, raw: str, new_password: str) -> User:
        validate_password(new_password)
        user = self._consume_token(raw, 'reset_password')
        user.password_hash = password_hash(new_password)
        now = self.clock()
        self.session.execute(update(AuthSession).where(
            AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None),
        ).values(revoked_at=now))
        self.audit('account.password_reset', user_id=user.id)
        return user

    def require_membership(self, user_id, business_id, roles: Iterable[str] | None = None) -> Membership:
        if roles is not None:
            self.lock_user(user_id)
        member = self.session.scalar(select(Membership).join(User, Membership.user_id == User.id).where(
            Membership.user_id == user_id, Membership.business_id == business_id,
            User.disabled_at.is_(None),
        ).execution_options(populate_existing=True))
        if not member or (roles is not None and member.role not in set(roles)):
            raise IdentityError('forbidden_tenant', 'This workspace is not available to your account.', 403)
        return member

    def require_verified_user(self, user_id) -> User:
        user = self.lock_user(user_id)
        if not user or user.disabled_at is not None:
            raise IdentityError('authentication_required', 'Sign in required.', 401)
        if user.email_verified_at is None:
            raise IdentityError('verification_required', 'Verify your email before connecting providers or authorizing operations.', 403)
        return user
