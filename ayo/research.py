"""Provider-backed public research with explicit evidence and permission gates.

No submitted URL is fetched by this process. The only network destination in the
production adapter is api.firecrawl.dev. Live use requires server-side provider
credentials, separately authorized spend, and operator-reviewed hosted egress and
source policies. These configuration attestations are not a claim that Firecrawl
or Ayo's production controls have been independently verified.

Official API contracts consulted 2026-10-26 (public documentation, no API calls):
https://docs.firecrawl.dev/api-reference/endpoint/search
https://docs.firecrawl.dev/api-reference/endpoint/crawl-post
https://docs.firecrawl.dev/api-reference/endpoint/crawl-get
https://docs.firecrawl.dev/api-reference/endpoint/crawl-delete
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from html import unescape
import json
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ayo.website_research import SiteInputError, extract_public_page, normalize_public_url
from ayo.intelligence import IntelligenceResult, PublicResearchContext, SourceEvidence, validate_analysis
from ayo.budgets import BudgetError
from ayo.provider_usage import metered_operation
from ayo.provider_config import valid_api_key

COUNTRY_NAMES = {"NG": "Nigeria", "GH": "Ghana"}
MAX_RESPONSE_BYTES = 1_000_000
MAX_SOURCE_CHARS = 60_000
MAX_SEARCH_RESULTS = 5
# A shared platform host cannot establish which merchant/profile was retrieved.
# Keep the exact public path/identity on these platforms; no guessed redirects.
SHARED_PUBLIC_HOSTS = frozenset({'facebook.com', 'm.facebook.com', 'instagram.com',
    'tiktok.com', 'x.com', 'twitter.com', 'jiji.ng', 'jiji.com.gh',
    'jumia.com.ng', 'jumia.com.gh', 'konga.com', 'tonaton.com', 'etsy.com'})


class ResearchError(Exception):
    """Stable public error; never carries provider bodies or credentials."""

    def __init__(self, code: str, message: str, status_code: int = 503):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _country(value: str) -> str:
    if value not in ("", "NG", "GH"):
        raise ResearchError("invalid_input", "Choose Nigeria or Ghana, or leave the market unselected.", 400)
    return value


def _text(value: str, limit: int, label: str = "Text") -> str:
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise ResearchError("invalid_input", f"{label} is invalid or exceeds its length limit.", 400)
    return re.sub(r"\s+", " ", value).strip()


def _public_url(value: str) -> str:
    try:
        url = normalize_public_url(value)
    except (ValueError, TypeError) as exc:
        raise ResearchError("invalid_url", "Enter a public business website or profile URL.", 400) from exc
    host = urlsplit(url).hostname or ""
    # The syntax-only legacy parser does not cover all legacy numeric aliases.
    if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", host, re.I):
        raise ResearchError("invalid_url", "Numeric network addresses are not supported.", 400)
    if host in {"metadata.google.internal", "metadata.google", "instance-data.ec2.internal"}:
        raise ResearchError("invalid_url", "Private network targets are not supported.", 400)
    if re.search(r"/(?:admin|wp-admin|wp-login\.php|account|accounts|login|logout|signin|sign-in|auth|oauth|api|graphql|private|internal|cart|checkout|password|reset-password|\.git|\.env)(?:/|$)", urlsplit(url).path, re.I):
        raise ResearchError("invalid_url", "Only public business pages may be researched.", 400)
    return url


def _candidate_identity(url: str) -> tuple[str, str, str]:
    """Deduplicate common URL aliases without merging distinct public profiles.

    This is an index-candidate heuristic, not proof of organization ownership or
    a redirect permission. The original validated URL stays attached as evidence.
    """
    parsed = urlsplit(url)
    host = (parsed.hostname or '').removeprefix('www.')
    return host, parsed.path.rstrip('/') or '/', parsed.query


def _ambiguous_profile(url: str) -> bool:
    parsed = urlsplit(url)
    return (parsed.hostname in {'facebook.com', 'www.facebook.com', 'm.facebook.com'}
            and parsed.path == '/profile.php' and not parsed.query)


def _same_research_target(requested_url: str, returned_url: str) -> bool:
    requested, returned = urlsplit(requested_url), urlsplit(returned_url)
    if requested.hostname != returned.hostname:
        return False
    host = (requested.hostname or '').removeprefix('www.')
    if host in SHARED_PUBLIC_HOSTS:
        return _candidate_identity(requested_url) == _candidate_identity(returned_url)
    return True


def _access_wall(content: str, title: str = '') -> bool:
    """Fail closed on common 200-status login/challenge placeholders.

    A normal public page may mention login in its navigation. Only recognizable
    leading challenge text or a challenge title is refused; no bypass is tried.
    """
    markers = ('just a moment', 'verify you are human', 'please verify you are human',
        'checking your browser', 'enable javascript and cookies to continue',
        'please enable javascript and cookies', 'access denied', 'request blocked',
        'log in to continue', 'login to continue', 'you must log in',
        "this page isn't available", 'this page is not available')
    for value in (title, content[:500]):
        normalized = re.sub(r'\s+', ' ', value).strip().lstrip('#* _').casefold()
        if any(normalized.startswith(marker) for marker in markers):
            return True
    return False


def _public_content(value: str) -> str:
    # Never render provider HTML. Strip executable blocks and redact contact PII
    # before persistence or any later model context. HTML remains untrusted data.
    value = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1\s*>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[email redacted]", value, flags=re.I)
    value = re.sub(r"(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)", "[phone redacted]", value)
    value = "".join(c for c in value if ord(c) >= 32 or c in "\n\t")
    return value.strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ResearchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PublicProduct(ResearchModel):
    name: str = Field(min_length=1, max_length=200)
    listed_price: str | None = Field(default=None, max_length=40)
    currency: str | None = Field(default=None, pattern=r'^[A-Z]{3}$')
    classification: Literal['PUBLIC_STRUCTURED_DATA_UNVERIFIED'] = 'PUBLIC_STRUCTURED_DATA_UNVERIFIED'

    @field_validator('listed_price')
    @classmethod
    def valid_price(cls, value):
        if value is not None:
            try:
                number = Decimal(value)
                if not number.is_finite() or number < 0:
                    raise ValueError('Invalid public price')
            except InvalidOperation as exc:
                raise ValueError('Invalid public price') from exc
        return value


class BusinessCandidate(ResearchModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=240)
    url: str
    snippet: str = Field(default="", max_length=600)
    country: Literal["", "NG", "GH"] = ""
    source_id: str = Field(min_length=1, max_length=120)
    discovered_at: datetime
    provider: str = Field(default="firecrawl", min_length=1, max_length=40)
    source_type: Literal["PUBLIC_SEARCH_INDEX"] = "PUBLIC_SEARCH_INDEX"
    ownership_verified: Literal[False] = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        return _public_url(value)

    @field_validator("discovered_at")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None:
            raise ValueError("Source timestamps must include timezone")
        return value


class SourceDocument(ResearchModel):
    id: str = Field(min_length=1, max_length=100)
    url: str
    retrieved_at: datetime
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str = Field(default="", max_length=240)
    excerpt: str = Field(min_length=1, max_length=600)
    content: str = Field(min_length=1, max_length=MAX_SOURCE_CHARS)
    provider: str = Field(min_length=1, max_length=40)
    provider_receipt_id: str = Field(min_length=1, max_length=120)
    robots_policy: Literal["PROVIDER_REQUESTED"] = "PROVIDER_REQUESTED"
    source_type: Literal["PUBLIC_WEB"] = "PUBLIC_WEB"
    html_source_hash: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    product_observations: tuple[PublicProduct, ...] = Field(default=(), max_length=20)
    channel_observations: tuple[str, ...] = Field(default=(), max_length=10)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        return _public_url(value)

    @field_validator("retrieved_at")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None:
            raise ValueError("Evidence timestamps must include timezone")
        return value

    @model_validator(mode="after")
    def coherent_snapshot(self):
        if hashlib.sha256(self.content.encode()).hexdigest() != self.source_hash:
            raise ValueError("Evidence content does not match its immutable hash")
        if self.excerpt not in self.content:
            raise ValueError("Evidence excerpt must occur in retained source content")
        if (self.product_observations or self.channel_observations) and not self.html_source_hash:
            raise ValueError('Public markup observations require their captured HTML hash')
        if any(product.name not in self.content for product in self.product_observations):
            raise ValueError('Product observations must be present in the retained evidence')
        if any(channel not in self.content for channel in self.channel_observations):
            raise ValueError('Channel observations must be present in the retained evidence')
        return self


class ReportClaim(ResearchModel):
    text: str = Field(min_length=1, max_length=800)
    kind: Literal["OBSERVED", "INFERRED", "UNKNOWN"]
    evidence_ids: tuple[str, ...] = ()
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def observed_requires_sources(self):
        if self.kind == "OBSERVED" and (not self.evidence_ids or self.observed_at is None):
            raise ValueError("Observed claims require evidence IDs and capture time")
        return self


class ReportOpportunity(ResearchModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=800)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    next_step: str = Field(min_length=1, max_length=500)
    classification: Literal["INFERRED"] = "INFERRED"
    status: Literal["PROPOSED"] = "PROPOSED"


class ResearchReport(ResearchModel):
    schema_version: Literal["1"] = "1"
    business_name: str = Field(min_length=1, max_length=240)
    target_url: str
    country: Literal["", "NG", "GH"] = ""
    status: Literal["SUCCEEDED", "PARTIAL"]
    source_documents: tuple[SourceDocument, ...] = Field(min_length=1, max_length=10)
    claims: tuple[ReportClaim, ...] = Field(max_length=40)
    opportunities: tuple[ReportOpportunity, ...] = Field(max_length=10)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=20)
    created_at: datetime
    website_ownership_verified: Literal[False] = False
    shopify_connected: Literal[False] = False
    analysis_status: Literal['not_requested', 'pending', 'completed', 'unavailable', 'rejected'] = 'not_requested'
    analysis: IntelligenceResult | None = None
    analysis_error_code: str | None = Field(default=None, pattern=r'^[a-z_]{1,80}$')

    def public_analysis_context(self):
        return PublicResearchContext(country=self.country,
            question=('Analyze this public business evidence: products, selling channels, buyer journey, '
                      'positioning and actionable improvements. Distinguish observations, hypotheses '
                      'and unknowns. Do not invent competitors or private metrics.'),
            evidence=tuple(SourceEvidence(id=source.id, url=source.url,
                excerpt=source.content[:4000], observed_at=source.retrieved_at,
                source_kind='PUBLIC_WEB') for source in self.source_documents[:6]))

    @field_validator("target_url")
    @classmethod
    def validate_url(cls, value):
        return _public_url(value)

    @model_validator(mode="after")
    def citation_integrity(self):
        ids = {source.id for source in self.source_documents}
        if len(ids) != len(self.source_documents):
            raise ValueError("Evidence identifiers must be unique")
        for claim in (*self.claims, *self.opportunities):
            if not set(claim.evidence_ids).issubset(ids):
                raise ValueError("Report cites evidence absent from its source documents")
        if self.analysis_status == 'completed':
            if (self.analysis is None or self.analysis.provider != 'gemini' or
                    not self.analysis.model or self.analysis.status != 'completed' or self.analysis_error_code):
                raise ValueError('Completed public analysis requires a Gemini result and no error')
            if not self.analysis.claims and not self.analysis.recommendations:
                raise ValueError('Completed public analysis requires source-backed findings')
            if self.analysis.generated_at.tzinfo is None:
                raise ValueError('AI result timestamp must include timezone')
            validate_analysis(self.analysis.model_dump(include={'claims', 'recommendations', 'limitations'}),
                              self.public_analysis_context())
        elif self.analysis is not None:
            raise ValueError('Unavailable or unfinished analysis cannot contain a generated result')
        if self.analysis_status in {'unavailable', 'rejected'}:
            if not self.analysis_error_code or self.status != 'PARTIAL':
                raise ValueError('Unavailable AI requires a partial report and a reason')
        elif self.analysis_error_code:
            raise ValueError('An unfinished or completed analysis cannot contain a failure code')
        return self


class ResearchProvider(Protocol):
    async def search(self, query: str, country: str = "", city: str = "", limit: int = 5) -> tuple[BusinessCandidate, ...]: ...
    async def fetch(self, url: str, country: str = "") -> SourceDocument: ...


class FirecrawlProvider:
    """Fixed-host API client. No local crawl, browser execution or bypass mode.

    Hosted egress/redirect safety remains a required operator/vendor acceptance
    gate. Source allowlisting provides an additional local boundary. API keys or
    a personal ChatGPT connector never imply authorization to incur API charges.
    """

    API_BASE = "https://api.firecrawl.dev/v2"

    def __init__(
        self, api_key: str, *, spend_authorized: bool = False,
        egress_policy_verified: bool = False, approved_hosts: tuple[str, ...] = (),
        transport: httpx.AsyncBaseTransport | None = None,
        poll_interval: float = 1.0, max_polls: int = 15, deadline_seconds: float = 35.0,
        dispatch_budget=metered_operation,
    ):
        if not valid_api_key(api_key):
            raise ResearchError("provider_not_configured", "Public research provider credentials are not configured.")
        if not spend_authorized:
            raise ResearchError("provider_spend_not_authorized", "Research provider spending has not been authorized.")
        if not 0 < deadline_seconds <= 45:
            raise ValueError('Research deadline must be positive and at most 45 seconds')
        self._api_key = api_key
        self._egress_policy_verified = egress_policy_verified
        self._approved_hosts = frozenset(approved_hosts)
        self._transport = transport
        self._poll_interval = max(0.0, min(poll_interval, 2.0))
        self._max_polls = max(1, min(max_polls, 20))
        self._deadline_seconds = deadline_seconds
        self._dispatch_budget = dispatch_budget

    @classmethod
    def from_env(cls):
        return cls(
            os.getenv("FIRECRAWL_API_KEY", ""),
            spend_authorized=os.getenv("AYO_PROVIDER_SPEND_AUTHORIZED") == "1",
            egress_policy_verified=os.getenv("AYO_RESEARCH_EGRESS_POLICY") == "provider_managed_verified",
            approved_hosts=tuple(h.strip().lower() for h in os.getenv("AYO_RESEARCH_APPROVED_HOSTS", "").split(",") if h.strip()),
        )

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        # Paths are internal constants or locally checked receipt IDs; never use
        # provider-returned polling URLs and never follow API redirects.
        try:
            # A direct scrape can take longer than an API status poll.
            # Bound it below the enclosing 35-second research deadline.
            deadline = 32.0 if method == "POST" and path == "/scrape" else 12.0
            async with asyncio.timeout(deadline), httpx.AsyncClient(
                timeout=httpx.Timeout(deadline), follow_redirects=False,
                transport=self._transport,
            ) as client:
                async with client.stream(
                    method, self.API_BASE + path, json=payload,
                    headers={"Authorization": "Bearer " + self._api_key, "Accept": "application/json"},
                ) as response:
                    if response.status_code in {401, 403}:
                        raise ResearchError("provider_authorization_failed", "Research provider access was rejected.")
                    if response.status_code == 429:
                        raise ResearchError("provider_rate_limited", "Research provider is temporarily rate limited.", 429)
                    if response.status_code == 402:
                        raise ResearchError("provider_budget_exhausted", "Research provider credits or access are unavailable.", 503)
                    if response.status_code in {408, 504}:
                        raise ResearchError("provider_timeout", "Research provider did not finish within its request deadline.", 504)
                    if response.status_code in {502, 503}:
                        raise ResearchError("provider_service_unavailable", "Research provider is temporarily unavailable.", 503)
                    if response.status_code != 200:
                        raise ResearchError("provider_failure", "Research provider could not complete this request.", 502)
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise ResearchError("provider_response_too_large", "Research provider response exceeded the safety limit.", 502)
                        chunks.append(chunk)
            body = json.loads(b"".join(chunks))
        except ResearchError:
            raise
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ResearchError("provider_timeout", "Research provider did not finish within its request deadline.", 504) from exc
        except (httpx.HTTPError, ValueError, TypeError, RecursionError) as exc:
            raise ResearchError("provider_failure", "Research provider is unavailable or returned invalid data.", 502) from exc
        if not isinstance(body, dict):
            raise ResearchError("provider_malformed", "Research provider returned malformed data.", 502)
        # Current v2 search/crawl-create use a success envelope. Crawl status
        # and cancellation instead return a status object. Do not reject valid
        # documented responses or accept an explicit failure/error as success.
        accepted = (body.get('success') is True if method == 'POST' else
                    body.get('success') is not False and 'error' not in body and isinstance(body.get('status'), str))
        if not accepted:
            raise ResearchError("provider_failure", "Research provider did not return a successful result.", 502)
        return body

    async def search(self, query: str, country: str = "", city: str = "", limit: int = 5) -> tuple[BusinessCandidate, ...]:
        query, country, city = _text(query, 250, 'Business search'), _country(country), _text(city, 100, 'City')
        if not query or type(limit) is not int or not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise ResearchError('invalid_input', 'Enter a business search and request at most five results.', 400)
        try:
            async with self._dispatch_budget('firecrawl', 'search') as debit:
                result = await self._search(query, country, city, limit)
                debit.usage['searches'] = 1
                return result
        except BudgetError as exc:
            raise ResearchError(exc.code, str(exc), 429 if exc.code == 'budget_exceeded' else 503) from exc

    async def _search(self, query: str, country: str = "", city: str = "", limit: int = 5) -> tuple[BusinessCandidate, ...]:
        query = _text(query, 250, "Business search")
        country = _country(country)
        city = _text(city, 100, "City")
        if not query or type(limit) is not int or not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise ResearchError("invalid_input", "Enter a business search and request at most five results.", 400)
        location = ", ".join(part for part in (city, COUNTRY_NAMES.get(country, "")) if part)
        payload = {"query": query, "limit": limit, "sources": ["web"], "timeout": 10000}
        if location:
            payload["location"] = location
        if country:
            # Firecrawl otherwise defaults geo-targeting to US. This biases
            # discovery toward the selected market; it does not prove domicile.
            payload['country'] = country
        body = await self._request("POST", "/search", payload)
        web = body.get("data", {}).get("web") if isinstance(body.get("data"), dict) else None
        if not isinstance(web, list):
            raise ResearchError("provider_malformed", "Research provider returned malformed search results.", 502)
        result, seen = [], set()
        for item in web[:MAX_SEARCH_RESULTS]:
            if not isinstance(item, dict):
                continue
            try:
                url = _public_url(item.get("url", ""))
                if not isinstance(item.get('title'), str) or not isinstance(item.get('description'), str):
                    continue
                title = _public_content(item['title']).strip()[:240]
                snippet = _public_content(item['description']).strip()[:600]
            except ResearchError:
                continue
            # Same canonical link appears once. Distinct marketplace profiles
            # may share a host and are not automatically the same organization.
            identity = _candidate_identity(url)
            if not title or len(snippet) < 20 or _access_wall(snippet, title) or _ambiguous_profile(url) or identity in seen:
                continue
            seen.add(identity)
            fingerprint = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:32]
            result.append(BusinessCandidate(
                id="candidate-" + fingerprint, name=title, url=url, snippet=snippet,
                country=country, source_id="search-" + fingerprint,
                discovered_at=_now(), provider="firecrawl",
            ))
        return tuple(result[:limit])

    async def fetch(self, url: str, country: str = "") -> SourceDocument:
        url, country = _public_url(url), _country(country)
        if _ambiguous_profile(url):
            raise ResearchError('invalid_url', 'Enter a public profile address with its numeric business identity.', 400)
        if not self._egress_policy_verified:
            raise ResearchError('research_egress_not_verified', 'Hosted crawl egress and redirect safety have not been verified.')
        if urlsplit(url).hostname not in self._approved_hosts:
            raise ResearchError('source_policy_not_approved', 'This source has not been approved under Ayo\'s public access policy.', 403)
        try:
            async with self._dispatch_budget('firecrawl', 'fetch') as debit:
                result = await self._fetch(url, country)
                debit.usage['pages'] = 1
                return result
        except BudgetError as exc:
            raise ResearchError(exc.code, str(exc), 429 if exc.code == 'budget_exceeded' else 503) from exc

    async def _fetch(self, url: str, country: str = "") -> SourceDocument:
        url = _public_url(url)
        country = _country(country)
        if _ambiguous_profile(url):
            raise ResearchError('invalid_url', 'Enter a public profile address with its numeric business identity.', 400)
        host = urlsplit(url).hostname
        if not self._egress_policy_verified:
            raise ResearchError("research_egress_not_verified", "Hosted crawl egress and redirect safety have not been verified.")
        if host not in self._approved_hosts:
            raise ResearchError("source_policy_not_approved", "This source has not been approved under Ayo's public access policy.", 403)
        scrape_options = {
            "formats": [{"type": "markdown"}, {"type": "html"}], "onlyMainContent": False,
            "skipTlsVerification": False, "timeout": 10000, "maxAge": 0,
            "proxy": "basic", "storeInCache": False, "redactPII": True,
            "blockAds": True, "parsers": [],
        }
        if country:
            scrape_options["location"] = {"country": country}
        if os.getenv("AYO_SINGLE_PAGE_FETCH_MODE") == "scrape":
            # A single URL should not incur an asynchronous crawl+poll cycle.
            # Do not fall back to crawl or retry after an uncertain paid dispatch.
            # Firecrawl's scrape API returns one data object, not a crawl status.
            try:
                async with asyncio.timeout(self._deadline_seconds):
                    body = await self._request("POST", "/scrape", {
                        "url": url, **scrape_options,
                    })
            except TimeoutError as exc:
                raise ResearchError("source_outcome_uncertain",
                    "The single-page provider request timed out; it was not retried.", 503) from exc
            page = body.get("data")
            if not isinstance(page, dict):
                raise ResearchError("source_unavailable",
                    "No readable public page was returned by the provider.", 502)
            completed = {"data": [page]}
            # /scrape has no provider-issued crawl receipt. This marker is a
            # LOCAL deterministic fingerprint, never represented as vendor ID.
            receipt = "local-scrape-" + hashlib.sha256(
                (url + json.dumps(page, sort_keys=True, default=str)).encode()
            ).hexdigest()[:32]
        else:
            receipt, completed, active = None, None, False
            try:
                # One absolute deadline covers creation AND every status request;
                # per-request HTTP timeouts alone would multiply across polls.
                async with asyncio.timeout(self._deadline_seconds):
                    body = await self._request("POST", "/crawl", {
                        "url": url, "limit": 1, "maxDiscoveryDepth": 0,
                        "sitemap": "skip", "crawlEntireDomain": False,
                        "allowExternalLinks": False, "allowSubdomains": False,
                        "ignoreRobotsTxt": False, "maxConcurrency": 1,
                        "scrapeOptions": scrape_options,
                    })
                    receipt = body.get("id")
                    if not isinstance(receipt, str) or not re.fullmatch(r"[a-zA-Z0-9-]{8,100}", receipt):
                        receipt = None
                        raise ResearchError("provider_malformed", "Research provider did not return a valid crawl receipt.", 502)
                    active = True
                    for attempt in range(self._max_polls):
                        try:
                            status = await self._request("GET", "/crawl/" + receipt)
                        except ResearchError as exc:
                            # A receipt proves the chargeable crawl was accepted.
                            # Rate/service errors while polling must never invite a
                            # fresh crawl as though the initial dispatch was denied.
                            if exc.code in {'provider_rate_limited', 'provider_service_unavailable'}:
                                raise ResearchError('source_outcome_uncertain',
                                    'The source request was accepted but its result could not be confirmed; it has not been retried.', 503) from exc
                            raise
                        if status.get("status") == "completed":
                            completed, active = status, False
                            break
                        if status.get("status") in {"failed", "cancelled"}:
                            active = False
                            raise ResearchError("source_unavailable", "The public source could not be retrieved under the access policy.", 502)
                        if status.get("status") not in {"scraping", "queued"}:
                            raise ResearchError("provider_malformed", "Research provider returned an invalid crawl state.", 502)
                        if attempt + 1 < self._max_polls:
                            await asyncio.sleep(self._poll_interval)
                    if completed is None:
                        raise ResearchError("research_timeout", "Research exceeded its bounded time budget; no completed report is available.", 504)
            except TimeoutError as exc:
                raise ResearchError("research_timeout", "Research exceeded its bounded time budget; no completed report is available.", 504) from exc
            finally:
                if active and receipt:
                    # A received receipt permits best-effort cancellation on timeout,
                    # transport error or worker cancellation. A two-second cleanup
                    # bound is additional to the research deadline. Cancellation is
                    # not a refund or proof of stopped/bill-free provider execution.
                    try:
                        async with asyncio.timeout(2):
                            await self._request("DELETE", "/crawl/" + receipt)
                    except (ResearchError, TimeoutError):
                        pass
        documents = completed.get("data")
        if not isinstance(documents, list) or len(documents) != 1 or not isinstance(documents[0], dict):
            raise ResearchError("source_unavailable", "No readable public page was returned; access may be blocked or disallowed.", 502)
        page = documents[0]
        metadata = page.get("metadata")
        if not isinstance(metadata, dict) or metadata.get("statusCode") != 200:
            raise ResearchError("source_unavailable", "The public page did not return a readable successful response.", 502)
        try:
            final_url = _public_url(metadata.get("url") or metadata.get("sourceURL") or "")
        except ResearchError as exc:
            raise ResearchError("provider_unsafe_redirect", "Research returned an unsafe source address.", 502) from exc
        if not _same_research_target(url, final_url):
            raise ResearchError("provider_unsafe_redirect", "Research redirected outside the approved source or selected public profile.", 502)
        raw_content = page.get("markdown")
        if not isinstance(raw_content, str) or len(raw_content) > MAX_SOURCE_CHARS:
            raise ResearchError("source_unavailable", "Source text is missing or exceeds the research size limit.", 502)
        content = _public_content(raw_content)
        title = _public_content(metadata.get('title') if isinstance(metadata.get('title'), str) else '')[:240]
        if _access_wall(content, title):
            raise ResearchError('source_access_restricted', 'The source returned a login or access challenge; no bypass was attempted.', 422)
        if len(content) < 30 or len(re.findall(r'\w+', content)) < 5:
            raise ResearchError("insufficient_evidence", "Not enough readable public evidence was retrieved to create a report.", 422)
        products, channels, html_hash = (), (), None
        html = page.get('html')
        if isinstance(html, str) and html:
            if len(html) > 300_000:
                raise ResearchError('source_unavailable', 'Public markup exceeded the extraction limit.', 502)
            html_hash = hashlib.sha256(html.encode()).hexdigest()
            parsed = extract_public_page(final_url, html)
            collected = []
            for item in parsed.product_structured_data:
                name = _public_content(item.get('name') or '')[:200]
                if not name:
                    continue
                price = str(item['price']) if item.get('price') is not None else None
                if price is not None and len(price) > 40:
                    price = None
                currency = item.get('priceCurrency')
                currency = currency.upper() if isinstance(currency, str) and re.fullmatch(r'[A-Za-z]{3}', currency) else None
                try:
                    product = PublicProduct(name=name, listed_price=price, currency=currency)
                except ValueError:
                    product = PublicProduct(name=name, currency=currency)
                if product not in collected:
                    collected.append(product)
            products = tuple(collected[:20])
            hosts = {urlsplit(link).hostname for link in parsed.links}
            known = {'WhatsApp': {'wa.me', 'api.whatsapp.com', 'whatsapp.com'},
                     'Instagram': {'instagram.com', 'www.instagram.com'},
                     'Facebook': {'facebook.com', 'www.facebook.com'},
                     'TikTok': {'tiktok.com', 'www.tiktok.com'},
                     'Jiji': {'jiji.ng', 'jiji.com.gh'}, 'Jumia': {'jumia.com.ng', 'jumia.com.gh'}}
            channels = tuple(name for name, domains in known.items() if hosts & domains)
            if products or channels:
                appendix = '\n\nPUBLIC MARKUP OBSERVATIONS (UNVERIFIED):\n' + json.dumps(
                    {'listed_products': [p.model_dump() for p in products], 'linked_channels': channels}, ensure_ascii=False)
                content = content[:MAX_SOURCE_CHARS - len(appendix)] + appendix
        digest = hashlib.sha256(content.encode()).hexdigest()
        return SourceDocument(
            id="source-" + digest[:32], url=final_url, retrieved_at=_now(), source_hash=digest,
            title=title,
            excerpt=content[:600], content=content, provider="firecrawl",
            provider_receipt_id=receipt,
            html_source_hash=html_hash, product_observations=products, channel_observations=channels,
        )


class ResearchService:
    def __init__(self, provider: ResearchProvider):
        self.provider = provider

    @classmethod
    def from_env(cls):
        return cls(FirecrawlProvider.from_env())

    async def search(self, query: str, country: str = "", city: str = "", limit: int = 5) -> tuple[BusinessCandidate, ...]:
        query = _text(query, 250, "Business search")
        country = _country(country)
        city = _text(city, 100, "City")
        if not query or type(limit) is not int or not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise ResearchError("invalid_input", "Enter a business search and request at most five results.", 400)
        values = await self.provider.search(query, country, city, limit)
        if not isinstance(values, (tuple, list)):
            raise ResearchError("provider_malformed", "Research provider returned malformed candidates.", 502)
        result, seen = [], set()
        for value in values[:limit]:
            try:
                candidate = BusinessCandidate.model_validate(value)
            except (ValueError, TypeError, ResearchError) as exc:
                raise ResearchError("provider_malformed", "Research provider returned an invalid candidate.", 502) from exc
            identity = _candidate_identity(candidate.url)
            if identity not in seen:
                seen.add(identity)
                result.append(candidate)
        return tuple(result)

    async def research(self, url: str, country: str = "", business_name: str = "") -> ResearchReport:
        url = _public_url(url)
        country = _country(country)
        business_name = _text(business_name, 240, "Business name")
        source = await self.provider.fetch(url, country)
        try:
            source = SourceDocument.model_validate(source)
        except (ValueError, TypeError, ResearchError) as exc:
            raise ResearchError("provider_malformed", "Research provider returned invalid evidence.", 502) from exc
        if not _same_research_target(url, source.url):
            raise ResearchError("provider_unsafe_redirect", "Evidence does not match the requested business host or public profile.", 502)
        return build_report(source, country=country, business_name=business_name)


def build_report(source: SourceDocument, *, country: str = "", business_name: str = "") -> ResearchReport:
    """Rules-based evidence analysis. No LLM, execution, or financial inference.

    Observed claims describe the returned source text, not verified ownership or
    factual truth of a merchant's marketing claims. Proposed improvements are
    hypotheses with a review step, never measured revenue/conversion promises.
    """
    country = _country(country)
    source = SourceDocument.model_validate(source)
    ids = (source.id,)
    claims = [ReportClaim(
        text="The retrieved public page contains this excerpt: “" + source.excerpt[:480] + "”",
        kind="OBSERVED", evidence_ids=ids, observed_at=source.retrieved_at,
    )]
    opportunities = []
    for product in source.product_observations:
        price = f' Listed price: {product.currency or "currency not established"} {product.listed_price}.' if product.listed_price is not None else ' A usable listed price was not established.'
        claims.append(ReportClaim(text=f'Public product markup names “{product.name}”.' + price + ' This is not verified stock, checkout or sales data.',
                                  kind='OBSERVED', evidence_ids=ids, observed_at=source.retrieved_at))
    if not source.product_observations:
        claims.append(ReportClaim(text='A structured product catalog was not established from the retrieved source. Products may exist on other pages or selling channels.', kind='UNKNOWN', evidence_ids=ids))
    for channel in source.channel_observations:
        claims.append(ReportClaim(text=f'The public page includes a link to {channel}. The profile ownership and functioning sales process are not verified.',
                                  kind='OBSERVED', evidence_ids=ids, observed_at=source.retrieved_at))
    lower = source.content.casefold()
    checks = [
        ("delivery", ("delivery", "shipping", "dispatch"), "Clarify delivery coverage", "Review whether your public page clearly explains delivery locations, charges and timing."),
        ("returns", ("return", "refund", "exchange policy"), "Make returns easy to find", "Review a concise returns, refund and exchange policy for your actual selling channels."),
        ("selling channels", ("whatsapp", "instagram", "marketplace", "add to cart", "shop now", "buy now"), "Make the next buying step clear", "Review the route from product discovery to an authorized order or business enquiry."),
    ]
    for topic, words, title, next_step in checks:
        if any(word in lower for word in words):
            # Presence of exact text only; no claim that delivery/payment works.
            found = next(word for word in words if word in lower)
            claims.append(ReportClaim(
                text=f'The retrieved page mentions “{found}” in its public text.',
                kind="OBSERVED", evidence_ids=ids, observed_at=source.retrieved_at,
            ))
        else:
            claims.append(ReportClaim(
                text=f"The retrieved page sample does not establish {topic}; other pages may contain this information.",
                kind="UNKNOWN", evidence_ids=ids,
            ))
            opportunities.append(ReportOpportunity(
                title=title,
                description=f"A clearer explanation of {topic} may help customers decide what to do next. This is a hypothesis based only on the retrieved page sample.",
                evidence_ids=ids, next_step=next_step,
            ))
    if country:
        term = "NGN" if country == "NG" else "GHS"
        mentions = term.casefold() in lower
        claims.append(ReportClaim(
            text=(f"The public text contains the currency label {term}; actual transactions and settlement are not verified."
                  if mentions else f"The retrieved text does not establish pricing in {term}; no currency has been inferred."),
            kind="OBSERVED" if mentions else "UNKNOWN", evidence_ids=ids,
            observed_at=source.retrieved_at if mentions else None,
        ))
    claims.append(ReportClaim(text="Revenue, conversion, stock, customer counts and payment settlement cannot be determined from public page text.", kind="UNKNOWN"))
    return ResearchReport(
        business_name=business_name or source.title or urlsplit(source.url).hostname or "Public business",
        target_url=source.url, country=country, status="PARTIAL",
        source_documents=(source,), claims=tuple(claims), opportunities=tuple(opportunities),
        limitations=(
            "Coverage is one permitted public page, not the full website or product catalog.",
            "Public page statements are unverified merchant claims; ownership and store authorization are separate.",
            "Robots compliance and controlled egress were requested from the configured hosted provider; independent vendor acceptance remains required.",
            "Source-observation opportunities are rules-based hypotheses. Any Gemini analysis is labeled separately; no business outcomes have been verified.",
        ), created_at=_now(),
    )
