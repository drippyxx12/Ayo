# Merchant analysis and the first live research worker

Updated 28 October 2026. This extends the existing application; no new platform, paid service or public deployment was created. The first-500-users all-feature entitlement is preserved.

## What worked with real providers

The existing leased worker completed a Gemini-assisted **limited company-record report for Trashy Bags, Ghana**. It used a permitted Wikidata CC0 record, not the company's storefront. The report was claimed into the existing local PostgreSQL research workspace and reopened unchanged after HTTP logout/login. [Actual worker/usage receipt](evidence/small-company-live-worker-corrected.json), [immutable report export](evidence/small-company-live-report.json), [reviewed readable report](evidence/trashy-bags-report.md).

Successful synthesis: `gemini-3.5-flash-lite`, HTTP200, 518 input +447 output =965 tokens. No Firecrawl operation, credit purchase, billing upgrade, outreach, merchant write or deployment occurred. The earlier successful Gemini connectivity test was preserved and not repeated.

This establishes the real worker → retained source → Gemini → saved report path. It does not establish a complete business audit, complete product/pricing analysis, official company verification, hosted merchant service or full NG/GH milestone acceptance.

## Merchant-supplied information

Verified owners/admins/editors can use `/business-analysis` to submit a description, products, pricing, market, website information and goals. A website supplied here is text; it is never fetched by this route. Optional uploads accept only UTF-8 `.txt`/`.md`, at most4,000 bytes. PDF/Office execution and attachment forwarding are absent. Original filenames are discarded. Fields are bounded, combined inputs are at most12,000 UTF-8 bytes, and the description needs at least10 characters.

Every input retains a separate ID, internal reference, origin (`merchant_form`/`merchant_upload`), field, capture time and SHA256. The report and exports label every supplied statement `OWNER_PROVIDED_UNVERIFIED`. Authorization, nonpersonal information and provider processing must be attested on each submission. Conservative contact/credential/control-character filtering applies to fields, uploads, report-bound follow-up questions and the final merchant model context; it cannot certify arbitrary text is free of personal information.

Inputs commit before inference in the existing research tables. Pending/failed model output remains an honest saved state, with no fabricated substitute. Replayed forms do not dispatch a second model call; changed contents under the same request ID conflict. Reports retain original input evidence, sourced AI hypotheses/recommendations, unknowns and limitations. The private library can reopen/export them.

“Ask Ayo about this report” creates a conversation bound to that report. Current report inputs are re-read under current tenant/account permissions. Prior prompts/generated answers are not evidence. The model cannot select other tenants, tools or external actions. Report-bound questions reuse the same nonpersonal policy and reject restricted text before saving or provider dispatch.

**Verification distinction:** form/upload → structured report → PostgreSQL save → logout/login → reopen → contextual follow-up passes SQLite/PostgreSQL HTTP tests with explicit offline Gemini responses. The first real synthetic merchant submission returned HTTP200/2451 tokens but incorrectly labeled owner statements OBSERVED; Ayo rejected it as `unverified_owner_claim`. [Actual failed attempt](evidence/merchant-input-live-workflow.json). Strict Gemini output schemas and filtering were corrected afterward. A successful real owner-input report/follow-up has not been independently verified; the real accepted result is the public Trashy Bags record report. Do not relabel fixture success as live owner success.

## Reviewed public source

Select `AYO_RESEARCH_SOURCE=wikidata_cc0` to use the fixed-host adapter. Its only operations are bounded `wbsearchentities` company search and an exact `Special:EntityData/Qid.json` fetch on `www.wikidata.org`. It does not follow arbitrary links, retrieve storefronts, select people or expose contact fields. Search candidates are not proof of domicile; fetched records reject explicit humans and descriptions outside the supported business/organization scope.

Official [structured-data licensing](https://www.wikidata.org/wiki/Wikidata:Licensing) was reviewed: structured data is CC0; other namespace text has different licensing and is not used as report evidence. [Wikimedia API guidelines](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines) were reviewed for identified clients, bounded use and no access-control bypass. [Dated policy-read receipt](evidence/wikidata-policy-review.json). No white-label API resale or commercial Firecrawl authorization is inferred.

Acquisition resolves the fixed host, rejects nonpublic addresses, CONNECTs through the inherited HTTP proxy to a pinned public IP, keeps certificate/SNI/Host validation for the original domain and rejects redirects. Responses are capped at1MB, with socket/outer deadlines. Only the label, description and explicitly present NG/GH country statements enter the retained record. Hash, source URL, capture time and provider revision receipt persist. Wikidata statements remain community assertions, not independent verification of the company.

Company-record reports now avoid storefront absence heuristics. Missing delivery/returns/catalog fields are unknowns, not evidence that a business has poor policies. The first accepted saved report predates this presentation correction; its immutable JSON is retained and its inherited wording is explicitly reviewed in the readable report.

## Zero-dollar dispatch controls

General `AYO_PROVIDER_SPEND_AUTHORIZED` and mail remain0. Gemini Free-only dispatch additionally needs `AYO_GEMINI_FREE_CALLS_AUTHORIZED=1`, `AYO_GEMINI_BILLING_MODE=free_only_reviewed`, `AYO_GEMINI_PROJECT_TIER_REVIEW=free_confirmed`, the exact reviewed `gemini-3.5-flash-lite` configuration, all monetary limits/reservations0, positive finite request/scope/provider call caps and a dated policy expiring no later than the next UTC midnight. Input/output/thinking configuration remains fingerprint-bound. `AYO_AI_DATA_POLICY=owner_nonpersonal_reviewed` permits only merchant-input analysis; `public_only_reviewed` permits only public research. Neither authorizes general private workspace inference.

Wikidata requires its separate `AYO_WIKIDATA_READ_AUTHORIZED=1`, `AYO_WIKIDATA_API_REVIEW=cc0_reviewed`, `AYO_WIKIDATA_BILLING_MODE=free_only_reviewed`, zero-dollar reservations and finite dated search/fetch call budgets. Free switches cannot dispatch Firecrawl or a paid policy. The current live window consumed its reviewed calls; both Free-only switches were disarmed afterward. Existing keys remain outside Git; do not ask for or print them again.

Cost basis: founder-reported Ayo Free-tier project and reviewed official Standard model free input/output pricing. Project billing/invoice telemetry was not independently accessible. Durable reservations are authorization accounting, not provider invoices. Timeouts, rejected output and uncertain results keep their consumed counts; no automatic refund/retry/reset occurs.

The founder's change to a smaller target was recorded through one explicit zero-dollar CC0 allowance review (2→4 reads) and one explicit Free Gemini replacement review (2→3 generations), retaining existing counts and audit events. These are operator-only methods, absent from HTTP/model tools. No monetary budget was raised. The current-day receipt includes four Wikidata operations and three Gemini attempts, one outcome/usage uncertain, two successful provider responses totaling2080 known tokens. The prior-day owner attempt used2451 tokens; the historical connection diagnostic used19. Do not report unknown usage as zero.

## Schema, safety and next work

Migration `0008_merchant_analysis` permits explicitly reviewed zero-dollar budget rows and adds a nullable report reference on conversations. It preserves populated conversation children on SQLite and uses explicit foreign keys on PostgreSQL. Downgrade refuses while zero-cost ledger evidence exists; do not delete evidence to force a rollback. Existing reports, migrations and first500 entitlements remain intact.

Tenant/role/CSRF/replay, no-person records, restricted follow-ups, input handling, output citations/classification, source matching, budget caps and populated migration preservation are covered by tests. PostgreSQL is a persistent local Docker volume, not a hosted database. Browser layout verification uses labeled offline records, separately from the real provider receipt.

Next: reviewed source refresh/ownership and richer licensed or owner-supplied product evidence. Firecrawl commercial use, storefront restrictions and Konga/Jumia are excluded from this path. No founder action is needed to keep developing this adapter or interface. A future larger live batch needs a new finite dated zero-cost allowance and current Free-tier/data confirmation; paid calls, public hosting, outreach or merge retain the founder's explicit approval boundary.
