"""Exact-host proof workflow using real databases and offline HTTPS fixtures."""
import hashlib
import re
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ayo import app as mod
from ayo.identity import IdentityError, IdentityService
from ayo.models import AuditEvent, Business, Membership, ResearchReportRecord, User
from ayo.public_http import PublicHTTPResponse
from ayo.retention import cleanup_expired
from ayo.site_control import SiteControlService, effective_status, site_host
from ayo.site_control_models import SiteControlClaim
from ayo.site_control_reader import FileProof, PROOF_PATH, SiteFileReader
from test_merchant_work import owner
from test_platform_flow import platform, csrf  # noqa: F401


def request_site(platform, host='fixture-studio.org', nonce=None):
    page = platform.client.get('/business/sites')
    assert page.status_code == 200
    nonce = nonce or re.search(r'name="nonce" value="([^"]+)"', page.text).group(1)
    result = platform.client.post('/business/sites', data={'csrf': csrf(platform.client, '/business/sites'),
        'host': host, 'nonce': nonce})
    assert result.status_code == 303, result.text
    return result.headers['location'].rsplit('/', 1)[1]


def challenge(platform, claim_id):
    with platform.factory() as sess:
        row = sess.get(SiteControlClaim, claim_id)
        return mod.fernet.decrypt(row.token_cipher.encode()).decode()


def fixture_reader(monkeypatch, text, *, callback=None):
    calls = []
    async def request(url):
        calls.append(url)
        if callback and not url.endswith('/robots.txt'):
            callback()
        body = b'User-agent: *\nAllow: /\n' if url.endswith('/robots.txt') else (text + '\n').encode()
        return PublicHTTPResponse(url, 200, {'content-type': 'text/plain'}, body)
    monkeypatch.setattr(mod.app.state, 'site_file_reader_factory', lambda: SiteFileReader(request=request))
    return calls


def test_http_proof_persists_relogin_revokes_and_never_rewrites_reports(platform, monkeypatch):
    user_id, business_id = owner(platform)
    claim_id = request_site(platform)
    text = challenge(platform, claim_id)
    with platform.factory() as sess:
        row = sess.get(SiteControlClaim, claim_id)
        assert text not in row.token_cipher and row.token_hash == hashlib.sha256(text.encode()).hexdigest()
        stored = ResearchReportRecord(id='untouched', business_id=business_id, title='Immutable fixture',
            country='GH', report_json='{"website_ownership_verified":false}',
            status='PARTIAL', created_at=1, expires_at=9999999999)
        sess.add(stored)
        sess.commit()
    calls = fixture_reader(monkeypatch, text)
    detail = '/business/sites/' + claim_id
    assert text in platform.client.get(detail).text
    assert not calls  # GET never initiates network verification.
    result = platform.client.post(detail + '/check', data={'csrf': csrf(platform.client, detail)})
    assert result.status_code == 303, result.text
    assert calls == ['https://fixture-studio.org/robots.txt', 'https://fixture-studio.org' + PROOF_PATH]
    page = platform.client.get(detail)
    assert 'HTTPS file control verified' in page.text and text not in page.text
    assert 'does not certify legal' in page.text and 'grants none' in page.text
    with platform.factory() as sess:
        row = sess.get(SiteControlClaim, claim_id)
        assert row.status == 'verified' and row.token_cipher is None and row.attempts == 1
        assert row.verified_until - row.verified_at == 7 * 86400
        assert row.proof_body_sha256 == hashlib.sha256((text + '\n').encode()).hexdigest()
        assert sess.get(ResearchReportRecord, 'untouched').report_json == '{"website_ownership_verified":false}'
        audits = sess.scalars(select(AuditEvent).where(AuditEvent.resource_type == 'site_control')).all()
        assert len(audits) == 3 and all(text not in event.details_json for event in audits)
    assert platform.client.post(detail + '/check', data={'csrf': csrf(platform.client, detail)}).status_code == 409
    assert len(calls) == 2  # A successful proof cannot be renewed by replay.
    assert platform.client.post('/logout', data={'csrf': csrf(platform.client, detail)}).status_code == 303
    assert platform.client.post('/login', data={'csrf': csrf(platform.client, '/login'),
        'email': 'work-owner@example.org', 'password': 'FixturePassword123!'}).status_code == 303
    assert 'HTTPS file control verified' in platform.client.get(detail).text
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as reopened:
        reopened.cookies.update(platform.client.cookies)
        assert 'HTTPS file control verified' in reopened.get(detail).text
        assert len(calls) == 2
    replacement = request_site(platform)
    assert replacement != claim_id
    assert platform.client.post('/business/sites/' + replacement + '/revoke',
        data={'csrf': csrf(platform.client, detail)}).status_code == 303
    with platform.factory() as sess:
        rows = sess.scalars(select(SiteControlClaim)).all()
        assert all(row.status == 'revoked' and row.token_cipher is None for row in rows)
        assert sess.get(ResearchReportRecord, 'untouched').report_json == '{"website_ownership_verified":false}'


@pytest.mark.parametrize('role,verified', [('analyst', True), ('editor', True), ('owner', False), ('admin', False)])
def test_only_current_verified_owner_admin_can_manage_or_read_text(platform, role, verified):
    user_id, business_id = owner(platform)
    claim_id = request_site(platform)
    text = challenge(platform, claim_id)
    with platform.factory() as sess:
        sess.get(Membership, (business_id, user_id)).role = role
        if not verified:
            sess.get(User, user_id).email_verified_at = None
        sess.commit()
    detail = '/business/sites/' + claim_id
    page = platform.client.get(detail)
    assert page.status_code == 200 and text not in page.text
    for operation in ['/check', '/revoke']:
        assert platform.client.post(detail + operation, data={'csrf': csrf(platform.client, detail)}).status_code == 403
    assert platform.client.post('/business/sites', data={'host': 'other-fixture.org',
        'nonce': secrets.token_urlsafe(24), 'csrf': csrf(platform.client, detail)}).status_code == 403


def test_workspace_isolation_and_csrf(platform, monkeypatch):
    user_id, business_id = owner(platform)
    claim_id = request_site(platform)
    text = challenge(platform, claim_id)
    calls = fixture_reader(monkeypatch, text)
    path = '/business/sites/' + claim_id
    for operation in ['/check', '/revoke']:
        assert platform.client.post(path + operation, data={'csrf': 'invalid'}).status_code == 403
    with platform.factory() as sess:
        other = IdentityService(sess).create_business(user_id, 'Other workspace', 'NG')
        other_id = other.id
        sess.commit()
    # Existing switch route uses a CSRF protected form.
    result = platform.client.post('/business/switch', data={'business_id': other_id,
        'csrf': csrf(platform.client, '/settings')})
    assert result.status_code == 303, result.text
    assert platform.client.get(path).status_code == 404
    for operation in ['/check', '/revoke']:
        assert platform.client.post(path + operation, data={'csrf': csrf(platform.client, '/business/sites')}).status_code == 404
    assert not calls


def test_revocation_during_network_cannot_publish_proof(platform, monkeypatch):
    user_id, business_id = owner(platform)
    claim_id = request_site(platform)
    def revoke():
        with platform.factory() as sess:
            SiteControlService(sess, mod.fernet).revoke(user_id, business_id, claim_id)
            sess.commit()
    calls = fixture_reader(monkeypatch, challenge(platform, claim_id), callback=revoke)
    path = '/business/sites/' + claim_id
    assert platform.client.post(path + '/check', data={'csrf': csrf(platform.client, path)}).status_code == 409
    assert len(calls) == 2
    with platform.factory() as sess:
        row = sess.get(SiteControlClaim, claim_id)
        assert row.status == 'revoked' and row.verified_at is None and row.token_cipher is None


def test_role_removal_during_network_cannot_publish_proof(platform, monkeypatch):
    user_id, business_id = owner(platform)
    claim_id = request_site(platform)
    def demote():
        with platform.factory() as sess:
            sess.get(Membership, (business_id, user_id)).role = 'analyst'
            sess.commit()
    fixture_reader(monkeypatch, challenge(platform, claim_id), callback=demote)
    path = '/business/sites/' + claim_id
    assert platform.client.post(path + '/check', data={'csrf': csrf(platform.client, path)}).status_code == 403
    with platform.factory() as sess:
        assert sess.get(SiteControlClaim, claim_id).verified_at is None


def test_challenge_idempotency_budgets_expiry_and_retention(platform):
    user_id, business_id = owner(platform)
    now = [10000.0]
    with platform.factory() as sess:
        service = SiteControlService(sess, mod.fernet, clock=lambda: now[0])
        nonce = secrets.token_urlsafe(24)
        row = service.create(user_id, business_id, 'fixture-studio.org', nonce)
        row_id = row.id
        assert service.create(user_id, business_id, 'fixture-studio.org', nonce).id == row_id
        assert service.create(user_id, business_id, 'fixture-studio.org', secrets.token_urlsafe(24)).id == row_id
        lease = service.begin_check(user_id, business_id, row_id)
        with pytest.raises(IdentityError, match='being checked'):
            service.begin_check(user_id, business_id, row_id)
        service.finish_check(user_id, business_id, lease, FileProof('0' * 64, '0' * 64))
        assert row.status == 'failed' and row.error_code == 'verification_mismatch'
        for attempt in range(4):
            now[0] += 61
            lease = service.begin_check(user_id, business_id, row_id)
            service.finish_check(user_id, business_id, lease, error_code='secret-provider-error')
            assert row.error_code == 'verification_fetch_failed'
        now[0] += 61
        with pytest.raises(IdentityError, match='five checks'):
            service.begin_check(user_id, business_id, row_id)
        service.revoke(user_id, business_id, row_id)
        assert service.create(user_id, business_id, 'fixture-studio.org', nonce).status == 'revoked'
        for host in ['two-fixture.org', 'three-fixture.org']:
            service.create(user_id, business_id, host, secrets.token_urlsafe(24))
        with pytest.raises(IdentityError, match='Too many new'):
            service.create(user_id, business_id, 'four-fixture.org', secrets.token_urlsafe(24))
        sess.commit()
        now[0] += 3601
        cleanup_expired(sess, now=now[0])
        pending = sess.scalars(select(SiteControlClaim).where(SiteControlClaim.id != row_id)).all()
        assert all(row.status == 'expired' and row.token_cipher is None for row in pending)
        assert effective_status(pending[0], now[0]) == 'expired'
        sess.commit()


def test_expired_or_superseded_lease_cannot_verify(platform):
    user_id, business_id = owner(platform)
    with platform.factory() as sess:
        now = [10000.0]
        service = SiteControlService(sess, mod.fernet, clock=lambda: now[0])
        row = service.create(user_id, business_id, 'fixture-studio.org', secrets.token_urlsafe(24))
        proof = FileProof(row.token_hash, '1' * 64)
        lease = service.begin_check(user_id, business_id, row.id)
        now[0] += 61
        new = service.begin_check(user_id, business_id, row.id)
        with pytest.raises(IdentityError, match='no longer current'):
            service.finish_check(user_id, business_id, lease, proof)
        now[0] += 3601
        with pytest.raises(IdentityError, match='no longer current'):
            service.finish_check(user_id, business_id, new, proof)
        assert effective_status(row, now[0]) == 'expired' and row.verified_at is None


def test_account_removal_revokes_pending_and_removes_exclusive_proofs(platform):
    user_id, business_id = owner(platform)
    request_site(platform)
    from ayo.account_deletion import remove_account
    with platform.factory() as sess:
        remove_account(sess, user_id, 'FixturePassword123!', 'DELETE')
        sess.commit()
        assert sess.scalar(select(func.count()).select_from(SiteControlClaim)) == 0
        assert sess.get(Business, business_id) is None


def test_pre_migration_site_page_fails_cleanly_without_blocking_existing_workspace(platform):
    user_id, business_id = owner(platform)
    SiteControlClaim.__table__.drop(bind=platform.engine)
    page = platform.client.get('/business/sites')
    assert page.status_code == 503 and 'hasn’t been applied' in page.text
    assert platform.client.get('/business').status_code == 200
    assert platform.client.get('/research/library').status_code == 200
    assert platform.client.get('/').status_code == 200
    from ayo.account_deletion import remove_account
    with platform.factory() as sess:
        cleanup_expired(sess)
        remove_account(sess, user_id, 'FixturePassword123!', 'DELETE')
        sess.commit()
        assert sess.get(Business, business_id) is None


def test_concurrent_creates_share_one_active_challenge(platform):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    user_id, business_id = owner(platform)
    barrier = Barrier(2)
    def create():
        with platform.factory() as sess:
            barrier.wait(timeout=10)
            row = SiteControlService(sess, mod.fernet).create(user_id, business_id,
                'fixture-studio.org', secrets.token_urlsafe(24))
            row_id = row.id
            sess.commit()
            return row_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        result = [future.result(timeout=15) for future in futures]
    assert result[0] == result[1]
    with platform.factory() as sess:
        assert sess.scalar(select(func.count()).select_from(SiteControlClaim)) == 1


def test_revoked_session_during_check_cannot_publish_proof(platform, monkeypatch):
    from ayo.models import AuthSession
    import time
    owner(platform)
    claim_id = request_site(platform)
    def revoke_session():
        with platform.factory() as sess:
            for row in sess.scalars(select(AuthSession)).all():
                row.revoked_at = time.time()
            sess.commit()
    fixture_reader(monkeypatch, challenge(platform, claim_id), callback=revoke_session)
    path = '/business/sites/' + claim_id
    assert platform.client.post(path + '/check', data={'csrf': csrf(platform.client, path)}).status_code == 403
    with platform.factory() as sess:
        assert sess.get(SiteControlClaim, claim_id).verified_at is None


@pytest.mark.parametrize('value', [
    'http://example.org', 'https://example.org/path', 'https://example.org/?x=1',
    'https://example.org/#fragment', 'https://example.org:444', 'https://user:pass@example.org',
    '127.0.0.1', '0x7f000001', 'metadata.google.internal', 'localhost',
    'https://[::1]', 'https://example.org\\@127.0.0.1', 'ftp://example.org', '', None,
])
def test_reject_invalid_site_origins(value):
    with pytest.raises(IdentityError):
        site_host(value)


def test_exact_host_normalization_never_conflates_aliases():
    assert site_host('WWW.Example.org') == 'www.example.org'
    assert site_host('https://example.org:443/') == 'example.org'
    assert site_host('shop.example.org') != site_host('example.org')
