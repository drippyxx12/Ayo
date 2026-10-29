"""Zero USD never means unlimited calls or permission for a paid provider."""
import asyncio
import time

import httpx
import pytest
from sqlalchemy import select

from ayo.budgets import BudgetError, BudgetPolicy
from ayo.intelligence import GeminiProvider, IntelligenceError
from ayo.models import ProviderBudgetAccount, ProviderUsageReservation
from ayo.provider_usage import budget_context, metered_operation
from test_platform_flow import platform  # noqa: F401
from test_merchant_analysis import free_config


def test_zero_budget_rejects_paid_model_provider_or_positive_cost(monkeypatch):
    free_config(monkeypatch)
    assert BudgetPolicy.from_env('gemini', 'analyze').reservation_microusd == 0
    for name, value in [('GEMINI_MODEL', 'paid-model'), ('AYO_GEMINI_PROJECT_TIER_REVIEW', 'paid'),
                        ('AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD', '1')]:
        with monkeypatch.context() as patch:
            patch.setenv(name, value)
            with pytest.raises(BudgetError):BudgetPolicy.from_env('gemini', 'analyze')
    with pytest.raises(BudgetError):BudgetPolicy.from_env('firecrawl', 'fetch')


def test_zero_budget_enforces_calls_replay_expiry_and_uncertain_debits(platform, monkeypatch):
    free_config(monkeypatch, calls=1)
    async def dispatch(prefix, *, fail=False):
        with budget_context(platform.factory, scope_id='free-test-scope', request_id='test-request', dispatch_prefix=prefix):
            policy = BudgetPolicy.from_env('gemini', 'analyze')
            async with metered_operation('gemini', 'analyze', policy.configuration_fingerprint):
                if fail:raise RuntimeError('uncertain test outcome')
    with pytest.raises(RuntimeError):asyncio.run(dispatch('first', fail=True))
    with pytest.raises(BudgetError) as error:asyncio.run(dispatch('first'))
    assert error.value.code == 'dispatch_already_reserved'
    with pytest.raises(BudgetError) as error:asyncio.run(dispatch('second'))
    assert error.value.code == 'budget_exceeded'
    with platform.factory() as session:
        record = session.scalar(select(ProviderUsageReservation))
        assert record.reserved_microusd == 0 and record.outcome == 'uncertain'
        assert all(row.limit_microusd == 0 and row.calls == 1 for row in session.scalars(select(ProviderBudgetAccount)))
    monkeypatch.setenv('AYO_GEMINI_BUDGET_POLICY_VALID_UNTIL', str(int(time.time()) - 1))
    with pytest.raises(BudgetError):asyncio.run(dispatch('expired'))


def test_free_switch_cannot_dispatch_paid_budget_or_firecrawl(platform, monkeypatch):
    free_config(monkeypatch)
    monkeypatch.setenv('AYO_GEMINI_BILLING_MODE', 'paid_reviewed')
    for key in ('AYO_REQUEST_BUDGET_MICROUSD', 'AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD',
                'AYO_GEMINI_DAILY_BUDGET_MICROUSD', 'AYO_GEMINI_SCOPE_DAILY_BUDGET_MICROUSD'):
        monkeypatch.setenv(key, '10')
    calls=[]
    provider=GeminiProvider('offline-free-test', 'gemini-3.5-flash-lite', thinking_level='MINIMAL',
        transport=httpx.MockTransport(lambda request: calls.append(request)))
    async def dispatch():
        with budget_context(platform.factory, scope_id='free-test', request_id='paid-policy'):
            await provider.complete('Test system policy.', {})
    with pytest.raises(IntelligenceError) as error:asyncio.run(dispatch())
    assert error.value.code == 'provider_spend_not_authorized' and calls == []


def test_operator_replacement_preserves_counts_and_cannot_repeat_or_enable_paid_capacity(platform,monkeypatch):
    from ayo.budgets import UsageLedger
    free_config(monkeypatch,calls=2)
    policy=BudgetPolicy.from_env('gemini','analyze')
    ledger=UsageLedger(platform.factory)
    ledger.reserve(scope_id='review-test',request_id='first',dispatch_id='first',policy=policy)
    ledger.review_free_gemini_replacement(reason='Explicit small-target replacement review; preserve the already consumed call.')
    with platform.factory() as session:
        day=session.scalar(select(ProviderBudgetAccount).where(ProviderBudgetAccount.kind=='provider_day'))
        assert day.calls==1 and day.call_limit==3 and day.limit_microusd==0
        assert len(session.scalars(select(ProviderUsageReservation)).all())==1
    with pytest.raises(BudgetError):
        ledger.review_free_gemini_replacement(reason='A repeated replacement must remain blocked and retain its counts.')
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED','1')
    with pytest.raises(BudgetError):
        ledger.review_free_gemini_replacement(reason='Paid settings must not permit this administrative review operation.')
