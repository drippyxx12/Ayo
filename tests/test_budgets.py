"""Real database budget guarantees; provider prices and usage are offline fixtures."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
import secrets

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from ayo.budgets import BudgetError, BudgetPolicy, UsageLedger
from ayo.models import Base, ProviderBudgetAccount, ProviderUsageReservation
from ayo.provider_config import MODEL_INPUT_MAX_BYTES, model_budget_fingerprint


NOW = 1_800_000_000


def policy(**changes):
    values = dict(provider='gemini', operation='analyze', reservation_microusd=10,
        request_limit_microusd=100, provider_daily_limit_microusd=100,
        scope_daily_limit_microusd=100, request_call_limit=10,
        provider_daily_call_limit=10, scope_daily_call_limit=10,
        policy_version='offline-fixture-v1', policy_valid_until=NOW + 86400 * 3)
    return BudgetPolicy(**{**values, **changes})


def config():
    """Artificial numbers test arithmetic, not current vendor prices."""
    return {
        'AYO_REQUEST_BUDGET_MICROUSD': '100', 'AYO_REQUEST_CALL_LIMIT': '10',
        'AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD': '10',
        'AYO_GEMINI_DAILY_BUDGET_MICROUSD': '100', 'AYO_GEMINI_DAILY_CALL_LIMIT': '10',
        'AYO_GEMINI_SCOPE_DAILY_BUDGET_MICROUSD': '100', 'AYO_GEMINI_SCOPE_DAILY_CALL_LIMIT': '10',
        'AYO_GEMINI_BUDGET_POLICY_VERSION': 'offline-fixture-v1',
        'AYO_GEMINI_BUDGET_POLICY_VALID_UNTIL': str(NOW + 86400),
        'GEMINI_MODEL': 'offline-model', 'AYO_GEMINI_BUDGET_MODEL': 'offline-model',
        'AYO_GEMINI_BUDGET_MAX_INPUT_BYTES': '32768', 'AYO_GEMINI_BUDGET_MAX_OUTPUT_TOKENS': '1500',
        'AYO_GEMINI_BUDGET_THINKING_LEVEL': 'provider_default',
    }


@pytest.fixture(params=['sqlite', 'postgresql'])
def database(request, tmp_path):
    admin = None
    if request.param == 'postgresql':
        url = os.getenv('AYO_TEST_POSTGRES_URL')
        if not url:
            pytest.skip('Set AYO_TEST_POSTGRES_URL for real PostgreSQL budget tests')
        admin = create_engine(url)
        schema = 'budget_' + secrets.token_hex(8)
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        engine = admin.execution_options(schema_translate_map={None: schema})
    else:
        engine = create_engine('sqlite:///' + str(tmp_path / 'budgets.db'),
            connect_args={'check_same_thread': False, 'timeout': 30})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    if admin:
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
    else:
        engine.dispose()


def reserve(ledger, dispatch_id='one', *, scope_id='anonymous.hash', request_id='request.one', **changes):
    return ledger.reserve(scope_id=scope_id, request_id=request_id, dispatch_id=dispatch_id, policy=policy(**changes))


def test_offline_policy_configuration_is_strict_and_expiring():
    assert BudgetPolicy.from_env('gemini', 'analyze', environ=config(), clock=lambda: NOW) == replace(policy(), policy_valid_until=NOW + 86400,
        configuration_fingerprint=model_budget_fingerprint('gemini', 'offline-model', MODEL_INPUT_MAX_BYTES, 1500))
    for key, value in [('AYO_REQUEST_CALL_LIMIT', '0'), ('AYO_REQUEST_BUDGET_MICROUSD', '-1'),
        ('AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD', '1.5'),
        ('AYO_GEMINI_BUDGET_POLICY_VERSION', 'unreviewed\ntext'),
        ('AYO_GEMINI_SCOPE_DAILY_BUDGET_MICROUSD', '9')]:
        invalid = {**config(), key: value}
        with pytest.raises(BudgetError, match='configuration') as error:
            BudgetPolicy.from_env('gemini', 'analyze', environ=invalid, clock=lambda: NOW)
        assert error.value.code == 'budget_not_configured'
    with pytest.raises(BudgetError) as missing:
        BudgetPolicy.from_env('gemini', 'analyze', environ={}, clock=lambda: NOW)
    assert missing.value.code == 'budget_not_configured'
    with pytest.raises(BudgetError) as expired:
        BudgetPolicy.from_env('gemini', 'analyze', environ=config(), clock=lambda: NOW + 86400)
    assert expired.value.code == 'budget_policy_expired'


def test_reservation_commits_before_dispatch_and_survives_new_ledger(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    result = reserve(ledger)
    assert result.dispatched_now
    with database() as session:
        row = session.get(ProviderUsageReservation, result.id)
        assert row.outcome == 'reserved' and row.reserved_microusd == 10
        assert len(session.scalars(select(ProviderBudgetAccount)).all()) == 3
        assert row.scope_hash != 'anonymous.hash'
        assert row.request_hash != 'request.one'
    duplicate = reserve(UsageLedger(database, clock=lambda: NOW))
    assert duplicate.id == result.id and not duplicate.dispatched_now


def test_same_dispatch_never_reauthorizes_even_after_settlement(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    first = reserve(ledger)
    ledger.settle(first.id, outcome='succeeded', usage={'input_tokens': 12})
    assert not reserve(ledger).dispatched_now
    with pytest.raises(BudgetError) as error:
        reserve(ledger, provider='claude')
    assert error.value.code == 'duplicate_dispatch_mismatch'
    with database() as session:
        assert len(session.scalars(select(ProviderUsageReservation)).all()) == 1
        assert {row.calls for row in session.scalars(select(ProviderBudgetAccount))} == {1}


def test_request_cost_limit_is_shared_across_providers_and_rolls_back_denial(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    reserve(ledger, 'source-search', provider='firecrawl', operation='search', request_limit_microusd=15)
    with pytest.raises(BudgetError) as error:
        reserve(ledger, 'model-analyze', request_limit_microusd=15)
    assert error.value.code == 'budget_exceeded'
    with database() as session:
        assert len(session.scalars(select(ProviderUsageReservation)).all()) == 1
        assert len(session.scalars(select(ProviderBudgetAccount)).all()) == 3
        assert {row.reserved_microusd for row in session.scalars(select(ProviderBudgetAccount))} == {10}


def test_request_call_limit_cannot_be_bypassed_by_another_provider(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    reserve(ledger, 'search', provider='firecrawl', operation='search', request_call_limit=1)
    with pytest.raises(BudgetError) as error:
        reserve(ledger, 'analyze', request_call_limit=1)
    assert error.value.code == 'budget_exceeded'


def test_provider_daily_limit_covers_all_scopes_and_requests(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    reserve(ledger, scope_id='user.one', provider_daily_limit_microusd=10)
    with pytest.raises(BudgetError) as error:
        reserve(ledger, scope_id='user.two', request_id='request.two', provider_daily_limit_microusd=10)
    assert error.value.code == 'budget_exceeded'


def test_scope_daily_money_limit_covers_new_requests_and_dispatches(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    reserve(ledger, scope_daily_limit_microusd=10)
    with pytest.raises(BudgetError) as error:
        reserve(ledger, 'next', request_id='new.request', scope_daily_limit_microusd=10)
    assert error.value.code == 'budget_exceeded'
    assert reserve(ledger, scope_id='another.scope', scope_daily_limit_microusd=10).dispatched_now


def test_provider_daily_call_cap_and_scope_caps_are_independent(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    reserve(ledger, scope_id='user.one', provider_daily_call_limit=1)
    with pytest.raises(BudgetError) as global_cap:
        reserve(ledger, scope_id='user.two', request_id='request.two', provider_daily_call_limit=1)
    assert global_cap.value.code == 'budget_exceeded'
    # A separate provider has separate global and per-scope counters.
    reserve(ledger, 'search', provider='firecrawl', operation='search', scope_daily_call_limit=1)
    with pytest.raises(BudgetError) as scope_cap:
        reserve(ledger, 'fetch', request_id='request.two', provider='firecrawl', operation='fetch', scope_daily_call_limit=1)
    assert scope_cap.value.code == 'budget_exceeded'
    reserve(ledger, 'search', scope_id='user.two', request_id='request.three', provider='firecrawl', operation='search', scope_daily_call_limit=1)


def test_active_caps_cannot_change_silently_and_denied_transaction_does_not_debit(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    reserve(ledger)
    for changed in ({'request_limit_microusd': 200}, {'provider_daily_call_limit': 11},
                    {'scope_daily_limit_microusd': 200}):
        with pytest.raises(BudgetError) as error:
            reserve(ledger, 'two', **changed)
        assert error.value.code == 'budget_policy_changed'
    with database() as session:
        assert {row.calls for row in session.scalars(select(ProviderBudgetAccount))} == {1}


@pytest.mark.parametrize('outcome', ['failed', 'uncertain', 'succeeded'])
def test_every_outcome_holds_full_debit_and_sanitizes_usage(database, outcome):
    ledger = UsageLedger(database, clock=lambda: NOW)
    result = reserve(ledger, request_limit_microusd=10)
    usage = {'input_tokens': 15, 'totalTokenCount': 20, 'output_tokens': -1,
             'credits_used': True, 'prompt': 'Never retain this untrusted provider body', 'api_key': 'not-a-real-key'}
    ledger.settle(result.id, outcome=outcome, usage=usage)
    ledger.settle(result.id, outcome=outcome, usage=usage)  # Exact repeat is idempotent.
    with database() as session:
        row = session.get(ProviderUsageReservation, result.id)
        assert row.outcome == outcome and row.reserved_microusd == 10
        assert json.loads(row.usage_json) == {'input_tokens': 15, 'totalTokenCount': 20}
        assert {row.reserved_microusd for row in session.scalars(select(ProviderBudgetAccount))} == {10}
    with pytest.raises(BudgetError) as exhausted:
        reserve(ledger, 'two', request_limit_microusd=10)
    assert exhausted.value.code == 'budget_exceeded'
    with pytest.raises(BudgetError) as mutation:
        ledger.settle(result.id, outcome=outcome, usage={'input_tokens': 1})
    assert mutation.value.code == 'duplicate_dispatch_mismatch'


def test_review_expiry_is_rechecked_at_dispatch_not_just_startup(database):
    ledger = UsageLedger(database, clock=lambda: NOW + 3 * 86400)
    with pytest.raises(BudgetError) as error:
        reserve(ledger)
    assert error.value.code == 'budget_policy_expired'
    with database() as session:
        assert session.scalar(select(ProviderUsageReservation)) is None


def test_daily_windows_reset_but_same_request_never_resets(database):
    clock = [NOW]
    ledger = UsageLedger(database, clock=lambda: clock[0])
    reserve(ledger, request_limit_microusd=10, provider_daily_limit_microusd=10, scope_daily_limit_microusd=10)
    clock[0] += 86400
    with pytest.raises(BudgetError) as request_cap:
        reserve(ledger, 'two', request_limit_microusd=10, provider_daily_limit_microusd=10, scope_daily_limit_microusd=10)
    assert request_cap.value.code == 'budget_exceeded'
    assert reserve(ledger, request_id='next.day', request_limit_microusd=10,
        provider_daily_limit_microusd=10, scope_daily_limit_microusd=10).dispatched_now


def test_concurrent_workers_cannot_overrun_provider_budget(database):
    ledger = UsageLedger(database, clock=lambda: NOW)

    def attempt(i):
        try:
            return reserve(ledger, scope_id='scope.' + str(i), request_id='request.' + str(i),
                provider_daily_limit_microusd=30).dispatched_now
        except BudgetError as error:
            assert error.code == 'budget_exceeded'
            return False

    with ThreadPoolExecutor(max_workers=8) as workers:
        assert sum(workers.map(attempt, range(12))) == 3
    with database() as session:
        records = session.scalars(select(ProviderUsageReservation)).all()
        assert len(records) == 3 and sum(row.reserved_microusd for row in records) == 30
        global_bucket = session.scalar(select(ProviderBudgetAccount).where(ProviderBudgetAccount.kind == 'provider_day'))
        assert global_bucket.reserved_microusd == 30 and global_bucket.calls == 3


def test_concurrent_duplicate_dispatch_only_one_worker_receives_permission(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(lambda _: reserve(ledger), range(8)))
    assert len({result.id for result in results}) == 1
    assert sum(result.dispatched_now for result in results) == 1


def test_untrusted_budget_identifiers_and_boolean_money_are_rejected(database):
    ledger = UsageLedger(database, clock=lambda: NOW)
    with pytest.raises(BudgetError):
        reserve(ledger, scope_id='https://private.test/name?token=unsafe')
    with pytest.raises(BudgetError):
        policy(reservation_microusd=True)
    with pytest.raises(BudgetError):
        ledger.settle('missing.reservation', outcome='succeeded')
