"""Reviewed private refresh/version workflows; all source/model/mail I/O is fake."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import re
import secrets
import time
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ayo import app as mod
from ayo.account_deletion import remove_account
from ayo.identity import IdentityError
from ayo.jobs import process_one
from ayo.models import AuditEvent, Membership, ResearchJob, ResearchReportRecord
from ayo.research import ResearchError, ResearchReport, ResearchService
from ayo.research_refresh import RefreshService
from ayo.retention import cleanup_expired
from test_platform_flow import platform, csrf, register, verify_latest, FixtureProvider  # noqa: F401
from test_research_workspace import account, saved, report


def setup(platform):
    user, business = account(platform)
    original = saved(platform.factory, user, business, report())
    return user, business, original


def request_data(platform, original, **changes):
    path = '/research/library/' + original + '/refresh'
    page = platform.client.get(path)
    assert page.status_code == 200
    return {'csrf': re.search(r'name="csrf" value="([^"]+)"', page.text)[1],
            'request_id': re.search(r'name="request_id" value="([^"]+)"', page.text)[1],
            'reviewed': 'true', **changes}


class GeminiFixture:
    name, model = 'gemini', 'offline-reviewed-refresh-fixture'

    def __init__(self, callback=None):
        self.calls, self.callback = [], callback

    async def complete(self, _system, context):
        self.calls.append(context)
        if self.callback:
            self.callback(context)
        source_id = context['evidence'][0]['id']
        return {'claims': [{'text': 'The retained public product text may benefit from clearer descriptions.',
            'kind': 'INFERRED', 'quote': '', 'evidence_ids': [source_id]}],
            'recommendations': [], 'limitations': ['Offline refresh fixture; no real provider call.']}, {'totalTokenCount': 10}


def test_private_refresh_versions_replay_relogin_and_immutable_export(platform, monkeypatch):
    user, business, original_id = setup(platform)
    path = '/research/library/' + original_id
    original_export = platform.client.get(path + '/export').json()
    with platform.factory() as session:
        original_json = session.get(ResearchReportRecord, original_id).report_json
    data = request_data(platform, original_id)
    queued = platform.client.post(path + '/refresh', data=data)
    assert queued.status_code == 303
    job_path = queued.headers['location']
    job_id = job_path.rsplit('/', 1)[1]
    assert platform.client.post(path + '/refresh', data=data).headers['location'] == job_path
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(ResearchJob)) == 1
        job = session.get(ResearchJob, job_id)
        assert 'fixture' not in job.payload_cipher
        assert job.report_id is None and job.claim_cipher is None
    assert platform.client.get('/research/jobs/' + job_id).status_code == 404

    def inspect_pending(_context):
        with platform.factory() as session:
            job = session.get(ResearchJob, job_id)
            fresh = session.get(ResearchReportRecord, job.report_id)
            assert fresh.status == 'PENDING_ANALYSIS' and fresh.business_id == business
            assert fresh.owner_user_id == user and fresh.anonymous_session_hash is None
            assert fresh.expires_at is None
            assert session.get(ResearchReportRecord, original_id).report_json == original_json
        assert platform.client.get('/research/library/' + fresh.id).status_code == 404

    monkeypatch.setenv('AYO_AI_DATA_POLICY', 'public_only_reviewed')
    model = GeminiFixture(inspect_pending)
    assert asyncio.run(process_one(platform.factory, mod.fernet,
        lambda: ResearchService(FixtureProvider()), analysis_provider=model))
    assert len(model.calls) == 1 and 'business_id' not in model.calls[0]
    result = platform.client.get(job_path)
    assert result.status_code == 303 and result.headers['location'] != path
    new_path = result.headers['location']
    new_id = new_path.rsplit('/', 1)[1]
    assert platform.client.get(new_path).status_code == 200
    assert platform.client.get(path + '/export').json() == original_export
    with platform.factory() as session:
        assert session.get(ResearchReportRecord, original_id).report_json == original_json
        fresh = session.get(ResearchReportRecord, new_id)
        assert ResearchReport.model_validate_json(fresh.report_json).analysis_status == 'completed'
        assert fresh.business_id == business and fresh.owner_user_id == user
        assert session.get(ResearchJob, job_id).claim_cipher is None
        assert session.scalar(select(AuditEvent).where(AuditEvent.action == 'research.refresh_published')) is not None
        unchanged_new = fresh.report_json
    assert platform.client.post(path + '/refresh', data=data).headers['location'] == job_path
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as stranger:
        assert stranger.get('/research/' + new_id).status_code == 404
        register(stranger, 'other-refresh@example.org')
        assert verify_latest(stranger, platform.factory).status_code == 303
        assert stranger.get(new_path).status_code == 404 and stranger.get(job_path).status_code == 404
    assert platform.client.post('/logout', data={'csrf': csrf(platform.client, '/work')}).status_code == 303
    assert platform.client.post('/login', data={'csrf': csrf(platform.client, '/login'),
        'email': 'research-owner@example.org', 'password': 'FixturePassword123!'}).status_code == 303
    assert platform.client.get(job_path).headers['location'] == new_path
    assert platform.client.get(new_path + '/export').json()['report_id'] == new_id
    with platform.factory() as session:
        assert session.get(ResearchReportRecord, new_id).report_json == unchanged_new


@pytest.mark.parametrize('role', ['owner', 'admin', 'editor', 'analyst'])
def test_refresh_roles_review_and_csrf(platform, role):
    user, business, original = setup(platform)
    with platform.factory() as session:
        session.get(Membership, (business, user)).role = role
        session.commit()
    path = '/research/library/' + original + '/refresh'
    page = platform.client.get(path)
    if role == 'analyst':
        assert page.status_code == 403
        assert platform.client.post(path, data={'csrf': csrf(platform.client, '/work'),
            'request_id': secrets.token_urlsafe(24), 'reviewed': 'true'}).status_code == 403
        return
    data = request_data(platform, original)
    assert platform.client.post(path, data={**data, 'reviewed': 'false'}).status_code == 400
    assert platform.client.post(path, data={**data, 'csrf': 'wrong'}).status_code == 403
    assert platform.client.post(path, data={**data, 'request_id': 'short'}).status_code == 400
    assert platform.client.post(path, data=data).status_code == 303


@pytest.mark.parametrize('when', ['before_source', 'during_source', 'during_model'])
def test_revoked_permissions_never_publish_or_expose_staged_refresh(platform, monkeypatch, when):
    user, business, original = setup(platform)
    path = '/research/library/' + original
    queued = platform.client.post(path + '/refresh', data=request_data(platform, original))
    job_id = queued.headers['location'].rsplit('/', 1)[1]
    calls = []

    def revoke(*_args):
        with platform.factory() as session:
            session.get(Membership, (business, user)).role = 'analyst'
            session.commit()

    class Provider(FixtureProvider):
        async def fetch(self, url, country=''):
            calls.append(url)
            if when == 'during_source':revoke()
            return await super().fetch(url, country)

    if when == 'before_source':revoke()
    monkeypatch.setenv('AYO_AI_DATA_POLICY', 'public_only_reviewed')
    model = GeminiFixture(revoke if when == 'during_model' else None)
    assert asyncio.run(process_one(platform.factory, mod.fernet,
        lambda: ResearchService(Provider()), analysis_provider=model))
    assert len(calls) == (0 if when == 'before_source' else 1)
    assert len(model.calls) == (1 if when == 'during_model' else 0)
    with platform.factory() as session:
        job = session.get(ResearchJob, job_id)
        assert job.status == 'failed' and job.report_id is None and job.claim_cipher is None
        assert session.scalar(select(func.count()).select_from(ResearchReportRecord)) == 1
        assert session.get(ResearchReportRecord, original) is not None


def test_denied_source_creates_no_fake_version_and_replay_does_not_retry(platform):
    _, _, original = setup(platform)
    path = '/research/library/' + original + '/refresh'
    data = request_data(platform, original)
    queued = platform.client.post(path, data=data)
    job_id = queued.headers['location'].rsplit('/', 1)[1]
    calls = []

    class Denied:
        async def research(self, *_args, **_kwargs):
            calls.append(1)
            raise ResearchError('robots_denied', 'Fixture source denial', 403)

    assert asyncio.run(process_one(platform.factory, mod.fernet, Denied))
    assert platform.client.post(path, data=data).headers['location'] == queued.headers['location']
    assert not asyncio.run(process_one(platform.factory, mod.fernet, Denied))
    assert len(calls) == 1
    with platform.factory() as session:
        assert session.get(ResearchJob, job_id).error_code == 'robots_denied'
        assert session.scalar(select(func.count()).select_from(ResearchReportRecord)) == 1


def test_account_removal_erases_queued_private_refresh_ciphertext(platform):
    user, _, original = setup(platform)
    queued = platform.client.post('/research/library/' + original + '/refresh', data=request_data(platform, original))
    job_id = queued.headers['location'].rsplit('/', 1)[1]
    with platform.factory() as session:
        remove_account(session, user, 'FixturePassword123!', 'DELETE')
        session.commit()
    with platform.factory() as session:
        assert session.get(ResearchJob, job_id) is None
        assert session.scalar(select(AuditEvent).where(AuditEvent.resource_type == 'research_job', AuditEvent.resource_id == job_id)) is None


def test_crash_resumes_pending_refresh_without_refetch_and_retention_preserves_versions(platform, monkeypatch):
    _, _, original = setup(platform)
    queued = platform.client.post('/research/library/' + original + '/refresh', data=request_data(platform, original))
    job_id = queued.headers['location'].rsplit('/', 1)[1]
    monkeypatch.setenv('AYO_AI_DATA_POLICY', 'public_only_reviewed')

    def interrupt(_context):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(process_one(platform.factory, mod.fernet,
            lambda: ResearchService(FixtureProvider()), analysis_provider=GeminiFixture(interrupt)))
    with platform.factory() as session:
        job = session.get(ResearchJob, job_id)
        checkpoint = job.report_id
        job.lease_until = time.time() - 1
        session.commit()

    def no_refetch():
        raise AssertionError('Committed refresh evidence must not be fetched again.')

    assert asyncio.run(process_one(platform.factory, mod.fernet, no_refetch, analysis_provider=GeminiFixture()))
    with platform.factory() as session:
        job = session.get(ResearchJob, job_id)
        assert job.status == 'succeeded' and job.report_id == checkpoint
        cleanup_expired(session, now=time.time() + 86401)
        session.commit()
    with platform.factory() as session:
        assert session.get(ResearchJob, job_id) is None
        assert session.get(ResearchReportRecord, original) is not None
        assert session.get(ResearchReportRecord, checkpoint).status == 'PARTIAL'


def test_changed_reviewed_report_is_rejected_before_dispatch(platform):
    user, business, original = setup(platform)
    path = '/research/library/' + original + '/refresh'
    data = request_data(platform, original)
    queued = platform.client.post(path, data=data)
    job_id = queued.headers['location'].rsplit('/', 1)[1]
    # A corrupted/out-of-band edit must not silently reuse the earlier review.
    with platform.factory() as session:
        session.get(ResearchReportRecord, original).report_json = report(name='Changed fixture').model_dump_json()
        session.commit()
    assert platform.client.post(path, data=data).status_code == 409

    def no_dispatch():
        raise AssertionError('Changed evidence must be re-reviewed before fetching.')

    assert asyncio.run(process_one(platform.factory, mod.fernet, no_dispatch))
    with platform.factory() as session:
        assert session.get(ResearchJob, job_id).status == 'failed'
        assert session.scalar(select(func.count()).select_from(ResearchReportRecord)) == 1


def test_unverified_account_and_cross_report_job_access_are_denied(platform):
    user, business, original = setup(platform)
    queued = platform.client.post('/research/library/' + original + '/refresh', data=request_data(platform, original))
    job_id = queued.headers['location'].rsplit('/', 1)[1]
    other = saved(platform.factory, user, business, report(name='Different saved report'))
    assert platform.client.get('/research/library/' + other + '/refresh/' + job_id).status_code == 404
    from ayo.models import User
    with platform.factory() as session:
        session.get(User, user).email_verified_at = None
        session.commit()
    assert platform.client.get('/research/library/' + original + '/refresh').status_code == 403


def test_three_unique_refreshes_per_hour_and_replay_does_not_consume_more(platform):
    user, business, original = setup(platform)
    with platform.factory() as session:
        service = RefreshService(session, mod.fernet)
        first_key = secrets.token_urlsafe(24)
        first = service.request(user, business, original, request_id=first_key, reviewed=True)
        assert service.request(user, business, original, request_id=first_key, reviewed=True).id == first.id
        for _ in range(2):
            service.request(user, business, original, request_id=secrets.token_urlsafe(24), reviewed=True)
        session.commit()
        with pytest.raises(IdentityError) as error:
            service.request(user, business, original, request_id=secrets.token_urlsafe(24), reviewed=True)
        assert error.value.status_code == 429
        session.rollback()
        assert session.scalar(select(func.count()).select_from(ResearchJob)) == 3


def test_expired_interrupted_private_checkpoint_is_cleaned_without_deleting_original(platform, monkeypatch):
    _, _, original = setup(platform)
    queued = platform.client.post('/research/library/' + original + '/refresh', data=request_data(platform, original))
    job_id = queued.headers['location'].rsplit('/', 1)[1]
    monkeypatch.setenv('AYO_AI_DATA_POLICY', 'public_only_reviewed')

    def interrupt(_context):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(process_one(platform.factory, mod.fernet,
            lambda: ResearchService(FixtureProvider()), analysis_provider=GeminiFixture(interrupt)))
    with platform.factory() as session:
        checkpoint = session.get(ResearchJob, job_id).report_id
        assert session.get(ResearchReportRecord, checkpoint).status == 'PENDING_ANALYSIS'
        cleanup_expired(session, now=time.time() + 86401)
        session.commit()
    with platform.factory() as session:
        assert session.get(ResearchJob, job_id) is None
        assert session.get(ResearchReportRecord, checkpoint) is None
        assert session.get(ResearchReportRecord, original) is not None


def test_owner_provided_business_information_cannot_be_turned_into_a_crawl(platform):
    from ayo.merchant_evidence import MerchantInputDocument
    user, business = account(platform)
    text = 'An authorized synthetic business description, not a public website.'
    now = datetime.now(timezone.utc)
    source = MerchantInputDocument(id='input-fixture-owner', url='workspace:input:' + 'x' * 24,
        retrieved_at=now, source_hash=hashlib.sha256(text.encode()).hexdigest(), title='Supplied description',
        excerpt=text, content=text, provider_receipt_id='fixture-review', origin='merchant_form', input_field='description')
    supplied = ResearchReport(origin='merchant_provided', business_name='Supplied fixture', country='GH',
        target_url='workspace:merchant:' + 'x' * 24, status='PARTIAL', source_documents=(source,),
        claims=(), opportunities=(), limitations=('OWNER_PROVIDED_UNVERIFIED fixture.',), created_at=now)
    with platform.factory() as session:
        row = ResearchReportRecord(business_id=business, owner_user_id=user, title=supplied.business_name,
            country='GH', status='PARTIAL', target_url=supplied.target_url, report_json=supplied.model_dump_json())
        session.add(row)
        session.commit()
        report_id = row.id
    assert platform.client.get('/research/library/' + report_id + '/refresh').status_code == 400
    assert platform.client.post('/research/library/' + report_id + '/refresh', data={
        'csrf': csrf(platform.client, '/work'), 'request_id': secrets.token_urlsafe(24), 'reviewed': 'true'}).status_code == 400
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(ResearchJob)) == 0


def test_expired_form_tombstone_prevents_replaying_a_cleaned_job(platform):
    user, business, original = setup(platform)
    key = secrets.token_urlsafe(24)
    with platform.factory() as session:
        job = RefreshService(session, mod.fernet).request(user, business, original, request_id=key, reviewed=True)
        session.commit()
        cleanup_expired(session, now=time.time() + 86401)
        session.commit()
        assert session.get(ResearchJob, job.id) is None
        with pytest.raises(IdentityError) as error:
            RefreshService(session, mod.fernet).request(user, business, original, request_id=key, reviewed=True)
        assert error.value.code == 'refresh_expired'
        session.rollback()
        assert session.scalar(select(func.count()).select_from(ResearchJob)) == 0


def test_concurrent_duplicate_submissions_create_only_one_private_job(platform):
    user, business, original = setup(platform)
    barrier = threading.Barrier(2)
    key = secrets.token_urlsafe(24)

    def submit():
        with platform.factory() as session:
            barrier.wait(timeout=5)
            job = RefreshService(session, mod.fernet).request(user, business, original, request_id=key, reviewed=True)
            session.commit()
            return job.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        ids = [future.result(timeout=10) for future in futures]
    assert len(set(ids)) == 1
    with platform.factory() as session:
        assert session.scalar(select(func.count()).select_from(ResearchJob)) == 1
        assert len(session.scalars(select(AuditEvent).where(AuditEvent.action == 'research.refresh_requested')).all()) == 1
