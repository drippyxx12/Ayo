"""Tenant-scoped site control. Caller commits; network runs outside transactions.

This proves temporary control of one exact HTTPS host, not legal ownership,
verified report claims, site-edit permission, OAuth scope or outreach consent.
"""
from dataclasses import dataclass, field
import hmac
import re
import secrets
import time
from urllib.parse import urlsplit

from sqlalchemy import func, inspect, select

from ayo.identity import IdentityError, IdentityService, token_hash
from ayo.models import AuditEvent, Business
from ayo.research import ResearchError, _public_url
from ayo.site_control_models import SiteControlClaim
from ayo.site_control_reader import FileProof, PROOF_PATH

CHALLENGE_SECONDS = 3600
PROOF_SECONDS = 7 * 86400
LEASE_SECONDS = 45
ERRORS = {
    'verification_mismatch': 'The file does not contain this workspace’s exact verification text.',
    'verification_timeout': 'The website check timed out. Try again after one minute.',
    'robots_denied': 'The website robots policy prevents this check.',
    'robots_pacing': 'The website requires a slower verification method.',
    'robots_unavailable': 'The website robots policy could not be checked.',
    'verification_file_type': 'Serve the file as uncompressed plain text.',
    'verification_file_unavailable': 'The HTTPS file was unavailable or redirected. Use the exact address below.',
    'verification_fetch_failed': 'The public HTTPS file could not be checked safely.',
}


def schema_ready(session):
    connection = session.connection()
    schema = connection.get_execution_options().get('schema_translate_map', {}).get(None)
    return inspect(connection).has_table('site_control_claims', schema=schema)


def site_host(value):
    try:
        normalized = _public_url(value)
        parsed = urlsplit(normalized)
        # Explicit origin only: discarded query/fragment would obscure intent.
        raw = urlsplit(value if '://' in value else 'https://' + value)
        if (parsed.scheme != 'https' or parsed.port not in {None, 443}
                or parsed.path not in {'', '/'} or raw.query or raw.fragment):
            raise ValueError
        return parsed.hostname
    except (ResearchError, ValueError, TypeError):
        raise IdentityError('invalid_site_host', 'Enter only the exact HTTPS website host, without a page, query or fragment.') from None


def effective_status(row, now):
    if row.status == 'verified':
        return 'verified' if row.verified_until > now else 'expired'
    if row.status in {'pending', 'failed', 'checking'} and row.expires_at <= now:
        return 'expired'
    if row.status == 'checking' and (row.lease_until or 0) <= now:
        return 'failed'
    return row.status


@dataclass(frozen=True)
class CheckLease:
    claim_id: str
    host: str
    token: str = field(repr=False)


class SiteControlService:
    def __init__(self, session, cipher, clock=time.time):
        self.session, self.cipher, self.clock = session, cipher, clock
        self.identity = IdentityService(session, clock=clock)

    def _ready(self):
        if not schema_ready(self.session):
            raise IdentityError('site_control_not_ready', 'Website verification needs database migration 0009. Research remains available.', 503)

    def _write_access(self, user_id, business_id):
        self._ready()
        self.identity.require_verified_user(user_id)
        self.identity.require_membership(user_id, business_id, roles={'owner', 'admin'})
        self.session.scalar(select(Business).where(Business.id == business_id).with_for_update()
                            .execution_options(populate_existing=True))

    def list(self, user_id, business_id):
        self._ready()
        self.identity.require_membership(user_id, business_id)
        return self.session.scalars(select(SiteControlClaim).where(SiteControlClaim.business_id == business_id)
            .order_by(SiteControlClaim.created_at.desc(), SiteControlClaim.id).limit(100)).all()

    def get(self, user_id, business_id, claim_id):
        self._ready()
        self.identity.require_membership(user_id, business_id)
        row = self.session.scalar(select(SiteControlClaim).where(SiteControlClaim.id == claim_id,
            SiteControlClaim.business_id == business_id).execution_options(populate_existing=True))
        if row is None:
            raise IdentityError('site_control_not_found', 'Website verification not found in this workspace.', 404)
        return row

    def create(self, user_id, business_id, host, nonce):
        self._write_access(user_id, business_id)
        host = site_host(host)
        if not isinstance(nonce, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,64}', nonce):
            raise IdentityError('invalid_site_nonce', 'Reload the page before creating a verification request.')
        claim_id = token_hash(f'site-control\0{user_id}\0{business_id}\0{host}\0{nonce}')
        existing = self.session.get(SiteControlClaim, claim_id)
        if existing:
            return existing
        now = self.clock()
        pending = self.session.scalar(select(SiteControlClaim).where(SiteControlClaim.business_id == business_id,
            SiteControlClaim.host == host, SiteControlClaim.status.in_(['pending', 'failed', 'checking']),
            SiteControlClaim.expires_at > now).order_by(SiteControlClaim.created_at.desc()))
        if pending:
            return pending
        for conditions, maximum in (
            ((SiteControlClaim.business_id == business_id, SiteControlClaim.created_at > now - 3600), 3),
            ((SiteControlClaim.created_by == user_id, SiteControlClaim.created_at > now - 86400), 10),
        ):
            if self.session.scalar(select(func.count()).select_from(SiteControlClaim).where(*conditions)) >= maximum:
                raise IdentityError('site_control_rate_limited', 'Too many new verification requests. Try again later.', 429, 3600)
        text = 'ayo-site-verification=' + secrets.token_urlsafe(32)
        row = SiteControlClaim(id=claim_id, business_id=business_id, created_by=user_id, host=host,
            method='https_file', status='pending', token_hash=token_hash(text),
            token_cipher=self.cipher.encrypt(text.encode()).decode(), created_at=now, expires_at=now + CHALLENGE_SECONDS,
            attempts=0)
        self.session.add(row)
        self.session.flush()
        self.identity.audit('site_control.requested', user_id=user_id, business_id=business_id,
            resource_type='site_control', resource_id=row.id, details={'method': 'https_file', 'write_permission': False})
        return row

    def challenge_text(self, user_id, business_id, claim_id):
        self._write_access(user_id, business_id)
        row = self.get(user_id, business_id, claim_id)
        if effective_status(row, self.clock()) not in {'pending', 'failed', 'checking'} or not row.token_cipher:
            return None
        return self.cipher.decrypt(row.token_cipher.encode()).decode()

    def begin_check(self, user_id, business_id, claim_id):
        self._write_access(user_id, business_id)
        row = self.get(user_id, business_id, claim_id)
        now = self.clock()
        state = effective_status(row, now)
        if state not in {'pending', 'failed'}:
            raise IdentityError('site_control_not_pending', 'This request is expired, already verified, revoked or being checked.', 409)
        if row.attempts >= 5:
            raise IdentityError('site_control_attempt_limit', 'This request has used its five checks. Revoke it and create a new request.', 429, 3600)
        checks = self.session.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.action == 'site_control.check_started', AuditEvent.actor_user_id == user_id,
            AuditEvent.created_at > now - 3600))
        if checks >= 20:
            raise IdentityError('site_control_rate_limited', 'Too many website checks. Try again later.', 429, 3600)
        last = self.session.scalar(select(func.max(SiteControlClaim.checked_at)).where(
            SiteControlClaim.business_id == business_id, SiteControlClaim.host == row.host))
        if last is not None and now - last < 60:
            raise IdentityError('site_control_rate_limited', 'Wait one minute between checks for this host.', 429, max(1, int(60 - (now - last))))
        lease = secrets.token_urlsafe(32)
        row.status, row.checked_at, row.attempts = 'checking', now, row.attempts + 1
        row.lease_hash, row.lease_until, row.error_code = token_hash(lease), now + LEASE_SECONDS, None
        self.identity.audit('site_control.check_started', user_id=user_id, business_id=business_id,
            resource_type='site_control', resource_id=row.id, details={'attempt': row.attempts, 'maximum_gets': 2})
        self.session.flush()
        return CheckLease(row.id, row.host, lease)

    def finish_check(self, user_id, business_id, lease, proof=None, error_code=None):
        self._write_access(user_id, business_id)
        row = self.get(user_id, business_id, lease.claim_id)
        now = self.clock()
        if (row.status != 'checking' or (row.lease_until or 0) <= now or row.expires_at <= now
                or not hmac.compare_digest(row.lease_hash or '', token_hash(lease.token))):
            raise IdentityError('site_control_stale_check', 'This check is no longer current. Reload the verification page.', 409)
        matched = isinstance(proof, FileProof) and hmac.compare_digest(proof.content_hash, row.token_hash)
        row.lease_hash, row.lease_until = None, None
        if matched and not error_code:
            row.status, row.verified_at, row.verified_until = 'verified', now, now + PROOF_SECONDS
            row.proof_body_sha256, row.token_cipher, row.error_code = proof.body_hash, None, None
        else:
            row.status = 'failed'
            row.error_code = error_code if error_code in ERRORS else ('verification_fetch_failed' if error_code else 'verification_mismatch')
        self.identity.audit('site_control.' + row.status, user_id=user_id, business_id=business_id,
            resource_type='site_control', resource_id=row.id,
            details={'method': 'https_file', 'attempt': row.attempts, 'write_permission': False,
                     'source_url': 'https://' + row.host + PROOF_PATH,
                     'verified_at': row.verified_at, 'verified_until': row.verified_until,
                     'proof_body_sha256': row.proof_body_sha256, 'error_code': row.error_code})
        self.session.flush()
        return row

    def revoke(self, user_id, business_id, claim_id):
        self._write_access(user_id, business_id)
        chosen = self.get(user_id, business_id, claim_id)
        # Revoke every outstanding proof for this exact workspace/host, including
        # an older valid proof while a replacement challenge is pending.
        rows = self.session.scalars(select(SiteControlClaim).where(SiteControlClaim.business_id == business_id,
            SiteControlClaim.host == chosen.host)).all()
        for row in rows:
            row.status, row.token_cipher, row.lease_hash, row.lease_until = 'revoked', None, None, None
        self.identity.audit('site_control.revoked', user_id=user_id, business_id=business_id,
            resource_type='site_control', resource_id=chosen.id, details={'method': 'https_file', 'write_permission': False})
        self.session.flush()
        return chosen
