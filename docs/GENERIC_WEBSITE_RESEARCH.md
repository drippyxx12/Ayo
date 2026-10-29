# Generic public website research

**29 October hosted acceptance:** one actual protected-staging worker command retained3 Books to Scrape public-demo pages, published a visible source-only report and reopened unchanged hashes. Gemini/Firecrawl/mail0, provider chargeUSD0. [Receipt](evidence/hosted-source-only-worker.json), [bounded worker-host contract](ON_DEMAND_RESEARCH_WORKER.md). This extends the historical single-page transport proof below; it does not establish universal domain support, merchant identity or AI/full-audit quality.

Updated 28 October 2026. Ayo's existing leased research worker now accepts a user-supplied ordinary public HTTP or HTTPS website without requiring a Firecrawl host allowlist or paid crawler call. The web request only queues encrypted work; the worker performs every source request.

**29 October extension:** ordinary direct-website jobs now sample up to three relevant linked pages under one shared deadline and retain separate citations. [Current multi-page contract](MULTI_PAGE_RESEARCH.md). The one-page live transport receipt below remains historical; multi-page behavior is verified separately with fixtures.

## Supported website behavior

The direct adapter is platform-neutral. Static HTML, server-rendered WordPress, Shopify and WooCommerce pages use the same path. Ayo checks `/robots.txt`, retrieves one selected page, extracts readable text, title/description/headings, public Product JSON-LD and links to known selling channels, redacts email addresses and phone numbers, then stores the final URL, capture time, content hash, raw HTML hash and access-policy result before Gemini is considered.

The transport accepts only normalized public `http`/`https` domain names on their standard ports80/443. It resolves all destination addresses and refuses the whole request if any address is private, loopback, link-local, multicast, unspecified or IPv4-mapped. The connection is pinned to a validated public address while TLS certificate verification, SNI and `Host` retain the submitted hostname. An inherited HTTP CONNECT proxy is supported without delegating DNS identity to it. Responses use identity encoding, a declared Ayo user agent and a one-megabyte body/parser limit. A45-second total retrieval deadline covers robots and all page redirects, within the worker lease. Cancellation closes the active blocking socket so a timed-out worker does not leave a body read running. No cookies, browser credentials or source authentication are accepted.

Redirects are limited to three hops and the same bare/`www` site. Every hop is normalized and revalidated, HTTPS cannot downgrade to HTTP, and robots is rechecked for a changed origin. Redirects to sibling/unrelated domains or unsafe addresses fail without following them.

## Explicit unsupported outcomes

“Any website” means any ordinary public page that returns readable HTML/text under these controls. Ayo reports a precise unavailable state for:

- robots denial;
- login, account, bot-verification or access walls;
- private/admin/API/cart/checkout/password paths;
- PDFs, images, downloads and other non-page content;
- pages that return only a JavaScript application shell;
- unsupported encodings, oversized responses, weak/empty evidence, unsafe redirects, DNS/network failures, rate limits and timeouts.

Ayo does not bypass a restriction, execute page scripts, submit forms, retain cookies, traverse a whole site or infer that a missing field is a business defect. A failed source never becomes a fabricated report. A normal navigation mention of login does not by itself block a readable public page.

## Discovery and model behavior

Direct URL input is available by default through `AYO_RESEARCH_SOURCE=direct_public_web`. When `AYO_RESEARCH_SOURCE=wikidata_cc0`, reviewed Wikidata entity URLs continue through the CC0 adapter and other website URLs use the direct adapter. An explicitly selected `firecrawl` source preserves the separately reviewed Firecrawl path.

Name-only discovery is separate from URL fetching. It uses the configured Wikidata or Firecrawl discovery source; with direct-only configuration the UI asks for the public URL. This keeps arbitrary search-provider spending out of a website request.

After source evidence commits, the existing Gemini step behaves as before. If the reviewed Gemini policy/budget is unavailable, the worker publishes a partial source report with an explicit analysis error; it does not call a model or generate a fake answer. A new live Gemini call was not needed for this implementation because the existing Gemini/business-report milestone is retained.

## Verification

Offline fixtures cover public DNS admission, body bounds, response substitution, static/WordPress/commerce HTML, public product/price/channel extraction, bare-host to `www` redirect, robots allow/deny/missing, foreign/downgrade redirects, PDF, JavaScript shell, access wall, weak evidence, prompt injection, contact redaction and the real leased-worker evidence-before-inference checkpoint.

Final reliability regressions additionally cover one deadline across slow robots+redirects, cancellation of blocking network I/O, pinning with original TLS/Host identity at the production transport boundary, and HTML larger than the older300KB parser ceiling but within1MB. **Final GitHub CI passed1004 tests** with SQLite/PostgreSQL17, plus dependency audit and secrets; local baseline1000 and follow-up103 affected cases passed. [Exact delivery/verification receipt](evidence/website-worker-verification.json). No duplicate provider/source verification call was made for this review.

One zero-cost live test used the IANA-reserved `https://example.com/` documentation domain. The adapter checked robots and captured the page; a second bounded run through `python -m ayo.worker --once` persisted one source and completed the job on its first attempt. Gemini and Firecrawl made zero calls, and the report correctly remained partial with `model_not_configured`. [Machine-readable receipt](evidence/direct-website-live-worker.json).

This live check proves the generic public-page transport and worker path, not merchant identity, product coverage, business usefulness or compatibility with every site's presentation. No public deployment was performed.
