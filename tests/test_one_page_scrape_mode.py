"""One-page scrape adapter contract. No external provider requests."""
import asyncio
import json
from contextlib import nullcontext

import httpx
import pytest

from ayo.provider_usage import OperationUsage
from ayo.research import FirecrawlProvider, ResearchError


def invoke(coro):
    return asyncio.run(coro)


def test_single_page_scrape_avoids_crawl_polling(monkeypatch):
    monkeypatch.setenv("AYO_SINGLE_PAGE_FETCH_MODE", "scrape")
    captured = []
    def handler(request):
        captured.append(request)
        assert request.method == "POST"
        assert request.url == "https://api.firecrawl.dev/v2/scrape"
        payload = json.loads(request.content)
        assert payload["url"] == "https://merchant.org/"
        assert payload["proxy"] == "basic"
        assert payload["skipTlsVerification"] is False
        assert payload["redactPII"] is True
        assert payload["storeInCache"] is False
        assert not payload.get("actions")
        return httpx.Response(200, json={"success": True, "data": {
            "markdown": "Fixture business sells shirts and publishes prices. No revenue is verified.",
            "metadata": {"sourceURL": "https://merchant.org/", "statusCode": 200, "title": "Fixture Store"},
        }})
    provider = FirecrawlProvider(
        "fixture-key", spend_authorized=True, egress_policy_verified=True,
        approved_hosts=("merchant.org",), transport=httpx.MockTransport(handler),
        dispatch_budget=lambda *_args: nullcontext(OperationUsage()),
    )
    result = invoke(provider.fetch("https://merchant.org/"))
    assert result.title == "Fixture Store"
    assert result.provider_receipt_id.startswith("local-scrape-")
    assert len(captured) == 1


def test_single_page_scrape_rejects_cross_domain_redirect(monkeypatch):
    monkeypatch.setenv("AYO_SINGLE_PAGE_FETCH_MODE", "scrape")
    def handler(_):
        return httpx.Response(200, json={"success": True, "data": {
            "markdown": "Fixture business sells shirts and publishes prices. No revenue is verified.",
            "metadata": {"sourceURL": "https://other.example/", "statusCode": 200},
        }})
    provider = FirecrawlProvider(
        "fixture-key", spend_authorized=True, egress_policy_verified=True,
        approved_hosts=("merchant.org",), transport=httpx.MockTransport(handler),
        dispatch_budget=lambda *_args: nullcontext(OperationUsage()),
    )
    with pytest.raises(ResearchError) as exc:
        invoke(provider.fetch("https://merchant.org/"))
    assert exc.value.code == "provider_unsafe_redirect"


def test_single_page_scrape_keeps_egress_and_host_checks(monkeypatch):
    monkeypatch.setenv("AYO_SINGLE_PAGE_FETCH_MODE", "scrape")
    def forbidden(_):
        raise AssertionError("Blocked requests must never reach the provider")
    p = FirecrawlProvider("fixture-key", spend_authorized=True,
        egress_policy_verified=False, approved_hosts=("merchant.org",),
        transport=httpx.MockTransport(forbidden),
        dispatch_budget=lambda *_args: nullcontext(OperationUsage()))
    with pytest.raises(ResearchError) as exc:
        invoke(p.fetch("https://merchant.org/"))
    assert exc.value.code == "research_egress_not_verified"
