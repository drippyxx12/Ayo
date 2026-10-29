# 26 — Ayo AI engine architecture: Gemini-primary, Claude-compatible, retrieval-owned-by-Ayo

**Engineering decision recommendation (25 Oct 2026):** Gemini as **primary** for public-web discovery/summarization at launch; Claude as **optional, feature-flagged secondary** for multi-step planning/quality evaluation. This is an initial routing default, not founder-mandated exclusive vendor lock-in. Validate model quality, price, latency and country/language fidelity with real evals. Model IDs MUST be pinned to versions actually available in the project at deploy time; never invent upcoming model names.

## Why
- Gemini offers provider-managed **Google Search grounding** with citations and a **URL Context** tool for page material; these fit the discovery-first acquisition loop. URL Context only reads specifically passed URLs and does **not crawl all nested links**. Google Search grounding is not, on its own, a complete searchable business database, B2B lead service or permission to crawl. [Official Search docs](https://ai.google.dev/gemini-api/docs/google-search), [URL Context](https://ai.google.dev/gemini-api/docs/url-context).
- Claude offers **cited web search** and strong tool-based planning; its search is also a commercial API and therefore not inherently free. [Official Claude web search docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool).
- Price/performance should be evaluated on comparable benchmark tasks; no unsupported assertion that one model is universally smarter. For 500 free founders, cost ceilings and backend controls matter. Claude subscription / Gemini app subscription do **not** equal Ayo API credits; configure distinct developer credentials and billing safely.
- Use an independent *business discovery/search provider* if structured repeatable results, licensing, quality and geographic coverage require it. Do **not** use Google's old Custom Search JSON API for a new project: [official docs say it is closed to new customers](https://developers.google.com/custom-search/v1/overview).

## Independent interfaces and trust boundaries
- `SearchProvider.search_entities(query, country, city, limit, budget) -> Candidate[]` with source/title/url/search_timestamp/confidence; real provider or `UNCONFIGURED`.
- `ContentFetcher.fetch_citable_pages(public_url, crawl_policy) -> EvidenceDocument[]` with per-page resolved DNS and egress allowlist, `robots.txt`, redirects, content limits, citation snapshots and source hash. Gemini URL Context may augment, but cannot substitute for Ayo's deterministic safe-crawl policy.
- `ModelProvider.complete_structured(task, sanitized_context, model_policy, budget) -> ValidatedJSON` with provider ID, model version, tool-use receipts, token/cost and trace ID. Provider must not see application secrets or unrelated tenant data.
- `EvidenceService.store(claim, citations, observed_time, extract_version, confidence, source_class)`. Every factual business or lead claim must anchor to actual citable evidence. Citations are immutable and link to source pages; TTL/refetch and removal policies prevent stale recommendations.
- `LeadSourceAdapter.find_organizations(merchant_offer, target_market, policy) -> sourced_organizations` must obey provider license and platform TOS. Never hallucinate emails or persons, never assume social profile access. Merchant contact and outreach are separate permissioned integrations.
- `MerchantWorkspaceService.claim_preview(ephemeral_claim_id, authenticated_user, verified_email) -> business_workspace` MUST validate one-time claim; ownership of site is separate and not implied.
- `ActionPolicyService.authorize(action_hash, tenant_permissions, consent, scopes, budget) -> decision`; model never executes direct writes. Outbound communications blocked without applicable lawful basis/suppression/opt-out/provider credentials and explicit authorization.

## AI task routing (config-driven)
- **Identity disambiguation:** search provider + deterministic entity matching first; Gemini can extract attributes but may not choose ownership on its own.
- **Public page interpretation:** Gemini Flash-class cost-optimized pinned model with structured schema output; validate literal evidence. If token/model/search limit reached, partial report instead of fabricated completion.
- **Mini-report:** Gemini synthesis of source-labeled observations, structured schema and citations; source checker drops unsupported claims. Cheap rules for obvious missing elements; recommendations labeled inferred.
- **Lead research:** SearchProvider finds sourced company candidates; Gemini classifies **fit** with reasons and disqualifiers. Leads remain `DISCOVERED` until validated, `REVIEW_REQUIRED` before message drafting.
- **Business strategy and complex cross-tool planning:** run bounded comparison between Gemini reasoning model and Claude Sonnet-class model on founder-owned evaluation set; select only if quality materially improves. No silent transmission of customer data to another provider without informing user and meeting privacy requirements.
- **Execution:** never delegated to raw Gemini/Claude tool calling. Ayo translates action suggestions to strict typed commands; policy engine verifies access, scope, pricing, merchant approval, consent, timeouts and idempotency. Provider adapter executes, reconciles receipt.

## Evaluation rubric (before declaring provider choice production ready)
Compare at least 20 diverse Nigeria + Ghana ecommerce cases with named public brands and consented test shops, including business with no site, reseller/wholesale, beauty/fashion, service confusion, low bandwidth, GHS and NGN price formatting, region/name collisions, inaccessible social site and misleading promotions. Measure: company match precision, citation fidelity, hallucinated entities, correctly admitted sources, B2B lead relevance, availability, inference labeling, response time, tokens/search cost per successful report, safe prompt-injection resistance, language readability. Test both models against **the same actual evidence** (blind review). Prefer lower-cost model if equivalent quality.

## Batching/cache/security/cost
Meter before-anonymous-signup requests by IP/session/verified captcha when risk warrants, with transparent safety rate limits. Cache public-domain immutable snapshots by source/time where lawful and allowed, but never share tenant notes, claimed reports, provider credentials or user-supplied private details across tenants. Enforce limits on pages, link depth, bytes, redirects, concurrent jobs, search/tool uses, retry budgets and spend per job; publish job statuses honestly. Founding 500 users still get **all released features free**; reasonable protective fair-use limits may be globally applied, not disguised premium gates. No arbitrary OpenAI/Anthropic/Google model switch without version/audit logs.

## Official docs consulted 25 Oct 2026
- https://ai.google.dev/gemini-api/docs/google-search
- https://ai.google.dev/gemini-api/docs/url-context
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
- https://developers.google.com/custom-search/v1/overview

**None of the model credentials, production search connections, spend budgets or provider calls are implemented by this document.**
