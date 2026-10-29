"""Explicit queued worker commands; all source/model I/O is synthetic."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import secrets
import threading

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from ayo import app as mod
from ayo.jobs import process_one
from ayo.models import Membership, ResearchJob, ResearchReportRecord
from ayo.research import ResearchError, ResearchReport, ResearchService
from ayo.research_refresh import RefreshService
from test_platform_flow import platform, csrf, FixtureProvider  # noqa: F401
from test_research_workspace import account, saved, report


@pytest.fixture
def hosted(platform, monkeypatch):
    monkeypatch.setenv('AYO_ON_DEMAND_RESEARCH', '1')
    monkeypatch.setenv('AYO_ON_DEMAND_GEMINI_AUTHORIZED', '0')
    monkeypatch.setenv('AYO_RESEARCH_SOURCE', 'direct_public_web')
    calls = []

    class Provider(FixtureProvider):
        async def fetch(self, url, country=''):
            calls.append(url)
            return await super().fetch(url, country)

    monkeypatch.setattr(mod.app.state, 'research_factory', lambda: ResearchService(Provider()))
    return platform, calls


def queue(client, url='https://fixture-clothing.org/'):
    sent = client.post('/research', data={'csrf': csrf(client), 'query': url, 'country': 'GH'})
    assert sent.status_code == 303
    return sent.headers['location']


def payload(client, path):
    return {'csrf': csrf(client)}


def postgres(platform):
    return platform.engine.dialect.name == 'postgresql'


def test_exact_public_job_runs_once_without_models_and_publishes_a_real_saved_partial(hosted, monkeypatch):
    platform, calls = hosted
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as other:
        older_path = queue(other, 'https://foreign-fixture.org/')
    path = queue(platform.client)
    data = payload(platform.client, path)

    def no_model(*_args, **_kwargs):
        raise AssertionError('Source-only dispatch must not initialize any model provider')
    monkeypatch.setattr('ayo.public_intelligence.IntelligenceOrchestrator', no_model)
    for _ in range(3):
        assert platform.client.get(path + '/updates').status_code == 200
    assert calls == []
    result = platform.client.post(path + '/dispatch', data={**data, 'source_only': 'false'},
                                  headers={'Accept': 'application/json'})
    if not postgres(platform):
        assert result.status_code == 503 and calls == []
        return
    assert result.status_code == 200 and result.json() == {'processed': True}
    for _ in range(2):
        assert platform.client.post(path + '/dispatch', data=data,
            headers={'Accept': 'application/json'}).status_code == 202
    assert calls == ['https://fixture-clothing.org/']
    with platform.factory() as session:
        untouched = session.get(ResearchJob, older_path.rsplit('/', 1)[1])
        assert untouched.status == 'queued' and untouched.attempts == 0
        job = session.get(ResearchJob, path.rsplit('/', 1)[1])
        assert job.status == 'succeeded' and job.attempts == 1
        retained = session.get(ResearchReportRecord, job.report_id)
        value = ResearchReport.model_validate_json(retained.report_json)
        assert value.source_documents and value.analysis is None
        assert value.analysis_status == 'unavailable' and value.status == 'PARTIAL'
        assert value.analysis_error_code == 'model_not_authorized_for_on_demand'
    opened = platform.client.get(path)
    assert opened.status_code == 303
    page = platform.client.get(opened.headers['location'])
    assert page.status_code == 200 and 'partial research with source observations only' in page.text
    assert 'data-model-dispatch="none"' in page.text


def test_csrf_foreign_capability_and_configuration_never_dispatch(hosted, monkeypatch):
    platform, calls = hosted
    path = queue(platform.client)
    data = payload(platform.client, path)
    assert platform.client.post(path + '/dispatch', data={'csrf': 'wrong'}).status_code == 403
    with TestClient(mod.app, base_url='http://testserver') as other:
        assert other.post(path + '/dispatch', data={'csrf': csrf(other)}).status_code == 404
    for name, value in (('AYO_ON_DEMAND_RESEARCH', '0'), ('AYO_PROVIDER_SPEND_AUTHORIZED', '1'),
                        ('AYO_RESEARCH_SOURCE', 'firecrawl')):
        with monkeypatch.context() as scoped:
            scoped.setenv(name, value)
            assert platform.client.post(path + '/dispatch', data=data).status_code == 503
    assert calls == []
    with platform.factory() as session:
        assert session.scalar(select(ResearchJob)).attempts == 0


def test_source_denial_creates_no_fake_report_or_silent_retry(hosted, monkeypatch):
    platform, calls = hosted
    path = queue(platform.client)

    class Denied(FixtureProvider):
        async def fetch(self, url, country=''):
            calls.append(url)
            raise ResearchError('robots_denied', 'Fixture policy denies reading.', 403)
    monkeypatch.setattr(mod.app.state, 'research_factory', lambda: ResearchService(Denied()))
    data = payload(platform.client, path)
    result = platform.client.post(path + '/dispatch', data=data)
    if not postgres(platform):
        assert result.status_code == 503
        return
    assert result.status_code == 303
    again = platform.client.post(path + '/dispatch', data=data)
    assert again.status_code == 303 and len(calls) == 1
    with platform.factory() as session:
        job = session.scalar(select(ResearchJob))
        assert job.status == 'failed' and job.report_id is None and job.attempts == 1
    assert 'Keep the research moving.' in platform.client.get(path).text


def test_private_refresh_command_requires_current_writer_and_original_scope(hosted):
    platform, calls = hosted
    user, business = account(platform)
    original = saved(platform.factory, user, business, report())
    with platform.factory() as session:
        job = RefreshService(session, mod.fernet).request(user, business, original,
            request_id=secrets.token_urlsafe(24), reviewed=True)
        session.commit()
        job_id = job.id
    path = '/research/library/' + original + '/refresh/' + job_id
    data = payload(platform.client, path)
    assert platform.client.post('/research/jobs/' + job_id + '/dispatch', data=data).status_code == 404
    with platform.factory() as session:
        session.scalar(select(Membership).where(Membership.user_id == user)).role = 'analyst'
        session.commit()
    assert platform.client.post(path + '/dispatch', data=data).status_code == 403
    assert not calls
    with platform.factory() as session:
        session.scalar(select(Membership).where(Membership.user_id == user)).role = 'owner'
        session.commit()
    result = platform.client.post(path + '/dispatch', data=data)
    if not postgres(platform):
        assert result.status_code == 503
        return
    assert result.status_code == 303 and len(calls) == 1
    opened = platform.client.get(path)
    assert opened.status_code == 303 and opened.headers['location'] != '/research/library/' + original
    assert platform.client.get(opened.headers['location']).status_code == 200


def test_selected_nonexistent_job_never_falls_back_to_another_queued_job(hosted):
    platform, calls = hosted
    queue(platform.client)
    assert not asyncio.run(process_one(platform.factory, mod.fernet, mod.app.state.research_factory,
                                       selected_job_id='missing-job', source_only=True))
    assert calls == []


def test_concurrent_command_replay_has_one_source_dispatch(hosted, monkeypatch):
    platform, calls = hosted
    path = queue(platform.client)
    data = payload(platform.client, path)
    if not postgres(platform):
        assert platform.client.post(path + '/dispatch', data=data).status_code == 503
        return
    started, release = threading.Event(), threading.Event()

    class Slow(FixtureProvider):
        async def fetch(self, url, country=''):
            calls.append(url)
            started.set()
            await asyncio.to_thread(release.wait, 10)
            return await super().fetch(url, country)
    monkeypatch.setattr(mod.app.state, 'research_factory', lambda: ResearchService(Slow()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(lambda: platform.client.post(path + '/dispatch', data=data,
                                                        headers={'Accept': 'application/json'}))
        try:
            assert started.wait(5)
            second = platform.client.post(path + '/dispatch', data=data,
                                          headers={'Accept': 'application/json'})
            assert second.status_code == 202
        finally:
            release.set()
        assert first.result(timeout=15).status_code == 200
    assert len(calls) == 1
