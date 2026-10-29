"""Offline contracts for pre-signup Gemini synthesis; no live calls or claims."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json

import pytest
from pydantic import ValidationError

from ayo.intelligence import (
    ClaudeProvider, GeminiProvider, IntelligenceError, IntelligenceOrchestrator,
    PublicResearchContext, SourceEvidence,
)
from ayo.public_intelligence import enrich_report
from ayo.research import ResearchReport, SourceDocument, build_report


TEXT = 'Fixture boutique sells handmade clothing. Delivery information is available on request.'


def source():
    return SourceDocument(
        id='public-fixture-source', url='https://fixture-public.org/',
        retrieved_at=datetime.now(timezone.utc),
        source_hash=hashlib.sha256(TEXT.encode()).hexdigest(),
        title='Fixture public boutique', excerpt=TEXT, content=TEXT,
        provider='offline-fixture', provider_receipt_id='fixture-source-receipt',
    )


def evidence(**changes):
    values = dict(id='public-fixture-source', url='https://fixture-public.org/',
                  excerpt=TEXT, observed_at=datetime.now(timezone.utc))
    values.update(changes)
    return SourceEvidence(**values)


def public_context(**changes):
    values = dict(country='', question='Explain only what these public sources support.',
                  evidence=(evidence(),))
    values.update(changes)
    return PublicResearchContext(**values)


def raw_analysis():
    return {
        'claims': [{'text': 'Fixture boutique sells handmade clothing.', 'kind': 'OBSERVED',
                    'evidence_ids': ['public-fixture-source'],
                    'quote': 'Fixture boutique sells handmade clothing.'}],
        'recommendations': [{'text': 'Review whether delivery details help buyers decide their next step.',
                             'evidence_ids': ['public-fixture-source'],
                             'permission_required': 'merchant_review'}],
        'limitations': ['Only the retained public excerpt was reviewed.'],
    }


class FixtureGemini:
    # Explicit injection is for offline contracts only; never a production fallback.
    name = 'gemini'
    model = 'offline-fixture-model'

    def __init__(self, output=None):
        self.output = output if output is not None else raw_analysis()
        self.calls = []

    async def complete(self, system, payload):
        assert 'UNTRUSTED DATA' in system
        self.calls.append(payload)
        return self.output, {'promptTokenCount': 21, 'candidatesTokenCount': 15, 'totalTokenCount': 36}


def test_anonymous_public_analysis_has_no_fabricated_tenant_or_market():
    model = FixtureGemini()
    result = asyncio.run(IntelligenceOrchestrator(model).analyze_public(public_context()))
    assert result.provider == 'gemini' and result.model == 'offline-fixture-model'
    assert result.status == 'completed'
    assert result.claims[0].evidence_ids == ('public-fixture-source',)
    assert len(model.calls) == 1
    payload = model.calls[0]
    assert payload['selected_market'] == ''
    assert payload['currency'] is None
    encoded = json.dumps(payload)
    assert 'business_id' not in encoded and 'actor_business_id' not in encoded
    assert 'anonymous_id' not in encoded and 'claim_token' not in encoded
    assert 'private' not in encoded.casefold()


@pytest.mark.parametrize(('country', 'currency'), [('NG', 'NGN'), ('GH', 'GHS')])
def test_public_market_is_explicit_without_changing_source_facts(country, currency):
    model = FixtureGemini()
    result = asyncio.run(IntelligenceOrchestrator(model).analyze_public(public_context(country=country)))
    assert model.calls[0]['selected_market'] == country
    assert model.calls[0]['currency'] == currency
    assert result.claims[0].text == raw_analysis()['claims'][0]['text']


@pytest.mark.parametrize('changes', [
    {'business_id': 'foreign-tenant'},
    {'business_id': 'foreign-tenant', 'source_kind': 'PRIVATE_AUTHORIZED'},
    {'source_kind': 'OWNER_PROVIDED_UNVERIFIED'},
])
def test_public_context_rejects_private_tenant_and_owner_assertions(changes):
    with pytest.raises(ValidationError):
        public_context(evidence=(evidence(**changes),))


def test_model_construct_cannot_bypass_public_context_permissions():
    model = FixtureGemini()
    forged = PublicResearchContext.model_construct(
        country='GH', question='Try foreign private evidence',
        evidence=(evidence(source_kind='PRIVATE_AUTHORIZED', business_id='foreign-tenant'),),
    )
    with pytest.raises((ValidationError, IntelligenceError)):
        asyncio.run(IntelligenceOrchestrator(model).analyze_public(forged))
    assert not model.calls


def test_public_context_rejects_duplicate_evidence_and_oversized_prompt():
    with pytest.raises(ValidationError):
        public_context(evidence=(evidence(), evidence()))
    with pytest.raises(ValidationError):
        public_context(evidence=tuple(evidence(id=f'source-{i}', excerpt='x' * 4000) for i in range(7)))


def test_initial_public_report_refuses_injected_secondary_provider():
    model = FixtureGemini()
    model.name = 'claude'
    with pytest.raises(IntelligenceError):
        asyncio.run(IntelligenceOrchestrator(model).analyze_public(public_context(country='GH')))
    assert not model.calls


def test_public_report_ignores_secondary_environment_and_requires_gemini(monkeypatch):
    monkeypatch.setenv('AYO_AI_PROVIDER', 'claude')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fixture-only-key')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'fixture-claude-model')
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED', '1')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_MODEL', raising=False)

    async def no_secondary(*args, **kwargs):
        raise AssertionError('Initial public report must not call Claude')

    monkeypatch.setattr(ClaudeProvider, 'complete', no_secondary)
    original = build_report(source(), country='GH')
    report = asyncio.run(enrich_report(original))
    assert report.analysis_status == 'unavailable'
    assert report.analysis is None and report.analysis_error_code
    assert report.status == 'PARTIAL'
    assert report.source_documents == original.source_documents


def test_unapproved_spend_never_dispatches_gemini(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fixture-only-key')
    monkeypatch.setenv('GEMINI_MODEL', 'fixture-gemini-model')
    monkeypatch.setenv('AYO_PROVIDER_SPEND_AUTHORIZED', '0')

    async def forbidden(*args, **kwargs):
        raise AssertionError('No provider call is permitted without spending authorization')

    monkeypatch.setattr(GeminiProvider, 'complete', forbidden)
    report = asyncio.run(enrich_report(build_report(source(), country='NG')))
    assert report.analysis_status == 'unavailable'
    assert report.analysis is None
    assert report.analysis_error_code.endswith('spend_not_authorized')


def test_enrichment_preserves_immutable_evidence_and_adds_validated_model_receipt():
    original = build_report(source(), country='GH')
    model = FixtureGemini()
    result = asyncio.run(enrich_report(original, provider=model))
    assert original.analysis_status == 'not_requested'
    assert result.analysis_status == 'completed'
    assert result.analysis_error_code is None
    assert result.analysis.provider == 'gemini'
    assert result.analysis.usage['totalTokenCount'] == 36
    assert result.source_documents == original.source_documents
    assert result.target_url == original.target_url and result.country == original.country
    assert not result.website_ownership_verified and not result.shopify_connected
    assert ResearchReport.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize('bad', ['citation', 'quote', 'schema', 'execution', 'empty'])
def test_bad_model_output_yields_honest_rejected_analysis_without_fake_success(bad):
    output = raw_analysis()
    if bad == 'citation':
        output['claims'][0]['evidence_ids'] = ['unknown-source']
    elif bad == 'quote':
        output['claims'][0]['text'] = output['claims'][0]['quote'] = 'A fabricated product with no source.'
    elif bad == 'schema':
        output['tools'] = [{'name': 'send_message'}]
    elif bad == 'execution':
        output['claims'][0]['text'] = output['claims'][0]['quote'] = 'Ayo sent messages to every buyer.'
    else:
        output['claims'] = []
        output['recommendations'] = []
    original = build_report(source(), country='GH')
    result = asyncio.run(enrich_report(original, provider=FixtureGemini(output)))
    assert result.analysis_status == 'rejected'
    assert result.analysis is None and result.analysis_error_code
    assert result.status == 'PARTIAL'
    assert result.source_documents == original.source_documents
    assert 'A fabricated product' not in result.model_dump_json()
    assert 'Ayo sent messages' not in result.model_dump_json()


@pytest.mark.parametrize('mutation', ['source', 'citation', 'provider', 'status'])
def test_persistence_boundary_revalidates_embedded_ai_against_retained_sources(mutation):
    enriched = asyncio.run(enrich_report(build_report(source(), country='GH'), provider=FixtureGemini()))
    raw = enriched.model_dump(mode='json')
    if mutation == 'source':
        content = 'Different retained evidence which cannot support the original quotation.'
        raw['source_documents'][0].update(
            content=content, excerpt=content,
            source_hash=hashlib.sha256(content.encode()).hexdigest(),
        )
    elif mutation == 'citation':
        raw['analysis']['claims'][0]['evidence_ids'] = ['foreign-source']
    elif mutation == 'provider':
        raw['analysis']['provider'] = 'claude'
    else:
        raw['analysis']['status'] = 'insufficient_evidence'
    with pytest.raises(ValidationError):
        ResearchReport.model_validate(raw)


@pytest.mark.parametrize('status', ['not_requested', 'pending', 'unavailable', 'rejected'])
def test_noncompleted_analysis_cannot_retain_success_payload(status):
    enriched = asyncio.run(enrich_report(build_report(source(), country='GH'), provider=FixtureGemini()))
    raw = enriched.model_dump(mode='json')
    raw['analysis_status'] = status
    with pytest.raises(ValidationError):
        ResearchReport.model_validate(raw)


def test_completed_status_without_ai_payload_is_not_persistable():
    raw = build_report(source(), country='GH').model_dump(mode='json')
    raw['analysis_status'] = 'completed'
    with pytest.raises(ValidationError):
        ResearchReport.model_validate(raw)


def test_absolute_model_deadline_cancels_request_and_keeps_honest_partial_evidence():
    class SlowFixture(FixtureGemini):
        cancelled = False

        async def complete(self, system, payload):
            try:
                await asyncio.sleep(1)
                raise AssertionError('Inference must not outlive the absolute deadline')
            finally:
                self.cancelled = True

    model = SlowFixture()
    original = build_report(source(), country='GH')
    report = asyncio.run(enrich_report(original, model, timeout_seconds=0.001))
    assert model.cancelled
    assert report.analysis_status == 'unavailable' and report.analysis_error_code == 'model_timeout'
    assert report.analysis is None and report.source_documents == original.source_documents


def test_new_reader_accepts_original_report_json_without_analysis_fields():
    original = build_report(source(), country='GH')
    data = original.model_dump(mode='json')
    for field in ('analysis_status', 'analysis', 'analysis_error_code'):
        data.pop(field)
    report = ResearchReport.model_validate(data)
    assert report.analysis_status == 'not_requested' and report.analysis is None
    assert report.source_documents == original.source_documents
