"""End-to-end HTTP workflow with explicit, offline provider fixtures.

These tests verify application behavior, not a live business or vendor grant.
"""
import hashlib
from contextlib import nullcontext
import json
import os
import re
import secrets
import httpx
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from ayo import app as mod
from ayo.models import Base, FoundingGrant, Lead, MailOutbox, ReportClaim, ResearchJob, ResearchReportRecord, User
from ayo.research import BusinessCandidate, ResearchReport, ResearchService, SourceDocument
from ayo.provider_usage import OperationUsage
from ayo.database import make_engine


class FixtureProvider:
    async def search(self, query, country='', city='', limit=5):
        now = datetime.now(timezone.utc)
        return tuple(BusinessCandidate(id=str(i), name='Fixture Clothing Shop', url=url,
            snippet='Fixture online clothing boutique and wholesale business in Accra.',
            country=country, source_id='fixture-search-' + str(i), discovered_at=now,
            provider='offline-fixture') for i, url in enumerate([
                'https://fixture-clothing.org/', 'https://fixture-clothing.org/catalog']))

    async def fetch(self, url, country=''):
        text = 'Fixture Clothing Shop sells handmade clothing online. Delivery information is available on request.'
        return SourceDocument(id='fixture-source', url=url, retrieved_at=datetime.now(timezone.utc),
            source_hash=hashlib.sha256(text.encode()).hexdigest(), title='Fixture Clothing Shop',
            excerpt=text, content=text, provider='offline-fixture', provider_receipt_id='fixture-receipt')


@pytest.fixture(params=['sqlite', 'postgresql'])
def platform(request, tmp_path, monkeypatch):
    admin = None
    if request.param == 'postgresql':
        url = os.getenv('AYO_TEST_POSTGRES_URL')
        if not url:
            pytest.skip('Set AYO_TEST_POSTGRES_URL for real PostgreSQL workflow tests')
        admin = create_engine(url)
        schema = 'flow_' + secrets.token_hex(8)
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = admin.execution_options(schema_translate_map={None: schema})
    else:
        engine = make_engine('sqlite:///' + str(tmp_path / 'platform.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(mod, 'DbSession', factory)
    monkeypatch.setattr(mod.app.state, 'research_factory', lambda: ResearchService(FixtureProvider()))
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as client:
        yield SimpleNamespace(client=client, factory=factory, engine=engine)
    if admin:
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()
    else:
        engine.dispose()


def csrf(client, path='/'):
    response = client.get(path)
    assert response.status_code == 200, response.text
    return re.search(r'name="csrf" value="([^"]+)"', response.text).group(1)


def register(client, email):
    response = client.post('/signup', data={'csrf': csrf(client, '/signup'), 'email': email,
        'password': 'FixturePassword123!', 'business_name': 'Fixture merchant', 'country': 'GH'})
    assert response.status_code == 303, response.text


def verify_latest(client, factory):
    with factory() as sess:
        mail = sess.scalar(select(MailOutbox).where(MailOutbox.kind == 'verify_email').order_by(MailOutbox.id.desc()))
        payload = json.loads(mod.fernet.decrypt(mail.payload_cipher.encode()))
    link = urlsplit(payload['url'])
    return client.get(link.path + '?' + link.query)


def gemini_fixture(factory, country='GH'):
    """Actual REST adapter with OFFLINE HTTP; verify committed evidence first."""
    from ayo.identity import IdentityError
    from ayo.intelligence import GeminiProvider
    from ayo.report_storage import ReportStore

    def handler(request):
        assert request.url.host == 'generativelanguage.googleapis.com'
        payload = json.loads(json.loads(request.content)['contents'][0]['parts'][0]['text'])
        assert 'business_id' not in payload and payload['selected_market'] == country
        source = payload['evidence'][0]
        with factory() as session:
            job = session.scalar(select(ResearchJob).where(ResearchJob.status == 'running'))
            checkpoint = session.get(ResearchReportRecord, job.report_id)
            assert checkpoint.status == 'PENDING_ANALYSIS'
            stored = ResearchReport.model_validate_json(checkpoint.report_json)
            assert source['id'] == stored.source_documents[0].id
            assert source['excerpt'] in stored.source_documents[0].content
            assert session.scalar(select(ReportClaim)) is None
            anonymous_id = json.loads(mod.fernet.decrypt(job.payload_cipher.encode()))['anonymous_id']
            with pytest.raises(IdentityError):
                ReportStore(session).accessible(checkpoint.id, anonymous_id=anonymous_id)
        quote = 'Fixture Clothing Shop sells handmade clothing online.'
        analysis = {'claims': [{'text': quote, 'quote': quote, 'kind': 'OBSERVED',
                               'evidence_ids': [source['id']]}],
                    'recommendations': [{'text': 'Review delivery information clarity on product pages.',
                        'evidence_ids': [source['id']], 'permission_required': 'merchant_review'}],
                    'limitations': ['Offline fixture response; not a real Gemini call.']}
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP',
            'content': {'parts': [{'text': json.dumps(analysis)}]}}],
            'usageMetadata': {'promptTokenCount': 80, 'candidatesTokenCount': 60, 'totalTokenCount': 140}})
    return GeminiProvider('offline-fixture-key', 'offline-gemini-fixture', transport=httpx.MockTransport(handler),
                          dispatch_budget=lambda *_args: nullcontext(OperationUsage()))


@pytest.mark.parametrize('market', ['NG', 'GH'])
def test_search_report_register_verify_save_reopen_and_lead_discovery(platform, market):
    client, factory = platform.client, platform.factory
    response = client.post('/research', data={'query': 'Fixture clothing business', 'country': market, 'csrf': csrf(client)})
    assert response.status_code == 200 and 'Fixture Clothing Shop' in response.text
    response = client.post('/research/select', data={'url': 'https://fixture-clothing.org/', 'country': market,
        'business_name': 'Fixture Clothing Shop', 'csrf': csrf(client)})
    assert response.status_code == 303, response.text
    job_path = response.headers['location']
    assert 'queued' in client.get(job_path).text.lower()
    import asyncio
    from ayo.jobs import process_one
    assert asyncio.run(process_one(factory, mod.fernet, mod.app.state.research_factory,
                                  analysis_provider=gemini_fixture(factory, market)))
    finished = client.get(job_path)
    assert finished.status_code == 303
    report_path = finished.headers['location']
    public_report = client.get(report_path)
    assert 'Fixture Clothing Shop' in public_report.text and 'fixture-source' in public_report.text
    assert 'data-analysis-status="completed"' in public_report.text
    assert 'offline-gemini-fixture' in public_report.text
    claim = re.search(r'name="claim_token" value="([^"]+)"', public_report.text)
    # Anonymous CTAs lead to registration; the capability stays in the signed
    # HttpOnly session, then a verified account can consume it atomically.
    assert claim is None
    with TestClient(mod.app, base_url='http://testserver') as stranger:
        assert stranger.get(report_path).status_code == 404
    register(client, 'owner@example.org')
    with factory() as sess:
        assert sess.scalar(select(ResearchReportRecord)).business_id is None
        assert sess.scalar(select(FoundingGrant)).slot == 1
    assert verify_latest(client, factory).status_code == 303
    home = client.get('/dashboard')
    assert home.status_code == 200 and 'Fixture Clothing Shop' in home.text
    saved = client.get(report_path)
    assert saved.status_code == 200 and 'Part of your business memory' in saved.text
    assert 'offline-gemini-fixture' in saved.text
    with factory() as sess:
        report = ResearchReport.model_validate_json(sess.scalar(select(ResearchReportRecord)).report_json)
        assert report.analysis_status == 'completed' and report.analysis.provider == 'gemini'
        assert report.analysis.usage['totalTokenCount'] == 140
    response = client.post('/leads/discover', data={'csrf': csrf(client, '/dashboard'),
        'query': 'clothing boutiques', 'country': 'GH', 'city': 'Accra'})
    assert response.status_code == 303, response.text
    assert 'Fixture Clothing Shop' in client.get('/leads').text
    client.post('/leads/discover', data={'csrf': csrf(client, '/dashboard'),
        'query': 'clothing boutiques', 'country': 'GH', 'city': 'Accra'})
    with factory() as sess:
        rows = sess.scalars(select(Lead)).all()
        assert len(rows) == 1 and rows[0].status == 'discovered'
        assert 'fixture-search' in rows[0].evidence_json
        assert sess.scalar(select(User)).email_verified_at is not None
        lead_id = rows[0].id
    assert client.post('/leads/' + lead_id + '/qualify', data={
        'csrf': csrf(client, '/dashboard'), 'note': 'Source describes a clothing boutique matching the offer.'}).status_code == 303
    assert 'Qualified' in client.get('/leads').text
    assert client.post('/leads/' + lead_id + '/qualify', data={
        'csrf': csrf(client, '/dashboard'), 'note': 'Repeated review'}).status_code == 409
    # A second account cannot access the first report or prospects, even with a
    # known report URL. It receives its own workspace and entitlement.
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as other:
        register(other, 'other@example.org')
        assert other.get(report_path).status_code == 404
        assert 'Fixture Clothing Shop' not in other.get('/leads').text
        assert other.post('/leads/' + lead_id + '/qualify', data={
            'csrf': csrf(other, '/dashboard'), 'note': 'Unauthorized review'}).status_code == 404
    # Database-backed sessions are revoked server-side, including captured cookies.
    cookie = client.cookies.get('ayo_session')
    assert client.post('/logout', data={'csrf': csrf(client, '/dashboard')}).status_code == 303
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as replay:
        replay.cookies.set('ayo_session', cookie)
        assert replay.get('/dashboard').status_code == 303
    token = csrf(client, '/login')
    assert client.post('/login', data={'csrf': token, 'email': 'owner@example.org', 'password': 'FixturePassword123!'}).status_code == 303
    reopened = client.get(report_path)
    assert reopened.status_code == 200 and 'offline-gemini-fixture' in reopened.text


def test_claim_rejects_other_browser_expiry_and_replay(platform):
    import asyncio
    from ayo.identity import IdentityError, IdentityService
    from ayo.report_storage import ReportStore
    report = asyncio.run(ResearchService(FixtureProvider()).research('https://fixture-clothing.org/', country='GH'))
    with platform.factory() as sess:
        identity = IdentityService(sess)
        account = identity.register('verified@example.org', 'FixturePassword123!', 'Fixture merchant', 'GH')
        identity.consume_verification(account.verification_token)
        record, raw = ReportStore(sess).save_preview(report, 'a' * 48)
        sess.commit()
        for anon in ['b' * 48, '']:
            with pytest.raises(IdentityError):
                ReportStore(sess).claim(raw, anon, account.user.id, account.business.id)
            sess.rollback()
        with pytest.raises(IdentityError):
            ReportStore(sess, clock=lambda: time_after(record.created_at)).claim(raw, 'a' * 48, account.user.id, account.business.id)
        sess.rollback()
        ReportStore(sess).claim(raw, 'a' * 48, account.user.id, account.business.id)
        sess.commit()
        with pytest.raises(IdentityError):
            ReportStore(sess).claim(raw, 'a' * 48, account.user.id, account.business.id)


def time_after(created):
    return created + 1801


def test_workspace_switch_is_membership_scoped_and_does_not_consume_founder_slot(platform):
    from ayo.models import Business, Membership
    client = platform.client
    register(client, 'multi@example.org')
    assert client.post('/business/setup', data={'csrf': csrf(client, '/dashboard'),
        'business_name': 'Second fixture business', 'country': 'NG'}).status_code == 303
    assert 'Second fixture business' in client.get('/dashboard').text
    assert 'NGN' in client.get('/settings').text
    with platform.factory() as sess:
        assert len(sess.scalars(select(FoundingGrant)).all()) == 1
        first = sess.scalar(select(Business).where(Business.name == 'Fixture merchant'))
        first_id = first.id
    assert client.post('/business/switch', data={'csrf': csrf(client, '/dashboard'), 'business_id': first_id}).status_code == 303
    assert 'GHS' in client.get('/settings').text
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as other:
        register(other, 'foreign@example.org')
        assert other.post('/business/switch', data={'csrf': csrf(other, '/dashboard'), 'business_id': first_id}).status_code == 403


def test_http_password_recovery_revokes_old_sessions_and_rejects_replay(platform):
    client = platform.client
    register(client, 'recover@example.org')
    assert verify_latest(client, platform.factory).status_code == 303
    captured = client.cookies.get('ayo_session')
    response = client.post('/forgot-password', data={'csrf': csrf(client, '/forgot-password'), 'email': 'recover@example.org'})
    assert response.status_code == 200 and 'queued' in response.text
    with platform.factory() as sess:
        mail = sess.scalar(select(MailOutbox).where(MailOutbox.kind == 'reset_password'))
        raw_url = json.loads(mod.fernet.decrypt(mail.payload_cipher.encode()))['url']
    parsed = urlsplit(raw_url)
    from urllib.parse import parse_qs
    token = parse_qs(parsed.query)['token'][0]
    page = client.get(parsed.path + '?' + parsed.query)
    assert page.headers['referrer-policy'] == 'no-referrer'
    csrf_value = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    assert client.post('/reset-password', data={'csrf': csrf_value, 'token': token, 'password': 'ChangedFixturePassword123!'}).status_code == 303
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as stale:
        stale.cookies.set('ayo_session', captured)
        assert stale.get('/dashboard').status_code == 303
    assert client.post('/login', data={'csrf': csrf(client, '/login'), 'email': 'recover@example.org', 'password': 'ChangedFixturePassword123!'}).status_code == 303
    assert client.post('/reset-password', data={'csrf': csrf(client, '/dashboard'), 'token': token, 'password': 'AnotherFixturePassword123!'}).status_code == 400


def test_local_account_removal_revokes_sessions_and_preserves_nonreusable_slot(platform):
    from ayo.models import AuthSession, Business, Membership
    client = platform.client
    register(client, 'delete-fixture@example.org')
    captured = client.cookies.get('ayo_session')
    assert client.post('/security/delete', data={'csrf': csrf(client, '/dashboard'),
        'password': 'wrong password', 'confirmation': 'DELETE'}).status_code == 403
    assert client.post('/security/delete', data={'csrf': csrf(client, '/dashboard'),
        'password': 'FixturePassword123!', 'confirmation': 'DELETE'}).status_code == 303
    with platform.factory() as sess:
        user = sess.scalar(select(User))
        assert user.disabled_at is not None and user.email != 'delete-fixture@example.org'
        assert sess.scalar(select(AuthSession)) is None
        assert sess.scalar(select(Membership)) is None
        assert sess.scalar(select(Business)) is None
        assert sess.scalar(select(MailOutbox)) is None
        assert sess.scalar(select(FoundingGrant)).slot == 1
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as stale:
        stale.cookies.set('ayo_session', captured)
        assert stale.get('/dashboard').status_code == 303
