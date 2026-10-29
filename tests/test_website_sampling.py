"""Multi-page sampling with explicit HTTP/model fixtures; no external calls."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ayo import app as mod
from ayo.direct_website import DirectWebsiteProvider
from ayo.jobs import process_one
from ayo.models import ResearchJob, ResearchReportRecord
from ayo.research import ResearchError, ResearchReport, ResearchService
from ayo.website_sampling import selected_page_links
from test_direct_website_source import Client, response, ROBOTS
from test_platform_flow import platform, csrf, register, verify_latest  # noqa: F401


ROOT = 'https://sample-shop.org/'
PRODUCT = ROOT + 'products/fixture-tote'
POLICY = ROOT + 'policies/shipping-and-returns'


def run(coro):
    return asyncio.run(coro)


def fixture_client(*, robots=ROBOTS, product_status=200):
    homepage = (f'<html><title>Fixture bag studio</title><h1>Our handmade bags</h1>'
        f'<p>A synthetic shop used only to verify research coverage.</p>'
        f'<a href="{PRODUCT}">Browse products</a><a href="{POLICY}">Delivery and returns policy</a>'
        f'<a href="{ROOT}products/ignored">Another product</a>'
        '<a href="https://different.org/products/unrelated">External product</a></html>').encode()
    product = b'''<html><title>Fixture tote listing</title><h1>Fixture tote</h1>
        <p>Public listing used only in offline tests. No real inventory or sales.</p>
        <script type="application/ld+json">{"@type":"Product","name":"Fixture tote","offers":{"price":"125","priceCurrency":"GHS"}}</script></html>'''
    policy = b'<html><title>Fixture policy</title><h1>Shipping and returns</h1><p>Fixture delivery terms and refund policy for this offline sample.</p></html>'
    return Client({ROOT + 'robots.txt': [response(ROOT + 'robots.txt', robots, content_type='text/plain')],
        ROOT: [response(ROOT, homepage)], PRODUCT: [response(PRODUCT, product, status=product_status)],
        POLICY: [response(POLICY, policy)]})


def test_selects_actual_same_site_product_and_policy_without_guessing_or_query_conflation():
    links = ('https://different.org/products/wrong', ROOT + 'checkout', ROOT + 'products/file.pdf',
             ROOT + 'products/query?id=123', ROOT + 'products/first?utm_source=fixture',
             ROOT + 'products/second', POLICY, ROOT + 'about', ROOT + 'products/first#details')
    assert selected_page_links(ROOT, links) == (ROOT + 'products/first', POLICY)
    assert selected_page_links('https://facebook.com/fixture-shop',
                               ('https://facebook.com/products/different-business',)) == ()
    assert selected_page_links(ROOT, ('http://sample-shop.org/products/insecure',)) == ()


@pytest.mark.parametrize('path', ['catalogue/books', 'category/bags', 'product-category/accessories'])
def test_selects_actual_catalogue_and_singular_category_paths(path):
    assert selected_page_links(ROOT, (ROOT + path, POLICY)) == (ROOT + path, POLICY)


def test_three_page_report_attaches_products_and_policy_to_the_correct_evidence():
    client = fixture_client()
    report = run(ResearchService(DirectWebsiteProvider(client)).research(ROOT, 'GH'))
    assert client.calls == [ROOT + 'robots.txt', ROOT, PRODUCT, POLICY]
    assert len(report.source_documents) == 3 and len({s.id for s in report.source_documents}) == 3
    product = report.source_documents[1]
    claims = [claim for claim in report.claims if 'Public product markup' in claim.text]
    assert len(claims) == 1 and claims[0].evidence_ids == (product.id,)
    assert 'GHS 125' in claims[0].text and report.status == 'PARTIAL'
    assert not any(claim.kind == 'UNKNOWN' and 'structured product catalog' in claim.text for claim in report.claims)
    assert any('not a complete business audit' in value for value in report.limitations)
    assert len(report.public_analysis_context().evidence) == 3
    assert ResearchReport.model_validate_json(report.model_dump_json()) == report


def test_linked_robots_denial_never_fetches_or_creates_fake_product_evidence():
    client = fixture_client(robots=b'User-agent: *\nAllow: /\nDisallow: /products/\n')
    report = run(ResearchService(DirectWebsiteProvider(client)).research(ROOT, 'GH'))
    assert PRODUCT not in client.calls and client.calls == [ROOT + 'robots.txt', ROOT, POLICY]
    assert len(report.source_documents) == 2
    assert all(not source.product_observations for source in report.source_documents)
    assert any('robots_denied' in item for item in report.limitations)
    assert any(claim.kind == 'UNKNOWN' and 'structured product catalog' in claim.text for claim in report.claims)


def test_rate_limited_link_stops_sampling_and_keeps_initial_evidence():
    client = fixture_client(product_status=429)
    report = run(ResearchService(DirectWebsiteProvider(client)).research(ROOT))
    assert POLICY not in client.calls
    assert len(report.source_documents) == 1
    assert any('provider_rate_limited' in note for note in report.limitations)


def test_shared_deadline_retains_homepage_and_does_not_start_later_links():
    client = fixture_client()
    fast = client.fetch_once

    async def delayed(url):
        if url == PRODUCT:
            await asyncio.sleep(0.05)
        return await fast(url)

    client.fetch_once = delayed
    bundle = run(DirectWebsiteProvider(client, deadline_seconds=0.01).fetch_bundle(ROOT))
    assert len(bundle.sources) == 1 and POLICY not in client.calls
    assert any('deadline' in value for value in bundle.limitations)


def test_crawl_delay_is_respected_within_the_shared_deadline():
    client = fixture_client(robots=b'User-agent: *\nAllow: /\nCrawl-delay: 10\n')
    bundle = run(DirectWebsiteProvider(client, deadline_seconds=0.01).fetch_bundle(ROOT))
    assert client.calls == [ROOT + 'robots.txt', ROOT]
    assert len(bundle.sources) == 1 and any('deadline' in value for value in bundle.limitations)


def test_identical_retained_text_on_distinct_pages_has_distinct_source_ids():
    client = fixture_client()
    same = (f'<html><h1>Identical public fixture page</h1><p>Shared public text from this offline sample.</p>'
            f'<a href="{PRODUCT}">Product</a><a href="{POLICY}">Policy</a></html>').encode()
    for url in (ROOT, PRODUCT, POLICY):
        client.responses[url] = [response(url, same)]
    report = run(ResearchService(DirectWebsiteProvider(client)).research(ROOT))
    assert len({source.source_hash for source in report.source_documents}) == 1
    assert len({source.id for source in report.source_documents}) == 3


def test_configured_cc0_discovery_still_routes_ordinary_sites_to_direct_sampling(monkeypatch):
    client = fixture_client()
    provider = DirectWebsiteProvider(client)
    monkeypatch.setenv('AYO_RESEARCH_SOURCE', 'wikidata_cc0')
    monkeypatch.setattr('ayo.direct_website.DirectWebsiteProvider', lambda: provider)
    report = run(ResearchService.from_env().research(ROOT))
    assert len(report.source_documents) == 3 and client.calls == [ROOT + 'robots.txt', ROOT, PRODUCT, POLICY]


def test_optional_firecrawl_sampling_does_not_expand_provider_operations(monkeypatch):
    from test_research_engine import source
    calls = []

    class OnePage:
        async def fetch(self, url, country=''):
            calls.append((url, country))
            return source()

    monkeypatch.setenv('AYO_RESEARCH_SOURCE', 'firecrawl')
    monkeypatch.setattr('ayo.research.FirecrawlProvider.from_env', lambda: OnePage())
    report = run(ResearchService.from_env().research('https://merchant.org/', 'GH'))
    assert len(report.source_documents) == 1 and calls == [('https://merchant.org/', 'GH')]


@pytest.mark.parametrize('country', ['NG', 'GH'])
def test_sampled_worker_commits_all_sources_claims_reopens_and_exports_isolated(platform, monkeypatch, country):
    client = fixture_client()
    monkeypatch.setenv('AYO_AI_DATA_POLICY', 'public_only_reviewed')
    monkeypatch.setattr(mod.app.state, 'research_factory', lambda: ResearchService(DirectWebsiteProvider(client)))
    queued = platform.client.post('/research', data={'query': ROOT, 'country': country, 'csrf': csrf(platform.client)})
    assert queued.status_code == 303 and client.calls == []
    job_path = queued.headers['location']
    job_id = job_path.rsplit('/', 1)[1]
    model_calls = []

    class GeminiFixture:
        name, model = 'gemini', 'offline-multi-page-fixture'

        async def complete(self, _system, context):
            with platform.factory() as session:
                row = session.get(ResearchJob, job_id)
                saved = session.get(ResearchReportRecord, row.report_id)
                pending = ResearchReport.model_validate_json(saved.report_json)
                assert saved.status == 'PENDING_ANALYSIS' and len(pending.source_documents) == 3
            assert len(context['evidence']) == 3
            model_calls.append(context)
            product_id = next(source['id'] for source in context['evidence'] if source['url'] == PRODUCT)
            return {'claims': [{'text': 'The public product listing may benefit from clearer category context.',
                'kind': 'INFERRED', 'quote': '', 'evidence_ids': [product_id]}],
                'recommendations': [{'text': 'Review the cited product listing before making changes.',
                    'evidence_ids': [product_id], 'permission_required': 'merchant_review'}],
                'limitations': ['Synthetic offline response; no business outcome verified.']}, {'totalTokenCount': 10}

    assert run(process_one(platform.factory, mod.fernet, mod.app.state.research_factory, analysis_provider=GeminiFixture()))
    assert len(model_calls) == 1 and client.calls == [ROOT + 'robots.txt', ROOT, PRODUCT, POLICY]
    finished = platform.client.get(job_path)
    report_path = finished.headers['location']
    page = platform.client.get(report_path)
    assert page.status_code == 200 and 'offline-multi-page-fixture' in page.text
    source_id = model_calls[0]['evidence'][1]['id']
    assert 'href="#source-' + source_id + '">Source 2' in page.text
    with TestClient(mod.app, base_url='http://testserver', follow_redirects=False) as stranger:
        assert stranger.get(report_path).status_code == 404
    register(platform.client, 'sample-owner@example.org')
    assert verify_latest(platform.client, platform.factory).status_code == 303
    with platform.factory() as session:
        row = session.get(ResearchJob, job_id)
        report_id = row.report_id
        original = session.get(ResearchReportRecord, report_id).report_json
    assert platform.client.post('/logout', data={'csrf': csrf(platform.client, '/work')}).status_code == 303
    assert platform.client.post('/login', data={'csrf': csrf(platform.client, '/login'),
        'email': 'sample-owner@example.org', 'password': 'FixturePassword123!'}).status_code == 303
    assert platform.client.get(report_path).status_code == 200
    export = platform.client.get('/research/library/' + report_id + '/export').json()
    assert len(export['sources']) == 3 and {source['url'] for source in export['sources']} == {ROOT, PRODUCT, POLICY}
    with platform.factory() as session:
        assert session.get(ResearchReportRecord, report_id).report_json == original
        assert len(json.loads(original)['source_documents']) == 3


def test_malformed_multi_page_bundle_is_rejected_before_report_publication():
    from ayo.website_sampling import WebsiteEvidence

    class Empty:
        async def fetch_bundle(self, _url, _country):
            return WebsiteEvidence(())

    with pytest.raises(ResearchError) as error:
        run(ResearchService(Empty()).research(ROOT))
    assert error.value.code == 'provider_malformed'
