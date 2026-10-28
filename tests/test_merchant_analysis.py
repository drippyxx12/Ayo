"""Merchant-authorized report/attachment/return/follow-up flows; model HTTP is offline."""
from datetime import datetime, timezone
import json
import re
import secrets
import time

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import func, select

from ayo import app as mod
from ayo.assistant_models import AssistantConversation
from ayo.intelligence import GeminiProvider, IntelligenceOrchestrator
from ayo.models import Membership, ProviderUsageReservation, ResearchReportRecord, User
from ayo.research import ResearchReport
from test_platform_flow import platform, csrf, register, verify_latest  # noqa: F401


def free_config(monkeypatch, *, calls=2):
    values = {'AYO_PROVIDER_SPEND_AUTHORIZED': '0', 'AYO_MAIL_SEND_AUTHORIZED': '0',
        'AYO_GEMINI_FREE_CALLS_AUTHORIZED': '1', 'AYO_GEMINI_BILLING_MODE': 'free_only_reviewed',
        'AYO_GEMINI_PROJECT_TIER_REVIEW': 'free_confirmed', 'AYO_AI_DATA_POLICY': 'owner_nonpersonal_reviewed',
        'GEMINI_MODEL': 'gemini-3.5-flash-lite', 'GEMINI_MAX_OUTPUT_TOKENS': '1500', 'GEMINI_THINKING_LEVEL': 'MINIMAL',
        'AYO_GEMINI_BUDGET_MODEL': 'gemini-3.5-flash-lite', 'AYO_GEMINI_BUDGET_MAX_INPUT_BYTES': '32768',
        'AYO_GEMINI_BUDGET_MAX_OUTPUT_TOKENS': '1500', 'AYO_GEMINI_BUDGET_THINKING_LEVEL': 'MINIMAL',
        'AYO_GEMINI_BUDGET_POLICY_VERSION': 'offline-free-merchant-v1',
        'AYO_GEMINI_BUDGET_POLICY_VALID_UNTIL': str((int(time.time()) // 86400 + 1) * 86400),
        'AYO_REQUEST_BUDGET_MICROUSD': '0', 'AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD': '0',
        'AYO_GEMINI_DAILY_BUDGET_MICROUSD': '0', 'AYO_GEMINI_SCOPE_DAILY_BUDGET_MICROUSD': '0',
        'AYO_REQUEST_CALL_LIMIT': '1', 'AYO_GEMINI_DAILY_CALL_LIMIT': str(calls), 'AYO_GEMINI_SCOPE_DAILY_CALL_LIMIT': str(calls)}
    for name, value in values.items():monkeypatch.setenv(name, value)
    return values


def owner(platform):
    register(platform.client, 'supplied-owner@example.org')
    assert verify_latest(platform.client, platform.factory).status_code == 303
    with platform.factory() as session:
        user = session.scalar(select(User))
        return user.id, session.scalar(select(Membership.business_id).where(Membership.user_id == user.id))


def form(platform, **changes):
    page = platform.client.get('/business-analysis')
    assert page.status_code == 200
    data = {'csrf': csrf(platform.client, '/business-analysis'),
        'request_id': re.search(r'name="request_id" value="([^"]+)"', page.text)[1],
        'name': 'Synthetic bag studio', 'country': 'NG',
        'description': 'Authorized nonpersonal test description for a reusable bag business.',
        'products': 'Canvas totes and cotton produce bags.', 'pricing': 'Merchant-stated test price: NGN 5000 per tote.',
        'website': 'No website supplied; no URL should be fetched.', 'goals': 'Improve product descriptions.',
        'authorized': 'true', 'nonpersonal': 'true', 'data_consent': 'true'}
    data.update(changes)
    return data


def model(monkeypatch, platform, *, malicious=None):
    free_config(monkeypatch)
    calls = []
    def handler(request):
        body = json.loads(request.content)
        context = json.loads(body['contents'][0]['parts'][0]['text'])
        assert body['generationConfig']['responseSchema']['properties']['claims']['items']['properties']['kind']['enum'] == ['INFERRED', 'UNKNOWN']
        calls.append(context)
        assert 'business_id' not in context and 'history' not in context
        assert all(e['classification'] == 'OWNER_PROVIDED_UNVERIFIED' for e in context['evidence'])
        with platform.factory() as session:
            assert session.scalar(select(ResearchReportRecord)) is not None
        source = context['evidence'][0]
        claim = {'text': 'The supplied offer may benefit from clearer product descriptions.', 'kind': 'INFERRED',
                 'evidence_ids': [source['id']], 'quote': ''}
        if malicious == 'observed':claim.update(kind='OBSERVED', text=source['excerpt'], quote=source['excerpt'])
        if malicious == 'citation':claim['evidence_ids'] = ['foreign-source']
        if malicious == 'contact':claim['text'] = 'Contact invented@example.org for sales.'
        raw = {'claims': [claim, {'text': 'Independent business performance is unknown.', 'kind': 'UNKNOWN', 'evidence_ids': [], 'quote': ''}],
            'recommendations': [{'text': 'Review product descriptions with the merchant.', 'evidence_ids': [source['id']], 'permission_required': 'merchant_review'}],
            'limitations': ['All business inputs are merchant-provided and unverified. Offline model fixture.']}
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(raw)}]}}],
            'usageMetadata': {'promptTokenCount': 50, 'candidatesTokenCount': 30, 'totalTokenCount': 80}})
    provider = GeminiProvider('offline-merchant-key', 'gemini-3.5-flash-lite', thinking_level='MINIMAL', transport=httpx.MockTransport(handler))
    monkeypatch.setattr(mod.app.state, 'merchant_analysis_provider', provider, raising=False)
    monkeypatch.setattr(mod.app.state, 'intelligence_factory', lambda: IntelligenceOrchestrator(provider))
    return calls


def test_supplied_report_upload_persists_relogin_and_scoped_followup_with_zero_ledger(platform, monkeypatch):
    user_id, business_id = owner(platform)
    calls = model(monkeypatch, platform)
    data = form(platform)
    response = platform.client.post('/business-analysis', data=data,
        files={'document': ('private-filename-do-not-retain.md', b'Category: reusable bags. Test shipping terms require merchant review.', 'text/markdown')})
    assert response.status_code == 303, response.text
    path = response.headers['location']
    report_id = path.split('/')[-1]
    with platform.factory() as session:
        row = session.get(ResearchReportRecord, report_id)
        report = ResearchReport.model_validate_json(row.report_json)
        assert row.business_id == business_id and row.owner_user_id == user_id
        assert row.expires_at is None and row.anonymous_session_hash is None
        assert report.origin == 'merchant_provided' and report.analysis_status == 'completed'
        assert report.opportunities and all(item.classification == 'INFERRED' for item in report.opportunities)
        assert all(s.source_type == 'OWNER_PROVIDED_UNVERIFIED' for s in report.source_documents)
        assert any(s.origin == 'merchant_upload' for s in report.source_documents)
        assert 'private-filename-do-not-retain' not in row.report_json
        original = row.report_json
    page = platform.client.get(path)
    assert page.status_code == 200 and 'OWNER_PROVIDED_UNVERIFIED' in page.text
    assert 'NGN 5000' in page.text and 'Supporting input' in page.text
    assert platform.client.get('/research/library/' + report_id).status_code == 200
    assert platform.client.get('/research/' + report_id).status_code == 200
    export = platform.client.get('/research/library/' + report_id + '/export').json()
    assert all(s['classification'] == 'OWNER_PROVIDED_UNVERIFIED' for s in export['sources'])
    assert export['ownership_verified'] is False
    assert platform.client.post('/business-analysis', data=data,
        files={'document': ('other-name.md', b'Category: reusable bags. Test shipping terms require merchant review.', 'text/markdown')}).status_code == 303
    assert len(calls) == 1
    assert platform.client.post('/business-analysis', data={**data, 'products': 'Changed products.'}).status_code == 409
    assert platform.client.post('/logout', data={'csrf': csrf(platform.client, '/work')}).status_code == 303
    assert platform.client.post('/login', data={'csrf': csrf(platform.client, '/login'), 'email': 'supplied-owner@example.org',
        'password': 'FixturePassword123!'}).status_code == 303
    assert platform.client.get(path).status_code == 200
    response = platform.client.post(path + '/conversation', data={'csrf': csrf(platform.client, path)})
    assert response.status_code == 303, response.text
    conversation_path = response.headers['location']
    from test_assistant import form_values
    for sensitive in ('Please contact person@example.org', 'Use api_key=private', 'Call +233 200 555 123'):
        rejected = platform.client.post(conversation_path + '/messages',
            data={**form_values(platform.client, conversation_path), 'question': sensitive})
        assert rejected.status_code == 400 and len(calls) == 1
    followup = platform.client.post(conversation_path + '/messages', data={**form_values(platform.client, conversation_path),
        'question': 'What should I improve first in this supplied offer?'})
    from ayo.assistant_models import AssistantMessage
    with platform.factory() as session:
        diagnostic = [(m.status, m.error_code) for m in session.scalars(select(AssistantMessage))]
    assert followup.status_code == 303 and len(calls) == 2, diagnostic
    with platform.factory() as session:
        assert session.scalar(select(AssistantConversation)).source_report_id == report_id
        assert session.get(ResearchReportRecord, report_id).report_json == original
        reservations = session.scalars(select(ProviderUsageReservation)).all()
        assert len(reservations) == 2 and all(r.reserved_microusd == 0 and r.outcome == 'succeeded' for r in reservations)
    assert 'gemini-3.5-flash-lite' in platform.client.get(conversation_path).text


@pytest.mark.parametrize('changes', [{'authorized': 'false'}, {'nonpersonal': 'false'}, {'data_consent': 'false'},
    {'country': 'US'}, {'description': 'short'}, {'products': 'Email person@example.org'}, {'pricing': 'api_key=secret'},
    {'description': 'x' * 2001}])
def test_invalid_supplied_inputs_never_dispatch(platform, monkeypatch, changes):
    owner(platform);calls = model(monkeypatch, platform)
    assert platform.client.post('/business-analysis', data=form(platform, **changes)).status_code == 400
    assert calls == []
    with platform.factory() as session:assert session.scalar(select(func.count()).select_from(ResearchReportRecord)) == 0


@pytest.mark.parametrize('filename,data', [('a.pdf', b'PDF'), ('a.txt', b'\xffbad'), ('a.txt', b'x' * 4001), ('a.md', b'bad\x00control')])
def test_unsafe_uploads_rejected(platform, monkeypatch, filename, data):
    owner(platform);calls = model(monkeypatch, platform)
    assert platform.client.post('/business-analysis', data=form(platform), files={'document': (filename, data)}).status_code == 400
    assert calls == []


@pytest.mark.parametrize('malicious', ['observed', 'citation', 'contact'])
def test_owner_statements_cannot_become_observed_or_foreign_cited(platform, monkeypatch, malicious):
    owner(platform);calls = model(monkeypatch, platform, malicious=malicious)
    response = platform.client.post('/business-analysis', data=form(platform))
    assert response.status_code == 303 and len(calls) == 1
    with platform.factory() as session:
        report = ResearchReport.model_validate_json(session.scalar(select(ResearchReportRecord)).report_json)
        assert report.analysis_status == 'unavailable' and report.analysis is None


def test_tenant_role_csrf_and_public_policy_boundaries(platform, monkeypatch):
    user_id, business_id = owner(platform);calls = model(monkeypatch, platform)
    data = form(platform)
    assert platform.client.post('/business-analysis', data={**data, 'csrf': 'wrong'}).status_code == 403
    with platform.factory() as session:
        session.get(Membership, (business_id, user_id)).role = 'analyst';session.commit()
    assert platform.client.post('/business-analysis', data=data).status_code == 403
    with platform.factory() as session:
        session.get(Membership, (business_id, user_id)).role = 'owner';session.commit()
    monkeypatch.setenv('AYO_AI_DATA_POLICY', 'public_only_reviewed')
    response = platform.client.post('/business-analysis', data=data)
    assert response.status_code == 303 and calls == []
    path = response.headers['location'];report_id = path.split('/')[-1]
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as other:
        register(other, 'other-supplied@example.org');assert verify_latest(other, platform.factory).status_code == 303
        assert other.get(path).status_code == 404
        assert other.get('/research/library/' + report_id + '/export').status_code == 404
        assert other.post(path + '/conversation', data={'csrf': csrf(other, '/work')}).status_code == 404
    with platform.factory() as session:
        session.get(User, user_id).email_verified_at = None;session.commit()
    assert platform.client.post('/business-analysis', data=form(platform, request_id=secrets.token_urlsafe(24))).status_code == 403


@pytest.mark.parametrize('where', ['question', 'excerpt'])
def test_direct_merchant_context_rejects_sensitive_text(where):
    from pydantic import ValidationError
    from ayo.intelligence import MerchantInputContext, SourceEvidence
    evidence = SourceEvidence(id='input-fixture', url='workspace:input:abcdefghijklmnop', source_kind='OWNER_PROVIDED_UNVERIFIED',
        excerpt='A reusable bag product.', observed_at='2026-10-28T00:00:00Z')
    question = 'Review this offer.'
    if where == 'question':question = 'Email person@example.org'
    else:evidence = evidence.model_copy(update={'excerpt': 'api_key=private'})
    with pytest.raises(ValidationError):
        MerchantInputContext(country='GH', question=question, evidence=(evidence,))
