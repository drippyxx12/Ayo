# Ayo project memory and stopping point

Updated: 28 October 2026 15:30 Europe/Warsaw. Overall platform: **PARTIALLY COMPLETE**.

## Latest milestone — generic public website worker

The existing leased worker now accepts a user-pasted ordinary public HTTP/HTTPS website without a Firecrawl host allowlist or paid crawler call. Default `AYO_RESEARCH_SOURCE=direct_public_web`; the prior Wikidata CC0 path remains selected for reviewed entity URLs when configured, and explicit Firecrawl configuration preserves its separate gates. The web request queues encrypted work; only the worker retrieves source bytes.

Supported: static/server-rendered HTML and text, including ordinary WordPress, Shopify and WooCommerce pages. The worker checks robots, validates every DNS address, pins public egress with original TLS/Host identity, follows at most3 same bare/`www` redirects with robots rechecks, caps one page at1MB, extracts public Product JSON-LD and linked channels, redacts contact text, and commits URL/time/content+HTML hashes before existing Gemini analysis. It never executes scripts, retains cookies or bypasses a wall. Robots denial, login/bot challenges, files, JavaScript-only shells, weak evidence, unsafe redirects, unsupported encodings, rate limits and timeouts are explicit failed states.

Live zero-cost proof: `python -m ayo.worker --once` retrieved the IANA-reserved `https://example.com/` test page through `direct_public_web`, persisted source evidence and completed job `oxLUgXsgG2i8JsXnSTqyxHz11_R2YTl3` on attempt1. Firecrawl0/Gemini0/paid spending0. Analysis correctly remained unavailable/model_not_configured; this is a transport/worker proof, not business intelligence. [Receipt](docs/evidence/direct-website-live-worker.json), [implementation and exact support limits](docs/GENERIC_WEBSITE_RESEARCH.md). A prior direct adapter check accounts for one additional robots+page pair; no retries/redirects.

Verification: the generic-site application passed **1000 tests**,0 failed/skipped, SQLite+actual local PostgreSQL17,131.84s, one upstream warning, plus successful GitHub CI40698330472 including dependency audit and secrets. Final reliability review then added a45-second whole-source deadline across robots/redirects, cancellation that closes the active blocking socket, and support for HTML between the old300KB parser ceiling and existing1MB transport limit. **103 affected regressions pass** after those fixes, including production-boundary pin/Host/TLS checks, cancellation and slow redirects. No extra live/model/source test was needed. The previous real Trashy Bags Gemini report remains verified. Hosted preview is unchanged.

## Latest milestone — real research worker and Gemini report

**REAL REPORT CREATED / GEMINI BUSINESS ANALYSIS VERIFIED LIVE**, limited to a community company record for **Trashy Bags, Ghana**. Do not use Konga or Jumia; the founder explicitly excluded them. No Firecrawl source operation is needed for this path. The earlier HTTP200 Gemini connectivity milestone remains verified and must not be repeated.

Actual existing-worker run: `python -m ayo.worker --once`, job `JzaOj27_N3uv7Eo-bLOfgku68P8Tl7jd`, status succeeded, attempt1; saved report `fynJLwhqiKG_DvOwBLe4jRz1CKFtP-S8`, analysis completed. Gemini `gemini-3.5-flash-lite` returned HTTP200, **518 input +447 output =965 tokens**. One previously retained Wikidata CC0 record was reused; no repeat source retrieval. Actual local PostgreSQL report survived logout/login and immutable reopen. [Receipt](docs/evidence/small-company-live-worker-corrected.json), [original export](docs/evidence/small-company-live-report.json), [reviewed readable report](docs/evidence/trashy-bags-report.md).

Source: `https://www.wikidata.org/wiki/Special:EntityData/Q7835749.json`; retained label/description/country only. Products, categories, pricing, channels, sales and ownership are unknown. This is not a complete business audit. The immutable first export retains generic storefront hypotheses from the old builder; these are unsupported as storefront findings and are annotated in the readable report. Future company-record reports use the corrected dedicated builder. Source IDs/observations are validated; semantic truth is not certified.

**Cost:** zero-dollar reviewed Free-tier run, based on founder-reported Free project and official Standard free pricing. Invoice/project billing telemetry was not independently inspected. Current-day receipt retains4 Wikidata reads and3 Gemini attempts (2 provider successes/2080 known tokens;1 uncertain usage), including earlier unsuccessful/excluded-target work. Explicit audited zero-dollar reviews changed source call cap2→4 and Gemini cap2→3, without clearing consumed counts or raising money limits. All calls consumed; Free switches disarmed. General provider spending/mail remain0. No purchases/billing upgrade/outreach/merchant write/public deployment/merge.

## Merchant information workflow and honest live limits

New `/business-analysis` accepts authorized description/products/pricing/market/website/goals and bounded UTF-8 .txt/.md uploads. Every input retains hash/time/field/origin and OWNER_PROVIDED_UNVERIFIED. Inputs commit before model dispatch; replay is fenced; report and scoped follow-up use current tenant/account permissions. No URL/file execution, invented contacts/metrics or owner statements promoted to observations. Filters apply to inputs, follow-ups and final model context. Saved private reports use the existing research workspace.

Form/upload→Gemini-shaped structured report→PostgreSQL save→logout/login/reopen→report-scoped follow-up passes HTTP integration tests with explicit offline model responses. The actual synthetic owner attempt returned200/2451 tokens but was rejected for OBSERVED owner claims, and persisted unavailable. Strict output schema was fixed afterward. **Successful live owner-input synthesis/follow-up remains unverified**; do not confuse fixture success with the accepted public-record report. [Actual owner attempt](docs/evidence/merchant-input-live-workflow.json), [implementation/operator details](docs/MERCHANT_INPUT_AND_CC0_RESEARCH.md).

Migration `0008_merchant_analysis` preserves existing populated records, adds nullable conversation/report linkage and reviewed zero-dollar ledger constraints. Downgrade refuses while zero-cost evidence exists. Do not reset ledgers/delete data to force rollback. Persistent local PostgreSQL17 uses Docker volume `ayo-merchant-postgres-data`, loopback55432; existing reports/ledger survived a container restart. Disposable tests use isolated schemas, never erase public records.

## Verification and design

The complete pre-review suite passed977 tests. Review then fixed sensitive follow-ups, nonbusiness direct-source records and inaccurate company-record heuristics;138 focused SQLite/PostgreSQL tests passed. Final full suite: **981 passed,0 failed/skipped**, SQLite+actual local PostgreSQL17,146.88s, one upstream warning. Chromium:135 HTTP+135 screen checks at390/768/1440, disposable PostgreSQL/offline fixtures/providers0. [Aggregate receipt](docs/evidence/merchant-cc0-delivery-verification.json). CI delivery receipt follows below. No additional live requests are necessary for these fixes.

Founder-requested interface cleanup preserves black/beige/warm-white/Syne/DM branding: primary research navigation, clearer report headings, grouped owner-input form, compact dashboard next steps and disclosure for secondary filters/comparison/activity. Browser tests use labeled offline records, separate from actual live provider receipts. Current hosted preview has not been updated.

## GitHub and permanent requirements

Repository https://github.com/drippyxx12/Ayo ; existing branch `codex/africa-platform`; draft PR https://github.com/drippyxx12/Ayo/pull/1 must remain open/unmerged. Starting local/remote head `e189c532c2058c416b82d0a21f9c6227f1a5dc84` was verified; preserve all ancestry. Delivery uses correct drippyxx12 connector, tested-tree equality and non-forced expected-head ref update; final receipt follows below. Repository is public: do not commit account/private runtime/raw webpage data.

Both existing provider credentials remain in owner-only `/workspace/.ayo-private/runtime.env`, outside Git (0700 directory/0600 file). Account/encryption state also stays outside Git. Managed bindings/rotation/recreation are not verified. Never print values/fingerprints or request the keys again. Real connectivity evidence is already retained; no smoke-test repetition.

Read this memory each session and update verified milestones. Preserve architecture/migrations, search-before-signup, optional Shopify and immutable all-feature-free entitlement for the first500 distinct legitimate users. Full C01–C18/M0–M10 scope remains in PRODUCT_VISION/ROADMAP; internal Work is not an external action engine. Historical delivery/test/provider records remain in PROGRESS.md.

## Direct browser preview

https://ayo-development-preview-5icko1nq4-ayodejiiolatunbosun-7460.vercel.app/

Existing protected preview is **interactive intake only**, with private accounts/providers disabled. `/static/tour.html` is historical screenshot evidence. New local worker/private features and layout have not been deployed there. Do not claim the hosted site changed.

## Stopped at / Next / Blocked by

**Stopped at:** generic direct public-site retrieval and a live leased-worker transport check verified;1000-test baseline/CI and103 reliability regressions pass. Reliability fix delivery follows. The real small-company Gemini report remains verified.

**Next:** finish reliability fix GitHub delivery, then reviewed multi-page refresh/ownership and richer licensed or owner-supplied product evidence.

**Blocked by:** no blocker to single-page public URL retrieval. Sites may themselves deny robots/access or require JavaScript rendering. Live Gemini calls remain at the consumed dated cap; hosted API/worker/database, delivered mail and multi-page rendering are separate unfinished work. Paid calls, public deployment, outreach and merge stay unapproved.

## Verified GitHub delivery

Generic website application commit **`28ba794af9edcf6421851711345e3ed54562e716`**, tree `89253b96ecbce4891334dfe51d906ed01352d4d5`, exactly matched the tested/staged local tree. Correct drippyxx12 connector advanced the existing branch from `833bbba` with expected-head protection/no force; fetch confirmed a clean matching local/remote branch. Draft PR #1 remains open/unmerged. CI [40698330472](https://github.com/drippyxx12/Ayo/actions/runs/40698330472) **completed successfully**, including Python/contracts/dependency audit and secret-scan jobs. Subsequent reliability fixes are tracked above and in the next delivery receipt.

Application commit **`e325dba6c40a933e470fc0c37d470d6949f3379b`**, tree `b380ec5198c7c9b092230d2999590a885e9cd5d8`, matches the tested/staged local tree exactly. Correct drippyxx12 connector advanced the existing branch from e189c53 with expected-head protection/no force; fetch confirmed matching local/remote and clean working tree. Draft PR #1 remains open/unmerged and its description now distinguishes the actual limited public-record result from owner fixtures. App CI [40657563530](https://github.com/drippyxx12/Ayo/actions/runs/40657563530) completed successfully: Python/contracts/dependency audit and secret-scan jobs both passed;981 local tests passed. This following documentation-only commit records delivery without model/source calls or application changes.
