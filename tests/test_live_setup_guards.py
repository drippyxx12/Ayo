"""No-charge setup regressions: HTTP/model/policy data are explicit offline fixtures."""
import asyncio
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import time

import httpx
import pytest

from ayo.budgets import BudgetError, BudgetPolicy
from ayo.intelligence import GeminiProvider, IntelligenceContext, IntelligenceError, IntelligenceOrchestrator, PublicResearchContext, SourceEvidence, provider_from_env
from ayo.provider_config import MODEL_INPUT_MAX_BYTES
from ayo.provider_usage import OperationUsage, budget_context


def config(monkeypatch):
    values = {'AYO_PROVIDER_SPEND_AUTHORIZED': '1', 'GEMINI_MODEL': 'offline-model', 'GEMINI_MAX_OUTPUT_TOKENS': '1500',
        'GEMINI_THINKING_LEVEL': 'MINIMAL', 'AYO_GEMINI_BUDGET_MODEL': 'offline-model',
        'AYO_GEMINI_BUDGET_THINKING_LEVEL': 'MINIMAL', 'AYO_GEMINI_BUDGET_MAX_INPUT_BYTES': '32768',
        'AYO_GEMINI_BUDGET_MAX_OUTPUT_TOKENS': '1500', 'AYO_REQUEST_BUDGET_MICROUSD': '100',
        'AYO_REQUEST_CALL_LIMIT': '3', 'AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD': '10',
        'AYO_GEMINI_DAILY_BUDGET_MICROUSD': '100', 'AYO_GEMINI_SCOPE_DAILY_BUDGET_MICROUSD': '100',
        'AYO_GEMINI_DAILY_CALL_LIMIT': '2', 'AYO_GEMINI_SCOPE_DAILY_CALL_LIMIT': '2',
        'AYO_GEMINI_BUDGET_POLICY_VERSION': 'offline-review',
        'AYO_GEMINI_BUDGET_POLICY_VALID_UNTIL': str(int(time.time())+3600)}
    for key,value in values.items():monkeypatch.setenv(key,value)


def no_ledger():
    raise AssertionError('Mismatched configuration must be denied before a reservation')


@pytest.mark.parametrize('changes', [{'model': 'different-model'}, {'max_output_tokens': 2000},
                                    {'thinking_level': 'HIGH'}])
def test_actual_model_settings_cannot_reuse_a_cheaper_review(monkeypatch, changes):
    config(monkeypatch)
    fields = {'model': 'offline-model', 'max_output_tokens': 1500, 'thinking_level': 'MINIMAL', **changes}
    adapter=GeminiProvider('offline-key', transport=httpx.MockTransport(lambda _: pytest.fail('Mismatch reached network')), **fields)
    with budget_context(no_ledger, scope_id='anonymous:one', request_id='one'):
        with pytest.raises(IntelligenceError) as error:
            asyncio.run(adapter.complete('policy', {}))
    assert error.value.code == 'budget_configuration_mismatch'


@pytest.mark.parametrize(('key','value'), [('GEMINI_MODEL','unreviewed-model'),
    ('GEMINI_MAX_OUTPUT_TOKENS','3000'), ('GEMINI_THINKING_LEVEL','HIGH'),
    ('AYO_GEMINI_BUDGET_MAX_INPUT_BYTES','65536'), ('AYO_GEMINI_BUDGET_MAX_OUTPUT_TOKENS','+1500')])
def test_changed_runtime_or_review_settings_fail_closed(monkeypatch,key,value):
    config(monkeypatch);monkeypatch.setenv(key,value)
    with pytest.raises(BudgetError) as error:BudgetPolicy.from_env('gemini','analyze')
    assert error.value.code == 'budget_not_configured'
    assert value not in str(error.value)


@pytest.mark.parametrize('value', ['x'*33000,'😀'*9000])
def test_utf8_byte_limit_applies_before_budget_and_http(value):
    def deny(*_args):raise AssertionError('Oversized input reached reservation')
    adapter=GeminiProvider('offline-key','offline-model',dispatch_budget=deny,
        transport=httpx.MockTransport(lambda _: pytest.fail('Oversized input reached network')))
    with pytest.raises(IntelligenceError) as error:asyncio.run(adapter.complete('policy',{'text':value}))
    assert error.value.code == 'model_input_budget_exceeded'


def test_utf8_serialization_avoids_ascii_escape_amplification_and_pins_thinking():
    value='😀'*6000
    def handle(request):
        body=json.loads(request.content)
        text=body['contents'][0]['parts'][0]['text']
        assert len(text.encode())+len('policy'.encode()) <= MODEL_INPUT_MAX_BYTES
        assert '\\ud83d' not in text and json.loads(text)['text']==value
        assert body['generationConfig']['thinkingConfig']=={'thinkingLevel':'MINIMAL','includeThoughts':False}
        assert 'tools' not in body
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{}'}]}}]})
    adapter=GeminiProvider('offline-key','offline-model',thinking_level='MINIMAL',
        transport=httpx.MockTransport(handle),dispatch_budget=lambda *_:nullcontext(OperationUsage()))
    assert asyncio.run(adapter.complete('policy',{'text':value}))[0]=={}


def test_public_only_policy_never_sends_private_context(monkeypatch):
    monkeypatch.setenv('AYO_AI_DATA_POLICY','public_only_reviewed')
    class NoModel:
        async def complete(self,*_args):pytest.fail('Private model call was not authorized')
    ctx=IntelligenceContext(business_id='one',actor_business_id='one',country='NG',question='Private owner question')
    with pytest.raises(IntelligenceError) as error:asyncio.run(IntelligenceOrchestrator(NoModel()).analyze(ctx))
    assert error.value.code=='private_analysis_not_authorized'


def test_public_only_policy_preserves_public_evidence_analysis(monkeypatch):
    monkeypatch.setenv('AYO_AI_DATA_POLICY','public_only_reviewed')
    quote='Public clothing products.'
    class PublicModel:
        name,model='gemini','offline-model'
        async def complete(self,policy,payload):
            assert 'business_id' not in payload
            return {'claims':[{'text':quote,'quote':quote,'kind':'OBSERVED','evidence_ids':['one']}],
                    'recommendations':[],'limitations':['Offline fixture only.']},{}
    ctx=PublicResearchContext(country='GH',question='Public research',evidence=(SourceEvidence(id='one',
        url='https://fixture.org/',excerpt=quote,observed_at=datetime.now(timezone.utc)),))
    assert asyncio.run(IntelligenceOrchestrator(PublicModel()).analyze_public(ctx)).status=='completed'


def test_current_model_and_profile_configuration_are_loaded_without_calling(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','offline-fixture-key')
    monkeypatch.setenv('GEMINI_MODEL','gemini-3.5-flash-lite')
    monkeypatch.setenv('GEMINI_MAX_OUTPUT_TOKENS','1500')
    monkeypatch.setenv('GEMINI_THINKING_LEVEL','MINIMAL')
    monkeypatch.setenv('AYO_AI_DATA_POLICY','public_only_reviewed')
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED','0')
    with pytest.raises(IntelligenceError) as error:provider_from_env('gemini')
    assert error.value.code=='provider_spend_not_authorized'
    # Fixture checks constructor settings only; no complete()/network invocation.
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED','1')
    adapter=provider_from_env('gemini')
    assert adapter.model=='gemini-3.5-flash-lite' and adapter.thinking_level=='MINIMAL' and adapter.max_output_tokens==1500


def test_disabling_spending_blocks_an_already_constructed_adapter(monkeypatch):
    config(monkeypatch)
    adapter=GeminiProvider('offline-key','offline-model',thinking_level='MINIMAL',
        transport=httpx.MockTransport(lambda _:pytest.fail('Disabled dispatch reached network')))
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED','0')
    with budget_context(no_ledger,scope_id='anonymous:one',request_id='one'):
        with pytest.raises(IntelligenceError) as error:asyncio.run(adapter.complete('policy',{}))
    assert error.value.code=='provider_spend_not_authorized'
