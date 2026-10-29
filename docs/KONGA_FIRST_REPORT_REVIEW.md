# Konga: first real report readiness — 27 October 2026

**FIRECRAWL: CONNECTED. GEMINI BUSINESS ANALYSIS: NOT VERIFIED. REAL REPORT: NOT CREATED.**

The existing Gemini synthetic connectivity receipt remains valid and was not repeated. No business inference, Firecrawl crawl/search, purchased credit, billing change, outreach or deployment occurred in this session. [Machine-readable readiness](evidence/konga-first-report-readiness.json).

## Actual account verification

After disclosing the operation, performed exactly one authenticated `GET https://api.firecrawl.dev/v2/team/credit-usage`, no retry or redirect. **HTTP200 / success:true / remainingCredits:1000 / planCredits:1000**. Period: 26 October–26 November. [Actual redacted receipt](evidence/firecrawl-account-readiness.json). The credential works and quota exists. The endpoint does not return a plan name, free-vs-paid credit classification, billing account, or automatic-purchase setting. A 1000-credit allowance is consistent with the advertised Free plan but does not independently establish those settings. No billable page operation was dispatched; no invoice was inspected.

Public [pricing](https://www.firecrawl.dev/pricing) advertises 1000 free monthly credits without a card, basic crawl 1 credit/page, search 2 credits/10 results. Advanced formats/add-ons may cost more. Paid plans can add credits automatically in $5 increments unless disabled/capped. Marketing prices are not proof of this account's configuration.

## Candidate identity and source rights

The homepage `https://www.konga.com/` returned HTTP200 and self-identifies as “Konga Nigeria | Online Shopping for Genuine Electronics, Phones, Fashion & More.” Its own footer links [terms](https://www.konga.com/content/terms-and-conditions), [privacy](https://www.konga.com/content/privacy-policy) and the Konga group about page. This establishes the proposed Nigerian storefront identity at the candidate domain, not legal ownership, corporate-registry proof or Ayo merchant control.

`https://www.konga.com/robots.txt` returned HTTP200. The declared operator-review agent is allowed at `/`; wildcard exclusions include `/product/*/details`, `/account/`, `/cart/`, `/checkout/`, `/search`, `/category/-`, `/product/-`. Do not follow these excluded paths. Provider robots behavior must remain enabled; no agent impersonation or bypass is approved.

The exact terms URL returned HTTP200 but only a loading shell, page title and metadata, not the substantive legal text. No source-use permission was inferred. A browser/rights-holder review remains necessary; founder consent cannot override third-party terms. The connected-browser tool is not exposed in this session, and we did not substitute a paid scrape to obtain the terms.

Operator source-policy review used bounded, declared-agent, public-IP-pinned HTTPS GETs for robots, homepage and the linked terms page, with TLS verification and no redirects. These are **policy/identity checks**, not Firecrawl-acquired retained source evidence or a completed report. Hashes/timestamps/statuses are in the readiness receipt; raw public pages remain outside Git, including any contact text. No manual-page content was sent to Gemini or presented as pipeline output.

## Data processing and provider policy

- Firecrawl [terms §5.d.1](https://www.firecrawl.dev/terms-of-service) prohibit commercial purposes “except as expressly authorized by Firecrawl”; the applicable Ayo plan/contract permission has not been evidenced. §5.d.4 also requires lawful/contract-compliant use. Confirm the permission applicable to this project before the business test.
- Firecrawl [privacy](https://www.firecrawl.dev/privacy-policy) describes US storage/transfers, collection on clients' behalf, caching/indexing and PII retention until written deletion request. Do not assert a zero-retention or no-training guarantee from this text.
- The [crawl API](https://docs.firecrawl.dev/api-reference/endpoint/crawl-post) documents `ignoreRobotsTxt:false`. `zeroDataRetention` defaults false and needs provider enablement. `storeInCache:false` is a cache preference, not independently verified deletion/no-log proof. No zero-retention entitlement was established. A guessed ZDR documentation URL returned404; the actual crawl option documentation was used instead.
- Gemini Free-tier terms allow improvement/training and human review and prohibit personal/sensitive/confidential submissions. Required approval is limited to inspected nonpersonal organization/product excerpts. Provider PII redaction is not a guarantee; inspect the actual staged snapshot before inference. No account identity, contact details, customer/orders, private owner facts, raw HTML, credentials or session links enter the model request.

## Exact proposed operations — not dispatched

| Operation | Target/settings | Expected usage | Current permission |
| --- | --- | --- | --- |
| Account quota GET | `/v2/team/credit-usage` | No scrape/search credits; one actual read completed | Completed under Phase1 request |
| Search | None: founder supplied the exact candidate domain | 0 credits | No search planned |
| One crawl creation | `POST https://api.firecrawl.dev/v2/crawl`, URL `https://www.konga.com/`, limit1, depth0, sitemap skip, external/subdomain traversal off, robots enforced, concurrency1 | **1 base credit** for one page; no paid extraction/proxy escalation | BLOCKED pending rights/account/data/egress review |
| Status/cancellation | `GET /v2/crawl/{actual_receipt}` at most15, `DELETE` once only if still active/uncertain | No additional page requested; neither cancellation nor failure proves a refund | Only as part of an approved crawl |
| Gemini report synthesis | One Standard `gemini-3.5-flash-lite` request over the committed, inspected public checkpoint; maximum32768 UTF8 input bytes,1500 output tokens, MINIMAL thinking, no tools/thought summaries | Free input/output on the founder-reported Free project; actual token use unknown until a response | BLOCKED pending the source/data/run policy |

Crawl settings retain markdown/HTML, `proxy:basic`, TLS verification, `storeInCache:false`, `redactPII:true`, no parsers, actions, screenshots, JSON/LLM extraction, prompt scanning or advanced proxy. The existing adapter has a35-second total deadline and bounded cancellation. There is **no retry allocation** and no second source page. A denied/challenged/insufficient/uncertain response stops the trial, with any accepted usage retained.

**Maximum authorized charge: USD0. Maximum possible monetary charge under the currently unverified account settings: UNKNOWN; do not dispatch.** Expected base credits are not a guaranteed invoice. Do not buy credits, upgrade billing, assume auto-purchase is off, or increase the cap.

## Existing budget controls and precise approvals

Ayo already commits request/provider/scope daily dollar/call reservations before dispatch, binds model/input/output/thinking configuration, enforces reviewed expiry and retains uncertain debits. These are conservative **positive USD authorization debits**, not measured invoice costs or a free-credit/automatic-purchase lock. No ledger/counter was reset. Ordinary workers can retry definitive provider denials; the operator trial must not run that retry loop or allow a concurrent worker.

The existing [private-loader offline preflight](evidence/konga-provider-preparation.json) exits2, zero network requests. Both credentials/model and disabled provider/mail switches pass. Data policy, hosted egress, exact hosts and reviewed source/model budgets remain unconfigured. The old two-business USD3 proposal remains inactive. A URL-only trial needs no index search; a search-budget preflight requirement is not permission to add search.

Founder-side facts/approval still needed:

1. In this Firecrawl account's plan/billing dashboard, confirm **Free plan** and **pay-as-you-go/automatic credit purchases disabled**. The API key and1000 balance are already verified; do not resend credentials.
2. Supply the applicable readable Konga source-access clause or permission and the Firecrawl commercial-use authorization for Ayo. Robots allow is insufficient. If permission cannot be established, select an actually permitted source instead; do not bypass restrictions.
3. Accept only the public, nonpersonal excerpt processing above, including normal Firecrawl retention and Gemini Free-tier improvement/human review. Do not mark private-analysis policy approved.
4. Once those facts exist, freeze the exact host/egress review and bounded, expiring **one crawl + one Gemini / no retry / USD0** run policy. No new paid authorization is inferred. If the entire bound can be independently established as free, the user's current instruction conditionally permits execution after the required reviews; do not ask for that same authorization again.

## Report acceptance after approval

Use existing `ResearchService` → `ReportStore.stage_preview` → committed/re-read evidence → operator data review → `enrich_report`/existing Gemini adapter → `finalize_preview`, with durable usage accounting. Do not substitute a generated example or manual inspection for that pipeline. Persist source URL, capture timestamp/hash, citations, provider/model usage, limitations and redacted receipt. Preserve a private database/checkpoint outside Git; do not publish raw contact text.

Independently compare every OBSERVED claim/quote with the retained source. Products/categories/channels/prices must trace to actual returned fields or quotations; mark missing items UNKNOWN. Suggestions remain hypotheses. No invented competitors, sales, inventory, revenue, conversion or performance metrics. A one-homepage result remains a **partial single-page assessment**, even if Gemini successfully synthesizes it. This trial does not complete the wider NG/GH M2 acceptance.

Current result: **no real report exists to validate**. The phase3 coverage fields remain unverified rather than populated from speculation.
