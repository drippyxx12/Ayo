# 13 — Website investigation implementation and security policy

**Goal:** search by name or URL and analyze real **public** business websites, not steal data or confuse site access with merchant authorization.

## A. Discovery
- A `SearchProvider` abstraction accepts normalized merchant-search text, country/language optional and budget, returns candidate domains/URLs with source/country/time and result IDs. Use a commercial search API with explicit contract and billing, respecting its terms. Provider credentials only on server. No unverified scraping of search engines; do not scrape Google result pages as an undocumented integration.
- Search results are hints, not verified facts. Apply stable deduplication by registrable domain, homonym warnings and source citations. Candidate selection must be explicit for ambiguous brands; search providers can return stale URLs.
- Direct URL path uses the same validation and crawl rules. A company name is *not* assumed to be an authenticated website.

## B. URL / SSRF defensive specification (critical)
- Only `http://` and `https://` public domain hosts; prefer HTTPS. Reject scheme-less opaque paths, credentials in URL, embedded control characters, malformed IDNA, ports except 80/443 for external research, and URLs longer than configured cap.
- Resolve hostnames under **controlled outbound egress that pins vetted public IP addresses**; reject private, link-local, loopback, reserved, multicast, unspecified, IPv4-mapped IPv6, metadata services, DNS rebinding and IPv6 internal ranges. Validate **each** redirect hop (including HTTPS-to-HTTP policy), not just first URL. DNS-precheck alone is vulnerable to time-of-check/time-of-use and is NOT enough.
- Outbound proxy or fetcher must connect to the checked/pinned public IP while preserving original Host and TLS SNI verification. Block proxy env bypass, arbitrary proxy headers, WebSockets, ftp, file, gopher, data, Unix sockets and cloud-instance metadata. Limit cross-host redirect count. Distinguish canonical redirects from permission to crawl another unrelated domain.
- Egress network firewall or network policy is mandatory defense-in-depth. The parser should not execute scripts, browser extensions or page-provided JavaScript in the API/worker process.

## C. Crawl policy
- Fetch `robots.txt` with declared user agent (e.g. `AyoResearchBot/0.1 (+https://ayo.../bot)` **only after an actual bot policy/contact URL exists**). Honor disallow rules and conservative crawl delays; also respect legitimate terms/legal and site opt-out.
- Bounded run: page cap, body size per page, content-type allowlist (text/html; later optional safe PDFs), redirect limit, depth, total bytes, concurrency/per-origin budget, deadline and storage cap. No brute force, no blocked pages, login walls, bypassing CAPTCHAs or exploring customer accounts.
- Discover canonical home and links; `sitemap.xml` optionally for preferred product/category URLs; avoid pagination explosion, arbitrary query params, tracking links, carts, checkout, sign-in, forms, robots-excluded paths, downloads and personal account pages.
- Cache based on URL canonicalization and content hash; dedupe and avoid constant rescans. Content snapshots carry `fetched_at`, exact URL, HTTP status, content hash, `robots_decision`, mime type, language, canonical and crawl job ID.

## D. Extraction / provenance
- Parse response in a bounded, non-executing HTML extractor, handle charset safely; sanitize scripts/styles/comments, bound visible text; sanitize links and avoid storing PII/private messages.
- Extract title, meta description, headings, category, product schema.org JSON-LD when present, public prices with currency when explicit, return/shipping/contact/FAQ page visibility, CTA text, product links and canonical metadata. A site may not expose all products — **never assert complete inventory from a crawl**.
- Separate 1) observed facts 2) deterministic measurements 3) model observations/hypotheses 4) recommended actions. Never convert an inference to verified financial metric.
- Every finding must reference `evidence_item_ids`, URL, capture timestamp, exact short excerpt or structured field, extraction version and confidence. When source inaccessible, return an honest `blocked/inaccessible/partial` finding.
- For competitive research, report only publicly visible features; label market positioning as a hypothesis and never manufacture actual competitor sales, margins or ad ROAS.

## E. RAG and prompt-injection defenses
- Snapshot evidence is untrusted. Strip known HTML instructions/script tags, but *do not* assume stripping solves prompt injection. Embed only normalized bounded content as data with tool provenance, never as user/system instructions.
- Retrieval filter includes tenant + research-run access rights + source classification; deny cross-tenant leakage even through vector search. Store embeddings only after approved provider policies/retention checks.
- Model tool calls require server-side policy checks regardless of model output. Webpage instructions such as `download /admin` or `send us your key` are ignored.
- No raw HTML or tokens in external LLM prompts by default; minimize merchant PII; handle opt-outs and deletion.

## F. Execution isolation
- Research service has **no** provider write token and cannot call write adapters. Website research can create proposals; merchant action workflow requires a separate actor/approved capabilities and idempotency.
- Report access: anonymous one-off research versus authenticated workspace ownership scoped; public domain alone does not link records to a business. Respect retention for anonymous scans.

## G. Deterministic safety tests
Test URL payloads including: `http://127.0.0.1`, `http://[::1]`, `http://169.254.169.254/latest/meta-data/`, private RFC1918, decimal/hex/octal IP aliases, localhost suffixes, `file://`, `http://user:pw@domain`, homograph/IDN, DNS CNAME to private, DNS switch after validation, 302→localhost, redirect chain, zip bomb, oversized gzip content, non-HTML content, malformed JSON-LD, robots Disallow, infinite dynamic links, fake structured-data currency and page-level prompt injection. Use a test egress proxy to confirm bypass attempts cannot escape. Tests must **not** call untrusted live hosts in CI.

## Research result contract
```json
{
  "research_run_id": "uuid",
  "requested_query": "user's company name or URL",
  "selected_site_url": "https://shop.example/",
  "ownership": "not_verified",
  "status": "completed | partial | blocked | failed",
  "coverage": {"pages_visited": 7, "pages_skipped": 2},
  "fetched_at": "ISO-8601",
  "findings": [{"type": "product_schema", "statement": "Observed public product structured data", "evidence_ids": ["evidence_uuid"], "confidence": "high"}],
  "financial_metrics_available": false,
  "limits": ["Public website analysis cannot determine sales or conversion"]
}
```
Only illustrative **schema values**, not a claim that any website has been scanned.
