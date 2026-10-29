"""Offline HTTP transports + real databases; no provider billing/live claims."""
import asyncio
import json
import os
import secrets
import time

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from ayo.budgets import BudgetError
from ayo.intelligence import GeminiProvider, IntelligenceError
from ayo.models import Base, ProviderBudgetAccount, ProviderUsageReservation
from ayo.provider_usage import budget_context
from ayo.research import FirecrawlProvider, ResearchError


def configure(monkeypatch, *, calls=4, amount=100):
    # Artificial numbers exercise authorization arithmetic, never vendor rates.
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED', '1')
    monkeypatch.setenv('AYO_REQUEST_BUDGET_MICROUSD', str(amount))
    monkeypatch.setenv('AYO_REQUEST_CALL_LIMIT', str(calls))
    for key, value in {'GEMINI_MODEL': 'offline-model', 'AYO_GEMINI_BUDGET_MODEL': 'offline-model',
            'AYO_GEMINI_BUDGET_MAX_INPUT_BYTES': '32768', 'AYO_GEMINI_BUDGET_MAX_OUTPUT_TOKENS': '1500',
            'AYO_GEMINI_BUDGET_THINKING_LEVEL': 'provider_default', 'GEMINI_THINKING_LEVEL': ''}.items():
        monkeypatch.setenv(key, value)
    for provider, operations in [('GEMINI', ('ANALYZE',)), ('FIRECRAWL', ('SEARCH', 'FETCH'))]:
        for suffix, value in [('DAILY_BUDGET_MICROUSD', '1000'), ('DAILY_CALL_LIMIT', '100'),
                ('SCOPE_DAILY_BUDGET_MICROUSD', '1000'), ('SCOPE_DAILY_CALL_LIMIT', '100'),
                ('BUDGET_POLICY_VERSION', 'offline-fixture-v1'),
                ('BUDGET_POLICY_VALID_UNTIL', str(int(time.time()) + 3600))]:
            monkeypatch.setenv(f'AYO_{provider}_{suffix}', value)
        for operation in operations:
            monkeypatch.setenv(f'AYO_{provider}_{operation}_RESERVATION_MICROUSD', '10')


@pytest.fixture(params=['sqlite', 'postgresql'])
def store(request, tmp_path):
    admin = None
    if request.param == 'postgresql':
        url = os.getenv('AYO_TEST_POSTGRES_URL')
        if not url:
            pytest.skip('Set AYO_TEST_POSTGRES_URL for actual PostgreSQL integration checks')
        admin = create_engine(url)
        schema = 'usage_' + secrets.token_hex(8)
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = admin.execution_options(schema_translate_map={None: schema})
    else:
        engine = create_engine('sqlite:///' + str(tmp_path / 'usage.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    if admin:
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
    else:
        engine.dispose()


def gemini(handler):
    return GeminiProvider('offline-key', 'offline-model', transport=httpx.MockTransport(handler))


def firecrawl(handler):
    return FirecrawlProvider('offline-key', spend_authorized=True, egress_policy_verified=True,
        approved_hosts=('fixture.org',), transport=httpx.MockTransport(handler), poll_interval=0)


def response():
    return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {
        'parts': [{'text': '{"claims":[],"recommendations":[],"limitations":[]}'}]}}],
        'usageMetadata': {'totalTokenCount': 22, 'thoughtsTokenCount': 5, 'promptTokenCount': True,
                          'cachedContentTokenCount': 4, 'private_body': 'never persist'}})


@pytest.mark.parametrize('provider', ['gemini', 'firecrawl'])
def test_unscoped_dispatch_is_denied_before_network(provider):
    calls = []
    def unexpected(request):
        calls.append(request)
        raise AssertionError('An unscoped dispatch reached HTTP')
    with pytest.raises((IntelligenceError, ResearchError)) as error:
        if provider == 'gemini':
            asyncio.run(gemini(unexpected).complete('policy', {}))
        else:
            asyncio.run(firecrawl(unexpected).search('Fixture business', 'NG'))
    assert error.value.code == 'budget_not_configured' and calls == []


def test_reservation_commits_before_http_and_request_cap_blocks_second_dispatch(store, monkeypatch):
    configure(monkeypatch, calls=1)
    calls = []
    def handle(request):
        calls.append(request)
        with store() as session:
            rows = session.scalars(select(ProviderUsageReservation)).all()
            assert len(rows) == 1 and rows[0].outcome == 'reserved'
            assert all(account.reserved_microusd == 10 for account in session.scalars(select(ProviderBudgetAccount)))
        return response()
    with budget_context(store, scope_id='business:one', request_id='request-one'):
        raw, usage = asyncio.run(gemini(handle).complete('policy', {}))
        assert usage == {'totalTokenCount': 22, 'thoughtsTokenCount': 5, 'cachedContentTokenCount': 4}
        with pytest.raises(IntelligenceError) as error:
            asyncio.run(gemini(handle).complete('policy', {}))
        assert error.value.code == 'budget_exceeded'
    assert len(calls) == 1
    with store() as session:
        row = session.scalar(select(ProviderUsageReservation))
        assert row.outcome == 'succeeded' and row.reserved_microusd == 10
        assert json.loads(row.usage_json) == {**usage, 'http_status': 200}
        assert 'private_body' not in row.usage_json


@pytest.mark.parametrize('failure', ['timeout', 'cancelled', 'malformed'])
def test_uncertain_dispatch_holds_budget_and_stable_resume_never_reissues(store, monkeypatch, failure):
    configure(monkeypatch)
    calls = []
    def handle(request):
        calls.append(request)
        if failure == 'timeout':
            raise httpx.ReadTimeout('offline timeout', request=request)
        if failure == 'cancelled':
            raise asyncio.CancelledError()
        return httpx.Response(200, content=b'not valid JSON')
    with budget_context(store, scope_id='anonymous:one', request_id='job-one', dispatch_prefix='job-one'):
        with pytest.raises((IntelligenceError, asyncio.CancelledError)):
            asyncio.run(gemini(handle).complete('policy', {}))
    with budget_context(store, scope_id='anonymous:one', request_id='job-one', dispatch_prefix='job-one'):
        with pytest.raises(IntelligenceError) as error:
            asyncio.run(gemini(handle).complete('policy', {}))
        assert error.value.code == 'dispatch_already_reserved'
    assert len(calls) == 1
    with store() as session:
        row = session.scalar(select(ProviderUsageReservation))
        assert row.outcome == 'uncertain' and row.reserved_microusd == 10
        assert all(account.reserved_microusd == 10 for account in session.scalars(select(ProviderBudgetAccount)))


def test_search_fetch_and_model_share_request_cap_but_polling_uses_no_new_reservation(store, monkeypatch):
    configure(monkeypatch, calls=2)
    calls = []
    def handle(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith('/search'):
            return httpx.Response(200, json={'success': True, 'data': {'web': [{
                'title': 'Offline fixture merchant', 'url': 'https://fixture.org/',
                'description': 'Offline fixture business publicly lists handmade clothing and delivery information.'}]}})
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'offline-crawl-1234'})
        return httpx.Response(200, json={'status': 'completed', 'data': [{
            'markdown': 'Offline fixture merchant sells handmade clothing and publishes delivery terms.',
            'metadata': {'statusCode': 200, 'sourceURL': 'https://fixture.org/'}}]})
    with budget_context(store, scope_id='anonymous:one', request_id='journey-one', dispatch_prefix='search'):
        assert asyncio.run(firecrawl(handle).search('Fixture merchant', 'GH'))
    with budget_context(store, scope_id='anonymous:one', request_id='journey-one', dispatch_prefix='job'):
        assert asyncio.run(firecrawl(handle).fetch('https://fixture.org/', 'GH'))
        with pytest.raises(IntelligenceError) as error:
            asyncio.run(gemini(lambda _: pytest.fail('Request cap must prevent Gemini HTTP')).complete('policy', {}))
        assert error.value.code == 'budget_exceeded'
    assert calls == [('POST', '/v2/search'), ('POST', '/v2/crawl'), ('GET', '/v2/crawl/offline-crawl-1234')]
    with store() as session:
        rows = session.scalars(select(ProviderUsageReservation)).all()
        assert len(rows) == 2 and {row.provider for row in rows} == {'firecrawl'}
        assert len({row.request_hash for row in rows}) == 1
        assert {row.operation for row in rows} == {'search', 'fetch'}


def test_invalid_or_expired_policy_fails_before_http(store, monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv('AYO_GEMINI_BUDGET_POLICY_VALID_UNTIL', '1')
    with budget_context(store, scope_id='anonymous:one', request_id='one'):
        with pytest.raises(IntelligenceError) as error:
            asyncio.run(gemini(lambda _: pytest.fail('Expired budget reached HTTP')).complete('policy', {}))
        assert error.value.code == 'budget_policy_expired'
    with store() as session:
        assert session.scalar(select(ProviderUsageReservation)) is None


def test_budget_storage_failure_blocks_dispatch_with_sanitized_error(monkeypatch):
    from sqlalchemy.exc import OperationalError
    configure(monkeypatch)
    def unavailable():
        raise OperationalError('credential-bearing SQL must not be shown', {}, Exception('upstream secret'))
    with budget_context(unavailable, scope_id='anonymous:one', request_id='one'):
        with pytest.raises(IntelligenceError) as error:
            asyncio.run(gemini(lambda _: pytest.fail('Unavailable ledger reached HTTP')).complete('policy', {}))
        assert error.value.code == 'budget_storage_unavailable'
        assert 'upstream secret' not in str(error.value) and 'credential-bearing' not in str(error.value)


@pytest.mark.parametrize('inner', [False, True])
def test_deeply_nested_provider_json_has_a_bounded_safe_failure(inner):
    from contextlib import nullcontext
    from ayo.provider_usage import OperationUsage
    nested = '{"nested":' + '[' * 10000 + '0' + ']' * 10000 + '}'
    if inner:
        body = json.dumps({'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': nested}]}}]})
    else:
        body = nested
    adapter = GeminiProvider('offline-key', 'offline-model',
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=body)),
        dispatch_budget=lambda *_: nullcontext(OperationUsage()))
    with pytest.raises(IntelligenceError) as error:
        asyncio.run(adapter.complete('policy', {}))
    assert error.value.code == ('invalid_model_output' if inner else 'provider_failure')


@pytest.mark.parametrize('store', ['postgresql'], indirect=True)
def test_postgresql_budget_lock_wait_is_bounded_before_network(store, monkeypatch):
    configure(monkeypatch)
    # Initialize the lock row in a committed operation, then hold it elsewhere.
    with budget_context(store, scope_id='business:one', request_id='initialize'):
        asyncio.run(gemini(lambda _: response()).complete('policy', {}))
    from ayo.models import ProviderBudgetLock
    with store() as blocker:
        blocker.scalar(select(ProviderBudgetLock).where(ProviderBudgetLock.id == 1).with_for_update())
        started = time.monotonic()
        with budget_context(store, scope_id='business:one', request_id='blocked'):
            with pytest.raises(IntelligenceError) as error:
                asyncio.run(gemini(lambda _: pytest.fail('Locked budget admission reached HTTP')).complete('policy', {}))
            assert error.value.code == 'budget_storage_unavailable'
        assert time.monotonic() - started < 6
        blocker.rollback()


def test_lost_gemini_worker_reuses_sources_without_a_second_billed_dispatch(store, monkeypatch):
    from cryptography.fernet import Fernet
    from ayo.jobs import enqueue, process_one
    from ayo.models import ResearchJob, ResearchReportRecord
    from ayo.research import ResearchReport, build_report, SourceDocument
    from datetime import datetime, timezone
    import hashlib
    configure(monkeypatch)
    fernet = Fernet(Fernet.generate_key())
    with store() as session:
        job = enqueue(session, fernet, url='https://fixture.org/', country='NG',
                      business_name='Offline fixture', anonymous_id='a' * 48)
        session.commit()
        job_id = job.id
    text = 'Offline fixture merchant sells handmade clothing with public delivery terms.'
    class Evidence:
        async def research(self, url, country='', business_name=''):
            return build_report(SourceDocument(id='offline-page', url=url,
                retrieved_at=datetime.now(timezone.utc), source_hash=hashlib.sha256(text.encode()).hexdigest(),
                title='Offline fixture', excerpt=text, content=text, provider='offline-fixture',
                provider_receipt_id='offline-receipt'), country=country, business_name=business_name)
    calls = []
    def interrupted(request):
        calls.append(request)
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(process_one(store, fernet, Evidence, analysis_provider=gemini(interrupted)))
    with store() as session:
        job = session.get(ResearchJob, job_id)
        checkpoint = session.get(ResearchReportRecord, job.report_id).report_json
        job.lease_until = time.time()-1
        session.commit()
    def no_recrawl():
        raise AssertionError('Committed source must not be fetched again')
    assert asyncio.run(process_one(store, fernet, no_recrawl, analysis_provider=gemini(interrupted)))
    with store() as session:
        job = session.get(ResearchJob, job_id)
        report = ResearchReport.model_validate_json(session.get(ResearchReportRecord, job.report_id).report_json)
        original = ResearchReport.model_validate_json(checkpoint)
        assert report.source_documents == original.source_documents and report.analysis is None
        assert report.analysis_error_code == 'model_dispatch_already_reserved'
        assert job.status == 'succeeded' and job.attempts == 2
        assert len(session.scalars(select(ProviderUsageReservation)).all()) == 1
    assert len(calls) == 1
