"""Provider-backed public research with explicit evidence and permission gates.

No submitted URL is fetched by this process. The only network destination in the
production adapter is api.firecrawl.dev. Live use requires server-side provider
credentials, separately authorized spend, and operator-reviewed hosted egress and
source policies. These configuration attestations are not a claim that Firecrawl
or Ayo's production controls have been independently verified.

Official API contracts consulted 2026-10-25:
https://docs.firecrawl.dev/api-reference/endpoint/search
https://docs.firecrawl.dev/api-reference/endpoint/crawl-post
https://docs.firecrawl.dev/api-reference/endpoint/crawl-get
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
from html import unescape
import json
import os
import re
import time
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ayo.website_research import SiteInputError, normalize_public_url

COUNTRY_NAMES = {"NG": "Nigeria", "GH": "Ghana"}
MAX_RESPONSE_BYTES = 1_000_000
MAX_SOURCE_CHARS = 60_000
MAX_SEARCH_RESULTS = 5


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
    if re.search(r"/(?:admin|account|accounts|login|signin|sign-in|cart|checkout)(?:/|$)", urlsplit(url).path, re.I):
        raise ResearchError("invalid_url", "Only public business pages may be researched.", 400)
    return url


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
        poll_interval: float = 1.0, max_polls: int = 15,
    ):
        if not api_key or not api_key.strip():
            raise ResearchError("provider_not_configured", "Public research provider credentials are not configured.")
        if not spend_authorized:
            raise ResearchError("provider_spend_not_authorized", "Research provider spending has not been authorized.")
        self._api_key = api_key
        self._egress_policy_verified = egress_policy_verified
        self._approved_hosts = frozenset(approved_hosts)
        self._transport = transport
        self._poll_interval = max(0.0, min(poll_interval, 2.0))
        self._max_polls = max(1, min(max_polls, 20))

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
            async with asyncio.timeout(12.0), httpx.AsyncClient(
                timeout=httpx.Timeout(12.0), follow_redirects=False,
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
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError) as exc:
            raise ResearchError("provider_failure", "Research provider is unavailable or returned invalid data.", 502) from exc
        if not isinstance(body, dict) or body.get("success") is not True:
            raise ResearchError("provider_failure", "Research provider did not return a successful result.", 502)
        return body

    async def search(self, query: str, country: str = "", city: str = "", limit: int = 5) -> tuple[BusinessCandidate, ...]:
        query = _text(query, 250, "Business search")
        country = _country(country)
        city = _text(city, 100, "City")
        if not query or not 1 <= limit <= MAX_SEARCH_RESULTS:
            raise ResearchError("invalid_input", "Enter a business search and request at most five results.", 400)
        location = ", ".join(part for part in (city, COUNTRY_NAMES.get(country, "")) if part)
        payload = {"query": query, "limit": limit, "sources": ["web"]}
        if location:
            payload["location"] = location
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
                title = _public_content(str(item.get("title", ""))).strip()[:240]
                snippet = _public_content(str(item.get("description", ""))).strip()[:600]
            except ResearchError:
                continue
            # Same canonical link appears once. Distinct marketplace profiles
            # may share a host and are not automatically the same organization.
            if not title or url in seen:
                continue
            seen.add(url)
            fingerprint = hashlib.sha256(url.encode()).hexdigest()[:32]
            result.append(BusinessCandidate(
                id="candidate-" + fingerprint, name=title, url=url, snippet=snippet,
                country=country, source_id="search-" + fingerprint,
                discovered_at=_now(), provider="firecrawl",
            ))
        return tuple(result[:limit])

    async def fetch(self, url: str, country: str = "") -> SourceDocument:
        url = _public_url(url)
        country = _country(country)
        host = urlsplit(url).hostname
        if not self._egress_policy_verified:
            raise ResearchError("research_egress_not_verified", "Hosted crawl egress and redirect safety have not been verified.")
        if host not in self._approved_hosts:
            raise ResearchError("source_policy_not_approved", "This source has not been approved under Ayo's public access policy.", 403)
        scrape_options = {
            "formats": [{"type": "markdown"}], "onlyMainContent": True,
            "skipTlsVerification": False, "timeout": 10000, "maxAge": 0,
            "proxy": "basic", "storeInCache": False, "redactPII": True,
            "blockAds": True, "parsers": [],
        }
        if country:
            scrape_options["location"] = {"country": country}
        body = await self._request("POST", "/crawl", {
            "url": url, "limit": 1, "maxDiscoveryDepth": 0,
            "sitemap": "skip", "crawlEntireDomain": False,
            "allowExternalLinks": False, "allowSubdomains": False,
            "ignoreRobotsTxt": False, "maxConcurrency": 1,
            "scrapeOptions": scrape_options,
        })
        receipt = body.get("id")
        if not isinstance(receipt, str) or not re.fullmatch(r"[a-zA-Z0-9-]{8,100}", receipt):
            raise ResearchError("provider_malformed", "Research provider did not return a valid crawl receipt.", 502)
        completed = None
        deadline = time.monotonic() + 35
        for attempt in range(self._max_polls):
            if time.monotonic() >= deadline:
                break
            status = await self._request("GET", "/crawl/" + receipt)
            if status.get("status") == "completed":
                completed = status
                break
            if status.get("status") in {"failed", "cancelled"}:
                raise ResearchError("source_unavailable", "The public source could not be retrieved under the access policy.", 502)
            if status.get("status") not in {"scraping", "queued"}:
                raise ResearchError("provider_malformed", "Research provider returned an invalid crawl state.", 502)
            if attempt + 1 < self._max_polls:
                await asyncio.sleep(self._poll_interval)
        if completed is None:
            # Stop provider work on this bounded request rather than leave an
            # uncontrolled background crawl. Cancellation is best-effort.
            try:
                await self._request("DELETE", "/crawl/" + receipt)
            except ResearchError:
                pass
            raise ResearchError("research_timeout", "Research exceeded its bounded time budget; no completed report is available.", 504)
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
        if urlsplit(final_url).hostname != host:
            raise ResearchError("provider_unsafe_redirect", "Research redirected outside the approved source host.", 502)
        raw_content = page.get("markdown")
        if not isinstance(raw_content, str) or len(raw_content) > MAX_SOURCE_CHARS:
            raise ResearchError("source_unavailable", "Source text is missing or exceeds the research size limit.", 502)
        content = _public_content(raw_content)
        if len(content) < 30:
            raise ResearchError("insufficient_evidence", "Not enough readable public evidence was retrieved to create a report.", 422)
        digest = hashlib.sha256(content.encode()).hexdigest()
        return SourceDocument(
            id="source-" + digest[:32], url=final_url, retrieved_at=_now(), source_hash=digest,
            title=_public_content(str(metadata.get("title", "")))[:240],
            excerpt=content[:600], content=content, provider="firecrawl",
            provider_receipt_id=receipt,
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
        if not query or not 1 <= limit <= MAX_SEARCH_RESULTS:
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
            if candidate.url not in seen:
                seen.add(candidate.url)
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
        if urlsplit(source.url).hostname != urlsplit(url).hostname:
            raise ResearchError("provider_unsafe_redirect", "Evidence does not match the requested business host.", 502)
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
            "Recommendations are deterministic hypotheses, not generated AI responses or verified business outcomes.",
        ), created_at=_now(),
    )
