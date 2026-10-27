"""Actual saved-record persistence and HTTP isolation; all evidence is offline."""
from datetime import datetime, timedelta, timezone
import hashlib
import json

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from ayo import app as mod
from ayo.identity import IdentityError, IdentityService
from ayo.intelligence import IntelligenceResult
from ayo.models import Business, Membership, ResearchReportRecord, User
from ayo.report_storage import ReportStore
from ayo.research import PublicProduct, SourceDocument, ResearchReport, build_report
from ayo.research_workspace import LibraryFilters, ResearchWorkspace, canonical_target
from test_platform_flow import platform, csrf, register, verify_latest  # noqa: F401

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def account(platform):
    register(platform.client, 'research-owner@example.org')
    assert verify_latest(platform.client, platform.factory).status_code == 303
    with platform.factory() as session:
        user = session.scalar(select(User))
        membership = session.scalar(select(Membership).where(Membership.user_id == user.id))
        return user.id, membership.business_id


def document(*, source_id='exact-evidence:one', url='https://fixture-shop.org/',
             captured=NOW, price='50.00', text=None, product=True, category=True, channel=True):
    text = text or ('Fixture Tote listed for ' + (price or 'an unstated price') + '.\n' +
                    ('Category: Accessories\n' if category else '') +
                    ('Instagram\n' if channel else '') + 'Delivery on request.\nContact fixture@example.org.')
    return SourceDocument(id=source_id, url=url, retrieved_at=captured,
        title='Offline Fixture Shop', excerpt=text[:300], content=text,
        source_hash=hashlib.sha256(text.encode()).hexdigest(),
        html_source_hash=hashlib.sha256(('markup ' + text).encode()).hexdigest(),
        product_observations=(PublicProduct(name='Fixture Tote', listed_price=price, currency='GHS'),) if product else (),
        channel_observations=('Instagram',) if channel else (),
        provider='offline-fixture', provider_receipt_id='do-not-export-provider-receipt')


def report(source=None, *, name='Offline Fixture Shop', ai=False, extra_sources=()):
    source = source or document()
    initial = build_report(source, country='GH', business_name=name)
    data = initial.model_dump()
    data.update(created_at=source.retrieved_at, source_documents=(source, *extra_sources))
    if ai:
        quote = source.content.splitlines()[0]
        data.update(analysis_status='completed', analysis=IntelligenceResult(
            status='completed', provider='gemini', model='offline-fixture-model',
            summary='Offline fixture synthesis', generated_at=source.retrieved_at,
            claims=({'text': quote, 'quote': quote, 'kind': 'OBSERVED', 'evidence_ids': (source.id,)},
                    {'text': 'Review the public product description.', 'kind': 'INFERRED', 'evidence_ids': (source.id,)}),
            recommendations=({'text': 'Review delivery information with the business owner.', 'evidence_ids': (source.id,),
                              'permission_required': 'merchant_review'},),
            limitations=('Offline fixture. No real model request.',)))
    return ResearchReport.model_validate(data)


def saved(factory, user_id, business_id, value, *, when=NOW):
    with factory() as session:
        store = ReportStore(session, clock=lambda: when.timestamp())
        row, token = store.save_preview(value, 'fixture-anonymous-session-' + 'x' * 32)
        store.claim(token, 'fixture-anonymous-session-' + 'x' * 32, user_id, business_id)
        session.commit()
        return row.id


def test_saved_history_inspection_and_source_bound_ai_persist_unchanged(platform):
    user_id, business_id = account(platform)
    older = saved(platform.factory, user_id, business_id,
        report(document(url='http://www.fixture-shop.org/', captured=NOW - timedelta(days=20), price='40.00')),
        when=NOW - timedelta(days=20))
    newer = saved(platform.factory, user_id, business_id, report(ai=True))
    with platform.factory() as session:
        originals = {row.id: row.report_json for row in session.scalars(select(ResearchReportRecord))}
        view = ResearchWorkspace(session, clock=lambda: NOW.timestamp()).inspect(user_id, business_id, newer)
        assert view['history_count'] == 2
        assert {row['id'] for row in view['history']} == {older, newer}
        assert view['products'][0]['listed_price'] == '50.00'
        assert view['categories'][0]['text'] == 'Category: Accessories'
        assert view['channels'][0]['text'] == 'Instagram'
        assert any(item['kind'] == 'UNKNOWN' for item in view['claims'])
        ai_claim = next(item for item in view['claims'] if item['origin'] == 'AI-generated')
        assert ai_claim['citations']['ids'] == ('exact-evidence:one',)
        assert ai_claim['citations']['links'][0] == {'id': 'exact-evidence:one', 'number': 1}
        assert any(item['origin'] == 'AI-generated proposal' for item in view['recommendations'])
        assert view['work_url'] == '/work?source_report_id=' + newer
        assert {row.id: row.report_json for row in session.scalars(select(ResearchReportRecord))} == originals
    inspection = platform.client.get('/research/library/' + newer)
    assert inspection.status_code == 200, inspection.text
    assert 'Source ID exact-evidence:one' in inspection.text
    assert 'href="#source-1"' in inspection.text
    assert 'AI-generated' in inspection.text and 'No supporting citation attached' in inspection.text
    assert 'source_report_id=' + newer in inspection.text


def test_library_filters_counts_pagination_freshness_and_unknowns(platform):
    user_id, business_id = account(platform)
    fresh = saved(platform.factory, user_id, business_id, report())
    stale = saved(platform.factory, user_id, business_id,
        report(document(captured=NOW - timedelta(days=14)), name='Old Fixture'), when=NOW - timedelta(days=14))
    future = saved(platform.factory, user_id, business_id,
        report(document(captured=NOW + timedelta(hours=1), product=False, channel=False, category=False), name='Future Fixture'))
    with platform.factory() as session:
        workspace = ResearchWorkspace(session, clock=lambda: NOW.timestamp())
        all_rows = workspace.library(user_id, business_id, LibraryFilters.parse({'page_size': '1'}))
        assert all_rows['total'] == all_rows['matched'] == 3
        assert len(all_rows['items']) == 1 and all_rows['page_count'] == 3
        assert all_rows['partial_count'] == 3 and all_rows['source_count'] == 3
        assert all_rows['stale_count'] == 1 and all_rows['freshness_days'] == 14
        for state, expected in [('fresh', fresh), ('stale', stale), ('unknown', future)]:
            rows = workspace.library(user_id, business_id, LibraryFilters.parse({'freshness': state}))
            assert rows['matched'] == 1 and rows['items'][0]['id'] == expected
        filtered = workspace.library(user_id, business_id, LibraryFilters.parse({'q': 'Old Fixture',
            'status': 'PARTIAL', 'date_from': '2026-10-12', 'date_to': '2026-10-12'}))
        assert filtered['matched'] == 1 and filtered['items'][0]['id'] == stale
        assert workspace.library(user_id, business_id, LibraryFilters.parse({'q': '%'}))['matched'] == 0
        unknown = workspace.inspect(user_id, business_id, future)
        assert unknown['products'] == unknown['channels'] == unknown['categories'] == []
        assert unknown['freshness'] == 'unknown'
    response = platform.client.get('/research/library?page_size=1')
    assert response.status_code == 200, response.text
    assert '3 matching reports' in response.text and '14 days' in response.text
    assert response.text.count('class="rw-library-record"') == 1
    assert 'page=2' in response.text
    assert 'No structured product observations were retained' in platform.client.get('/research/library/' + future).text


@pytest.mark.parametrize('values', [
    {'q': 'x' * 121}, {'q': 'bad\nfilter'}, {'target': 'https://127.0.0.1/'},
    {'target': 'javascript:alert(1)'}, {'status': 'PENDING_ANALYSIS'}, {'freshness': 'verified'},
    {'date_from': '2026-02-30'}, {'date_from': '2026-10-26', 'date_to': '2026-10-25'},
    {'page': '0'}, {'page': '-1'}, {'page': '100001'}, {'page_size': '51'}, {'page_size': 'true'},
    {'unknown_filter': 'value'},
])
def test_filter_input_is_bounded(values):
    with pytest.raises(IdentityError) as error:
        LibraryFilters.parse(values)
    assert error.value.status_code == 400


def test_private_current_workspace_cannot_read_other_membership_pending_or_anonymous(platform):
    user_id, business_id = account(platform)
    own = saved(platform.factory, user_id, business_id, report(name='Permitted saved fixture'))
    with platform.factory() as session:
        other = IdentityService(session).create_business(user_id, 'Second permitted workspace', 'GH')
        other_id = other.id
        session.commit()
    foreign = saved(platform.factory, user_id, other_id, report(name='Different workspace secret title'))
    with platform.factory() as session:
        store = ReportStore(session, clock=lambda: NOW.timestamp())
        pending = store.stage_preview(report(name='Hidden evidence checkpoint'), 'pending-anonymous-' + 'z' * 32)
        preview, _ = store.save_preview(report(name='Anonymous private preview'), 'preview-anonymous-' + 'y' * 32)
        expired, _ = store.save_preview(report(name='Expired anonymous preview'), 'expired-anonymous-' + 'x' * 32)
        expired.expires_at = NOW.timestamp() - 1
        session.commit()
        hidden_ids = [pending.id, preview.id, expired.id]
    library = platform.client.get('/research/library')
    assert library.status_code == 200
    assert 'Permitted saved fixture' in library.text
    assert 'Different workspace secret title' not in library.text
    assert 'Hidden evidence checkpoint' not in library.text
    assert 'Anonymous private preview' not in library.text
    for report_id in [foreign, *hidden_ids]:
        assert platform.client.get('/research/library/' + report_id).status_code == 404
        assert platform.client.get('/research/library/' + report_id + '/export').status_code == 404
        assert platform.client.get('/research/compare', params={'left': own, 'right': report_id}).status_code == 404
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as anonymous:
        assert anonymous.get('/research/library').status_code in {303, 401}
        register(anonymous, 'different-research-user@example.org')
        assert anonymous.get('/research/library/' + own).status_code == 404
    switched = platform.client.post('/business/switch', data={'csrf': csrf(platform.client, '/dashboard'), 'business_id': other_id})
    assert switched.status_code == 303
    assert platform.client.get('/research/library/' + foreign).status_code == 200
    assert platform.client.get('/research/library/' + own).status_code == 404


def test_comparison_uses_actual_snapshots_and_never_hash_compares_distinct_targets(platform):
    user_id, business_id = account(platform)
    left = saved(platform.factory, user_id, business_id, report(document(price='40.00')), when=NOW - timedelta(days=1))
    right = saved(platform.factory, user_id, business_id, report(document(price='50.00')))
    different = saved(platform.factory, user_id, business_id,
        report(document(url='https://other-fixture-shop.org/', source_id='other-source', price='90.00'), name='Other Fixture'))
    with platform.factory() as session:
        workspace = ResearchWorkspace(session, clock=lambda: NOW.timestamp())
        comparison = workspace.compare(user_id, business_id, left, right)
        assert comparison['mode'] == 'history' and comparison['left_is_earlier']
        assert comparison['hash_comparison'][0]['status'] == 'changed'
        assert comparison['price_differences'][0]['left']['listed_price'] == '40.00'
        assert comparison['price_differences'][0]['right']['listed_price'] == '50.00'
        assert comparison['deltas']['products']['shared_count'] == 0
        assert comparison['deltas']['channels']['shared_count'] == 1
        distinct = workspace.compare(user_id, business_id, left, different)
        assert distinct['mode'] == 'distinct_targets' and distinct['hash_comparison'] == []
        assert not distinct['merchant_assessment']
        assert workspace.compare(user_id, business_id, left, different, 'merchant_assessed_competitor')['merchant_assessment']
    response = platform.client.get('/research/compare', params={'left': left, 'right': right})
    assert response.status_code == 200, response.text
    assert 'Same-page hash comparison' in response.text and 'changed' in response.text
    assert 'left-source-1' in response.text and 'right-source-1' in response.text
    distinct_html = platform.client.get('/research/compare', params={'left': left, 'right': different})
    assert distinct_html.status_code == 200 and 'No relationship asserted' in distinct_html.text
    chosen = platform.client.get('/research/compare', params={'left': left, 'right': different, 'label': 'merchant_assessed_competitor'})
    assert chosen.status_code == 200 and 'Merchant assessment' in chosen.text
    for params in [{'left': left, 'right': left}, {'left': left}, {'left': left, 'right': right, 'label': 'verified_competitor'},
                   {'left': left, 'right': right, 'label': 'merchant_assessed_competitor'},
                   [('left', left), ('right', right), ('right', different)]]:
        assert platform.client.get('/research/compare', params=params).status_code == 400
    assert platform.client.get('/research/library?q=a&q=b').status_code == 400


def test_source_conflicts_require_distinct_pages_and_export_is_minimized_redacted(platform):
    user_id, business_id = account(platform)
    # An opaque citation may resemble contact data. Export must preserve its
    # identity while redacting actual contact text in the source excerpt.
    first = document(price='40.00', source_id='233201234567')
    second = document(price='50.00', source_id='second-capture', url='https://fixture-shop.org/products/tote')
    duplicate = document(price='60.00', source_id='third-capture')
    report_id = saved(platform.factory, user_id, business_id, report(first, extra_sources=(second, duplicate)))
    with platform.factory() as session:
        workspace = ResearchWorkspace(session, clock=lambda: NOW.timestamp())
        view = workspace.inspect(user_id, business_id, report_id)
        assert len(view['conflicts']) == 2
        assert all(canonical_target(item['left']['source_url']) != canonical_target(item['right']['source_url']) for item in view['conflicts'])
        second_id = saved(platform.factory, user_id, business_id, report(document(price='40.00')))
        comparison = workspace.compare(user_id, business_id, report_id, second_id)
        assert any(item['status'] == 'not_comparable' for item in comparison['hash_comparison'])
    exported = platform.client.get('/research/library/' + report_id + '/export')
    assert exported.status_code == 200
    assert exported.headers['content-disposition'] == 'attachment; filename="ayo-research-' + report_id + '.json"'
    assert exported.headers['cache-control'] == 'private, no-store'
    data = exported.json()
    assert data['ownership_verified'] is False and data['report_id'] == report_id
    assert 'fixture@example.org' not in exported.text and '[email redacted]' in exported.text
    assert 'do-not-export-provider-receipt' not in exported.text
    assert 'owner_user_id' not in exported.text and 'business_id' not in exported.text
    assert 'anonymous_session_hash' not in exported.text
    assert 'content' not in data['sources'][0] and 'provider_receipt_id' not in data['sources'][0]
    assert data['sources'][0]['source_hash'] == first.source_hash
    assert data['sources'][0]['id'] == '233201234567'
    assert data['claims'][0]['evidence_ids'] == ['233201234567']


def test_canonical_history_preserves_public_profile_and_page_identity():
    assert canonical_target('http://www.fixture-shop.org/about/') == canonical_target('https://fixture-shop.org/about')
    assert canonical_target('https://fixture-shop.org/about') != canonical_target('https://fixture-shop.org/')
    assert canonical_target('https://www.facebook.com/profile.php?id=123') != canonical_target('https://www.facebook.com/profile.php?id=456')
    assert canonical_target('https://m.facebook.com/public-shop/') == canonical_target('https://facebook.com/public-shop')
