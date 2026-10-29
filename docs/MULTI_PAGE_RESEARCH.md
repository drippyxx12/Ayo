# Bounded public website sampling

29 October 2026. The existing direct website worker can now retain an initial page plus up to two relevant pages linked from it. This improves evidence depth without a new provider, schema migration or paid call.

## Selection and limits

- Select only actual links in the first page's bounded HTML observation. Relative links are resolved; malformed links are ignored.
- Prefer one product/category/catalog link and one delivery/returns/about link. If a category has no match, another qualifying link may fill its slot. URLs are never guessed.
- Remain on the same bare/`www` site. Shared social/marketplace/CC0 hosts do not expand into other profiles. External links, private paths, files, fragments and identity-bearing query URLs are excluded before dispatch; tracking-only queries may be removed.
- Attempt at most three selected pages, including the initial page. Failed linked pages do not trigger replacement crawling or retries. Existing per-page redirect/size controls apply.
- One45-second deadline covers all robots reads, pacing, page requests and redirects. Each accepted page remains limited to1MB. No scripts, forms, cookies or authentication are used.

Every request still uses the existing public-IP-pinned transport and TLS/Host validation. Cached robots rules are applied to each exact path and to redirected targets. Matching uses the most specific applicable agent groups and path rule, equal-length Allow precedence, wildcard/end markers, and encoded-octet normalization. Published crawl-delay/request-rate pacing is respected within the shared deadline. An untrusted robots file cannot trigger regex backtracking.

The first page must succeed. If a linked page is denied, rate limited, unavailable or times out, useful initial evidence can still produce an explicitly partial report. Skipped-page content remains unknown. A rate limit or service failure stops further sampling. No restriction is bypassed.

## Evidence and synthesis

Each retained page keeps its own final URL, timestamp, content hash, HTML hash and source ID. New direct-source IDs bind both URL and content, so identical text on different pages retains distinct provenance. Existing saved reports remain immutable.

The deterministic report evaluates gaps across all retained pages. A product found on page2 is not mislabeled unknown because the homepage lacks catalog markup. Product observations cite their own page; differing public prices remain distinct observations. Summary bounds remain40 claims/10 opportunities, with at most20 distinct product/price observations and10 channel labels; the bounded source documents remain inspectable. No sales, stock, ownership, competitors or performance is inferred as fact.

All sources commit in the existing hidden PostgreSQL research checkpoint before one existing Gemini synthesis step. The same citation validator runs on publication. Missing/rejected/unapproved Gemini output remains partial. Public claim links now use the source's actual report number. Private save/export/reopen and tenant isolation reuse the existing workspace services.

Optional Firecrawl and Wikidata adapters retain their existing single-operation behavior; sampling does not expand their credit or call allowances. A configured Wikidata discovery source still routes ordinary website URLs to the direct adapter.

## Verification and remaining work

Tests use clearly labeled synthetic HTML, model responses and local account/outbox fixtures. They cover link admission, correct source citations, identical-content identity, denied/failed/rate-limited links, shared timeout, robots precedence/wildcards/pacing, configured-provider routing, and the complete worker→committed sources→fixture Gemini→claim→logout/login→immutable reopen/export flow on SQLite and actual isolated PostgreSQL schemas.

No live business crawl, Gemini call, Firecrawl operation, email, outreach, public deployment or merge was performed for this milestone. Earlier real Gemini/Trashy Bags and `example.com` transport receipts remain unchanged. Multi-page behavior is locally verified with fixtures; no new live multi-page acceptance is claimed.

This remains a small page sample. JavaScript rendering, full audits, recurring refresh, independently verified ownership, broader source-quality evaluation and hosted service acceptance remain unfinished.
