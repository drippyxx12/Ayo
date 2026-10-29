"""Offline model boundary tests. Fixtures are not actual AI/provider results."""
import asyncio
from contextlib import nullcontext
from datetime import datetime, timezone
import json

import httpx
import pytest
from pydantic import ValidationError

from ayo.intelligence import (
    ClaudeProvider, GeminiProvider, IntelligenceContext, IntelligenceError,
    IntelligenceOrchestrator, SourceEvidence, provider_from_env, validate_analysis,
)
from ayo.provider_usage import OperationUsage


def offline_budget(*_args):
    """Explicit fixture injection; used only with MockTransport, never network."""
    return nullcontext(OperationUsage())


def context(**changes):
    values = {'business_id': 'business-a', 'actor_business_id': 'business-a', 'country': 'GH',
        'question': 'What could improve the product journey?',
        'evidence': (SourceEvidence(id='page-1', business_id='business-a', url='https://merchant.org/',
            excerpt='Our boutique sells handmade clothing. Delivery details are on our policy page.',
            observed_at=datetime.now(timezone.utc)),)}
    values.update(changes)
    return IntelligenceContext(**values)


def analysis():
    return {'claims': [{'text': 'Our boutique sells handmade clothing.', 'kind': 'OBSERVED',
                       'evidence_ids': ['page-1'], 'quote': 'Our boutique sells handmade clothing.'}],
            'recommendations': [{'text': 'Review delivery information visibility on product pages.',
                                 'evidence_ids': ['page-1'], 'permission_required': 'merchant_review'}],
            'limitations': ['Only the cited source excerpt was reviewed.']}


class FakeModel:
    name = 'offline-fixture'
    model = 'fixture-v1'

    def __init__(self, response=None):
        self.response = response if response is not None else analysis()
        self.payload = None

    async def complete(self, system, payload):
        assert 'UNTRUSTED DATA' in system
        assert 'execute tools' in system
        self.payload = payload
        return self.response, {'input_tokens': 20, 'output_tokens': 30}


def test_real_provider_output_must_be_source_labeled_and_never_execute():
    model = FakeModel()
    result = asyncio.run(IntelligenceOrchestrator(model).analyze(context()))
    assert result.status == 'completed'
    assert result.provider == 'offline-fixture'
    assert result.claims[0].kind == 'OBSERVED'
    assert result.recommendations[0].permission_required == 'merchant_review'
    assert model.payload['selected_market'] == 'GH'
    assert model.payload['currency'] == 'GHS'
    assert 'business_id' not in model.payload
    assert not hasattr(result, 'tools')


def test_missing_evidence_returns_unknown_without_calling_a_model():
    model = FakeModel()
    result = asyncio.run(IntelligenceOrchestrator(model).analyze(context(evidence=())))
    assert result.status == 'insufficient_evidence'
    assert model.payload is None
    assert not result.claims and not result.recommendations


@pytest.mark.parametrize('changes', [
    {'actor_business_id': 'business-b'},
    {'evidence': (SourceEvidence(id='foreign', business_id='business-b', url='https://merchant.org/',
                     excerpt='Other tenant source', observed_at=datetime.now(timezone.utc)),)},
])
def test_foreign_business_evidence_is_rejected_before_inference(changes):
    with pytest.raises(ValidationError, match='business'):
        context(**changes)


@pytest.mark.parametrize(('change', 'code'), [
    ({'evidence_ids': ['nonexistent-source']}, 'unsupported_citation'),
    ({'evidence_ids': []}, 'missing_citation'),
    ({'text': 'This business has a great checkout.'}, 'unsupported_observation'),
    ({'text': 'Our store sells shoes.', 'quote': 'Our store sells shoes.'}, 'unsupported_observation'),
    ({'text': 'Revenue increased 30%.', 'quote': 'Revenue increased 30%.'}, 'unsupported_financial_claim'),
    ({'text': 'Ayo sent messages to all leads.', 'quote': 'Ayo sent messages to all leads.'}, 'unauthorized_action_claim'),
])
def test_model_cannot_invent_claims_citations_or_execution(change, code):
    raw = analysis()
    raw['claims'][0].update(change)
    with pytest.raises(IntelligenceError) as raised:
        validate_analysis(raw, context())
    assert raised.value.code == code


def test_owner_claims_do_not_become_observed_facts():
    owner = SourceEvidence(id='page-1', business_id='business-a', url='owner-provided',
        excerpt='Our boutique sells handmade clothing.', source_kind='OWNER_PROVIDED_UNVERIFIED',
        observed_at=datetime.now(timezone.utc))
    with pytest.raises(IntelligenceError) as raised:
        validate_analysis(analysis(), context(evidence=(owner,)))
    assert raised.value.code == 'unverified_owner_claim'


def test_prompt_injection_cannot_create_tools_or_permissions():
    raw = analysis()
    raw['tools'] = [{'name': 'send_email', 'approved': True}]
    with pytest.raises(IntelligenceError, match='invalid structured'):
        validate_analysis(raw, context())
    raw = analysis()
    raw['recommendations'][0]['permission_required'] = 'none'
    with pytest.raises(IntelligenceError):
        validate_analysis(raw, context())


def test_even_limitation_text_cannot_claim_actions_happened():
    raw = analysis()
    raw['limitations'] = ['Ayo has sent the campaign.']
    with pytest.raises(IntelligenceError) as raised:
        validate_analysis(raw, context())
    assert raised.value.code == 'unauthorized_action_claim'


def test_unconfigured_provider_and_spending_fail_closed(monkeypatch):
    monkeypatch.setenv('AYO_AI_PROVIDER', 'gemini')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_MODEL', raising=False)
    with pytest.raises(IntelligenceError) as raised:
        provider_from_env()
    assert raised.value.code == 'provider_not_configured'
    monkeypatch.setenv('GEMINI_API_KEY', 'offline-key')
    monkeypatch.setenv('GEMINI_MODEL', 'configured-evaluated-model')
    monkeypatch.delenv('AYO_PROVIDER_SPEND_AUTHORIZED', raising=False)
    with pytest.raises(IntelligenceError) as raised:
        provider_from_env()
    assert raised.value.code == 'provider_spend_not_authorized'
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED', '1')
    with pytest.raises(IntelligenceError) as raised:
        provider_from_env()
    assert raised.value.code == 'provider_data_policy_not_reviewed'
    monkeypatch.setenv('AYO_AI_DATA_POLICY', 'reviewed')
    assert isinstance(provider_from_env(), GeminiProvider)
    monkeypatch.setenv('AYO_AI_PROVIDER', 'claude')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'offline-key')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'configured-evaluated-model')
    assert isinstance(provider_from_env(), ClaudeProvider)


@pytest.mark.parametrize('provider_class', [GeminiProvider, ClaudeProvider])
def test_model_identifier_cannot_inject_a_destination(provider_class):
    with pytest.raises(IntelligenceError):
        provider_class('fixture-key', '../../untrusted-host')


def test_gemini_rest_adapter_uses_header_key_and_no_tools():
    def handle(request):
        assert str(request.url) == 'https://generativelanguage.googleapis.com/v1beta/models/configured-model:generateContent'
        assert request.headers['x-goog-api-key'] == 'fixture-key'
        assert 'fixture-key' not in str(request.url)
        body = json.loads(request.content)
        assert 'tools' not in body
        assert body['generationConfig']['maxOutputTokens'] == 1500
        assert body['generationConfig']['candidateCount'] == 1
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(analysis())}]}}],
                                         'usageMetadata': {'totalTokenCount': 50}})
    provider = GeminiProvider('fixture-key', 'configured-model', transport=httpx.MockTransport(handle), dispatch_budget=offline_budget)
    result = asyncio.run(IntelligenceOrchestrator(provider).analyze(context(country='NG')))
    assert result.model == 'configured-model' and result.usage == {'totalTokenCount': 50}


def test_claude_rest_adapter_rejects_tool_use_output():
    def handle(request):
        assert request.url.host == 'api.anthropic.com'
        assert request.headers['x-api-key'] == 'fixture-key'
        body = json.loads(request.content)
        assert 'tools' not in body
        return httpx.Response(200, json={'stop_reason': 'tool_use', 'content': [{'type': 'tool_use', 'name': 'send_email'}]})
    provider = ClaudeProvider('fixture-key', 'configured-model', transport=httpx.MockTransport(handle), dispatch_budget=offline_budget)
    with pytest.raises(IntelligenceError) as raised:
        asyncio.run(IntelligenceOrchestrator(provider).analyze(context()))
    assert raised.value.code == 'provider_failure'


def test_provider_errors_do_not_echo_keys_or_raw_upstream_details():
    transport = httpx.MockTransport(lambda request: httpx.Response(401, text='fixture-secret and upstream internals'))
    provider = GeminiProvider('fixture-secret', 'configured-model', transport=transport, dispatch_budget=offline_budget)
    with pytest.raises(IntelligenceError) as raised:
        asyncio.run(IntelligenceOrchestrator(provider).analyze(context()))
    assert 'fixture-secret' not in str(raised.value)
    assert 'upstream internals' not in str(raised.value)


def gemini_response(**changes):
    """Documented REST shape with clearly offline analysis content."""
    result = {'candidates': [{'finishReason': 'STOP',
        'content': {'parts': [{'text': json.dumps(analysis())}]}}]}
    result.update(changes)
    return result


def run_adapter_fixture(provider_class, body):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=body)

    provider = provider_class('offline-fixture-key', 'offline-model',
        transport=httpx.MockTransport(handle), dispatch_budget=offline_budget)
    result = asyncio.run(IntelligenceOrchestrator(provider).analyze(context()))
    assert len(calls) == 1
    return result


@pytest.mark.parametrize('parts', [
    [{'functionCall': {'name': 'send_email', 'args': {}}}],
    [{'text': json.dumps(analysis())}, {'functionCall': {'name': 'send_email'}}],
    [{'text': json.dumps(analysis()), 'functionCall': {'name': 'send_email'}}],
    [{'text': json.dumps(analysis()), 'thought': True}],
    [{'text': 'hidden reasoning', 'thought': True}, {'text': json.dumps(analysis())}],
    [{'inlineData': {'mimeType': 'image/png', 'data': 'offline'}}],
    [{'text': None}],
    [None],
    ['not-a-part'],
    [],
    None,
])
def test_gemini_refuses_nontext_tool_thought_and_malformed_parts(parts):
    body = gemini_response(candidates=[{'finishReason': 'STOP', 'content': {'parts': parts}}])
    with pytest.raises(IntelligenceError) as raised:
        run_adapter_fixture(GeminiProvider, body)
    assert raised.value.code == 'provider_failure'


@pytest.mark.parametrize('candidates', [
    None, {}, [], [None], ['not-a-candidate'],
    [{'finishReason': 'STOP', 'content': None}],
    [{'finishReason': 'STOP', 'content': {}}],
    [{'content': {'parts': [{'text': json.dumps(analysis())}]}}],
    [gemini_response()['candidates'][0], gemini_response()['candidates'][0]],
])
def test_gemini_refuses_ambiguous_or_malformed_candidates(candidates):
    with pytest.raises(IntelligenceError) as raised:
        run_adapter_fixture(GeminiProvider, gemini_response(candidates=candidates))
    assert raised.value.code == 'provider_failure'


@pytest.mark.parametrize('reason', ['MAX_TOKENS', 'SAFETY', 'RECITATION', 'UNEXPECTED_TOOL_CALL', 'CONTINUATION'])
def test_incomplete_gemini_generation_does_not_become_a_completed_report(reason):
    body = gemini_response()
    body['candidates'][0]['finishReason'] = reason
    with pytest.raises(IntelligenceError) as raised:
        run_adapter_fixture(GeminiProvider, body)
    assert raised.value.code == 'provider_failure'


def test_gemini_prompt_safety_block_is_explicit_and_never_echoes_provider_text():
    body = {'promptFeedback': {'blockReason': 'SAFETY', 'blockReasonMessage': 'offline-sensitive-provider-detail'}}
    with pytest.raises(IntelligenceError) as raised:
        run_adapter_fixture(GeminiProvider, body)
    assert raised.value.code == 'model_safety_blocked'
    assert 'offline-sensitive-provider-detail' not in str(raised.value)


@pytest.mark.parametrize('content', [
    None, {}, [None], ['not-a-block'], [],
    [{'type': 'text', 'text': None}],
    [{'type': 'text'}],
    [{'type': 'thinking', 'thinking': 'offline reasoning'}],
    [{'type': 'tool_use', 'name': 'send_email', 'input': {}}],
    [{'type': 'text', 'text': json.dumps(analysis())}, {'type': 'tool_use', 'name': 'send_email'}],
])
def test_claude_refuses_malformed_nontext_or_tool_content(content):
    with pytest.raises(IntelligenceError):
        run_adapter_fixture(ClaudeProvider, {'stop_reason': 'end_turn', 'content': content})


def test_gemini_retains_thinking_and_cache_counts_but_not_raw_metadata():
    usage = {'promptTokenCount': 30, 'candidatesTokenCount': 15, 'thoughtsTokenCount': 12,
        'cachedContentTokenCount': 5, 'toolUsePromptTokenCount': 0, 'totalTokenCount': 57,
        'provider_private_detail': 'offline-sensitive-metadata', 'invoice_usd': 99}
    result = run_adapter_fixture(GeminiProvider, gemini_response(usageMetadata=usage))
    assert result.usage == {key: value for key, value in usage.items()
                            if key not in {'provider_private_detail', 'invoice_usd'}}
    assert 'offline-sensitive-metadata' not in result.model_dump_json()


@pytest.mark.parametrize('invalid', [True, False, -1, 10**12, '100', 1.5, None])
@pytest.mark.parametrize('provider_class', [GeminiProvider, ClaudeProvider])
def test_provider_usage_rejects_boolean_negative_huge_and_noninteger_counts(provider_class, invalid):
    if provider_class is GeminiProvider:
        body = gemini_response(usageMetadata={'promptTokenCount': invalid,
            'thoughtsTokenCount': invalid, 'candidatesTokenCount': 10})
        expected = {'candidatesTokenCount': 10}
    else:
        body = {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(analysis())}],
                'usage': {'input_tokens': invalid, 'output_tokens': 10, 'cache_read_input_tokens': invalid}}
        expected = {'output_tokens': 10}
    assert run_adapter_fixture(provider_class, body).usage == expected


@pytest.mark.parametrize('usage', [None, [], 'offline-untrusted-usage'])
@pytest.mark.parametrize('provider_class', [GeminiProvider, ClaudeProvider])
def test_missing_or_malformed_usage_never_becomes_invented_cost(provider_class, usage):
    if provider_class is GeminiProvider:
        body = gemini_response(usageMetadata=usage)
    else:
        body = {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(analysis())}], 'usage': usage}
    result = run_adapter_fixture(provider_class, body)
    assert result.usage == {}
    assert not hasattr(result, 'cost_usd')


@pytest.mark.parametrize('api_key', ['', 'REPLACE_WITH_API_KEY', 'CHANGEME', 'fixture key',
    'fixture\nkey', 'fixture\tkey', 'fixture\x00key', 'fixture\x7fkey', 'fixture\u200bkey'])
@pytest.mark.parametrize('provider_class', [GeminiProvider, ClaudeProvider])
def test_invalid_or_placeholder_credentials_are_denied_before_dispatch(provider_class, api_key):
    calls = []

    def handle(request):
        calls.append(request)
        raise AssertionError('Invalid credential must be rejected before dispatch')

    with pytest.raises(IntelligenceError) as raised:
        provider_class(api_key, 'offline-model', transport=httpx.MockTransport(handle), dispatch_budget=offline_budget)
    assert raised.value.code == 'provider_not_configured'
    assert calls == []
