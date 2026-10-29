"""Offline regression fixtures only; no live Firecrawl/source/business claims."""
import asyncio
from contextlib import nullcontext
import json

import httpx
import pytest

from ayo.provider_usage import OperationUsage
from ayo.research import FirecrawlProvider, ResearchError, ResearchService
from ayo.website_research import SiteInputError, normalize_public_url


def run(coro):
    return asyncio.run(coro)


def provider(handler, **options):
    # The transport never leaves this process. Real constructors retain their
    # persistent-budget guard; this bypass is explicit fixture injection only.
    options.setdefault('dispatch_budget', lambda *_args: nullcontext(OperationUsage()))
    options.setdefault('approved_hosts', ('merchant.org',))
    return FirecrawlProvider('offline-fixture-only', spend_authorized=True,
        egress_policy_verified=True,
        transport=httpx.MockTransport(handler), poll_interval=0, **options)


def page(**metadata):
    return {'markdown': 'Fixture merchant publishes handmade clothing and delivery terms for its public storefront.',
        'metadata': {'sourceURL': 'https://merchant.org/', 'statusCode': 200, **metadata}}


@pytest.mark.parametrize(('country', 'city', 'location'), [('NG', 'Lagos', 'Lagos, Nigeria'), ('GH', 'Accra', 'Accra, Ghana')])
def test_selected_market_sets_explicit_country_and_location(country, city, location):
    def handler(request):
        payload = json.loads(request.content)
        assert payload['country'] == country
        assert payload['location'] == location
        assert 'scrapeOptions' not in payload  # Index lookup does not silently scrape results.
        return httpx.Response(200, json={'success': True, 'data': {'web': [
            {'title': 'Fixture merchant', 'url': 'https://merchant.org/',
             'description': 'A fixture business index description with no verified ownership or domicile.'}]}})
    result = run(provider(handler).search('Fixture merchant', country, city))
    assert result[0].country == country and result[0].ownership_verified is False


def test_unselected_market_remains_unknown_and_has_no_invented_country():
    def handler(request):
        payload = json.loads(request.content)
        assert 'country' not in payload and 'location' not in payload
        return httpx.Response(200, json={'success': True, 'data': {'web': [
            {'title': 'Fixture merchant', 'url': 'https://merchant.org/',
             'description': 'A fixture public company description with no established country.'}]}})
    result = run(provider(handler).search('Fixture merchant'))
    assert result[0].country == ''


@pytest.mark.parametrize('path', [
    '/%61dmin', '/%2561dmin', '/public/%2e%2e/admin', '/public/../admin',
    '/products%2fcheckout', '/products%252fcheckout', '/ADMIN;public', '/admin%3bpublic',
    '/safe%5cadmin', '/safe%255cadmin', '/%00products', '/safe%0d%0aX-Header:evil',
    '/%ZZ', '/%252525252561dmin', '/api/orders', '/.env', '/.git/config', '/wp-login.php',
])
def test_encoded_and_nonpublic_paths_never_reach_network(path):
    def unexpected(_):
        raise AssertionError('A private path reached the provider')
    with pytest.raises(ResearchError) as error:
        run(provider(unexpected).fetch('https://merchant.org' + path))
    assert error.value.code == 'invalid_url'


def test_profile_identity_is_preserved_without_tracking_or_credentials():
    value = normalize_public_url('https://www.facebook.com/profile.php?id=12345&utm_source=test&access_token=discard#about')
    assert value == 'https://www.facebook.com/profile.php?id=12345'
    # Previously stored generic URLs remain parseable; fresh fetches require ID.
    assert normalize_public_url('https://facebook.com/profile.php') == 'https://facebook.com/profile.php'
    with pytest.raises(ResearchError):
        run(provider(lambda _: pytest.fail('Ambiguous profile was fetched')).fetch('https://facebook.com/profile.php'))


@pytest.mark.parametrize('query', ['id=abc', 'id=123&id=456', 'access_token=discard'])
def test_malformed_profile_identity_is_not_silently_changed(query):
    with pytest.raises(SiteInputError):
        normalize_public_url('https://facebook.com/profile.php?' + query)


def test_search_deduplicates_url_aliases_and_keeps_distinct_profile_ids():
    urls = ['http://www.merchant.org/?utm_source=one', 'https://merchant.org/',
        'https://facebook.com/profile.php?id=123&utm_source=two',
        'https://facebook.com/profile.php?id=123', 'https://facebook.com/profile.php?id=456']
    def handler(_):
        return httpx.Response(200, json={'success': True, 'data': {'web': [
            {'title': 'Fixture public business', 'url': url,
             'description': 'A public fixture business index description with attributable source URL.'} for url in urls]}})
    results = run(ResearchService(provider(handler)).search('Fixture businesses'))
    assert len(results) == 3
    assert {r.url for r in results if 'facebook.com' in r.url} == {
        'https://facebook.com/profile.php?id=123', 'https://facebook.com/profile.php?id=456'}
    assert len({r.id for r in results}) == 3


def test_title_only_missing_or_access_wall_search_candidates_are_not_evidence():
    descriptions = [None, '', 'too short', {'invented': 'text'}, 'Log in to continue viewing this public profile.']
    def handler(_):
        return httpx.Response(200, json={'success': True, 'data': {'web': [
            {'title': 'Fixture merchant', 'url': f'https://merchant.org/{i}', 'description': value}
            for i, value in enumerate(descriptions)]}})
    assert run(provider(handler).search('Fixture merchant')) == ()


def test_current_crawl_status_contract_does_not_require_success_envelope():
    def handler(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
        return httpx.Response(200, json={'status': 'completed', 'data': [page()], 'creditsUsed': 1})
    report = run(ResearchService(provider(handler)).research('https://merchant.org/'))
    assert report.status == 'PARTIAL'
    assert report.source_documents[0].provider_receipt_id == 'fixture-job-12345'


@pytest.mark.parametrize(('status', 'code'), [(402, 'provider_budget_exhausted'), (408, 'provider_timeout'),
    (502, 'provider_service_unavailable'), (503, 'provider_service_unavailable'), (504, 'provider_timeout')])
def test_provider_budget_timeout_and_service_errors_are_sanitized(status, code):
    def handler(_):
        return httpx.Response(status, json={'error': 'private upstream diagnostic'})
    with pytest.raises(ResearchError) as error:
        run(provider(handler).search('Fixture merchant'))
    assert error.value.code == code
    assert 'private upstream diagnostic' not in str(error.value)


@pytest.mark.parametrize(('content', 'title'), [
    ('# Just a moment\nChecking your browser before accessing this website.', ''),
    ('Please verify you are human before viewing this public business page.', ''),
    ('Log in to continue viewing this page. Account registration is required.', ''),
    ('Some fixture page text that is long enough to appear to be useful business evidence.', 'Access denied'),
])
def test_http_200_access_wall_is_refused_without_bypass(content, title):
    def handler(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
        data = page(title=title)
        data['markdown'] = content
        return httpx.Response(200, json={'status': 'completed', 'data': [data]})
    with pytest.raises(ResearchError) as error:
        run(provider(handler).fetch('https://merchant.org/'))
    assert error.value.code == 'source_access_restricted'


def test_navigation_login_link_does_not_turn_public_business_evidence_into_access_wall():
    def handler(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
        data = page()
        data['markdown'] += ' Customer login is available beside the public catalog.'
        return httpx.Response(200, json={'status': 'completed', 'data': [data]})
    assert run(provider(handler).fetch('https://merchant.org/')).content


def test_absolute_fetch_deadline_includes_slow_crawl_creation():
    calls = []
    async def handler(request):
        calls.append(request.method)
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
    with pytest.raises(ResearchError) as error:
        run(provider(handler, deadline_seconds=0.01).fetch('https://merchant.org/'))
    assert error.value.code == 'research_timeout'
    assert calls == ['POST']  # No known receipt; stopped execution or refund cannot be claimed.


def test_absolute_deadline_cancels_received_crawl_with_current_cancel_contract():
    calls = []
    async def handler(request):
        calls.append(request.method)
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
        if request.method == 'GET':
            await asyncio.sleep(0.05)
            return httpx.Response(200, json={'status': 'scraping'})
        return httpx.Response(200, json={'status': 'cancelled'})
    with pytest.raises(ResearchError) as error:
        run(provider(handler, deadline_seconds=0.01).fetch('https://merchant.org/'))
    assert error.value.code == 'research_timeout'
    assert calls == ['POST', 'GET', 'DELETE']


def test_ambiguous_poll_transport_failure_cancels_without_retry():
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
        if request.method == 'GET':
            raise httpx.ReadTimeout('Do not publish private upstream diagnostics')
        return httpx.Response(200, json={'status': 'cancelled'})
    with pytest.raises(ResearchError) as error:
        run(provider(handler).fetch('https://merchant.org/'))
    assert error.value.code == 'provider_timeout'
    assert calls == ['POST', 'GET', 'DELETE']
    assert 'private' not in str(error.value)


def test_worker_cancellation_attempts_cancel_and_does_not_become_success():
    calls = []
    async def scenario():
        waiting = asyncio.Event()
        async def handler(request):
            calls.append(request.method)
            if request.method == 'POST':
                return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
            if request.method == 'GET':
                waiting.set()
                await asyncio.Event().wait()
            return httpx.Response(200, json={'status': 'cancelled'})
        task = asyncio.create_task(provider(handler).fetch('https://merchant.org/'))
        await waiting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    run(scenario())
    assert calls == ['POST', 'GET', 'DELETE']


@pytest.mark.parametrize('status', [429, 502, 503])
def test_poll_rejection_after_accepted_crawl_is_uncertain_and_not_fresh_retry(status):
    calls = []
    def handler(request):
        calls.append(request.method)
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
        if request.method == 'GET':
            return httpx.Response(status, json={'error': 'private upstream diagnostic'})
        return httpx.Response(200, json={'status': 'cancelled'})
    with pytest.raises(ResearchError) as error:
        run(provider(handler).fetch('https://merchant.org/'))
    assert error.value.code == 'source_outcome_uncertain'
    assert calls == ['POST', 'GET', 'DELETE']


@pytest.mark.parametrize(('requested', 'returned'), [
    ('https://facebook.com/profile.php?id=123', 'https://facebook.com/profile.php?id=456'),
    ('https://instagram.com/fixture-one/', 'https://instagram.com/fixture-two/'),
    ('https://jiji.ng/seller-one', 'https://jiji.ng/seller-two'),
    ('https://www.jumia.com.gh/fixture-one/', 'https://www.jumia.com.gh/fixture-two/'),
])
def test_shared_host_different_profile_redirect_is_not_the_selected_business(requested, returned):
    from urllib.parse import urlsplit
    def handler(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
        return httpx.Response(200, json={'status': 'completed', 'data': [page(sourceURL=returned)]})
    with pytest.raises(ResearchError) as error:
        run(provider(handler, approved_hosts=(urlsplit(requested).hostname,)).fetch(requested))
    assert error.value.code == 'provider_unsafe_redirect'


@pytest.mark.parametrize(('requested', 'returned'), [
    ('https://facebook.com/profile.php?id=123&utm_source=discard', 'https://facebook.com/profile.php?id=123'),
    ('https://instagram.com/fixture-one', 'https://instagram.com/fixture-one/'),
    ('https://merchant.org/about', 'https://merchant.org/about-us'),
])
def test_same_profile_canonical_alias_or_ordinary_samehost_redirect_stays_usable(requested, returned):
    from urllib.parse import urlsplit
    def handler(request):
        if request.method == 'POST':
            return httpx.Response(200, json={'success': True, 'id': 'fixture-job-12345'})
        return httpx.Response(200, json={'status': 'completed', 'data': [page(sourceURL=returned)]})
    result = run(provider(handler, approved_hosts=(urlsplit(requested).hostname,)).fetch(requested))
    assert result.url == returned


def test_service_rechecks_shared_profile_binding_for_every_provider_adapter():
    import hashlib
    from datetime import datetime, timezone
    from ayo.research import SourceDocument
    class OfflineProvider:
        async def fetch(self, url, country=''):
            content = 'Explicit offline fixture evidence for a different public business profile.'
            return SourceDocument(id='fixture-other-profile', url='https://facebook.com/profile.php?id=456',
                retrieved_at=datetime.now(timezone.utc), source_hash=hashlib.sha256(content.encode()).hexdigest(),
                excerpt=content, content=content, provider='offline-fixture', provider_receipt_id='fixture-only')
    with pytest.raises(ResearchError) as error:
        run(ResearchService(OfflineProvider()).research('https://facebook.com/profile.php?id=123'))
    assert error.value.code == 'provider_unsafe_redirect'


@pytest.mark.parametrize('value', [None, 123, {}, ['https://merchant.org/']])
def test_malformed_index_urls_are_omitted_and_not_server_failures(value):
    def handler(_):
        return httpx.Response(200, json={'success': True, 'data': {'web': [
            {'title': 'Fixture merchant', 'url': value,
             'description': 'Explicit offline fixture description containing enough public text.'}]}})
    assert run(provider(handler).search('Fixture merchant')) == ()


def test_mock_transport_without_explicit_budget_injection_still_fails_closed():
    def unexpected(_):
        raise AssertionError('A budgetless default dispatch reached even a mock network')
    guarded = FirecrawlProvider('offline-fixture-only', spend_authorized=True,
        egress_policy_verified=True, approved_hosts=('merchant.org',), transport=httpx.MockTransport(unexpected))
    with pytest.raises(ResearchError) as error:
        run(guarded.search('Fixture merchant', 'GH'))
    assert error.value.code == 'budget_not_configured'
    with pytest.raises(ResearchError) as error:
        run(guarded.fetch('https://merchant.org/'))
    assert error.value.code == 'budget_not_configured'
