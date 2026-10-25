## Current full-product direction — 25 October 2026

**Persistent handoff preference:** Read [MEMORY.md](MEMORY.md) at the start of every work session. Before pausing, handing off or ending a session, update it with the exact milestone/stopping point, last completed work, actual verification, current branch/remote code commit/PR, direct browser preview URL and its actual interactive scope (screenshot evidence must be labeled separately), blockers and the next concrete action. Keep historical evidence in PROGRESS.md and synchronize FEATURE_STATUS.md when behavior changes. Finish each work-session summary with a brief **Stopped at / Next / Blocked by** checkpoint so the founder can always see the current process. Never store credentials, personal data or fabricated outcomes in memory. This is repository-persisted project memory; do not imply an account-wide memory tool was used.

Before further feature development, read [PRODUCT_VISION.md](PRODUCT_VISION.md), [ROADMAP.md](ROADMAP.md), [FEATURE_STATUS.md](FEATURE_STATUS.md) and [PROGRESS.md](PROGRESS.md). They consolidate the original architecture package into the full Nigeria/Ghana platform, beyond MVP. Preserve one unified Ayo, public research before signup, optional commerce integrations and all-feature access for the first 500 distinct legitimate users. Gemini must be used in the FIRST functional business-research milestone, with source-bound structured output and an authorized real API call; a separate model adapter or rules-only report is not acceptance. Earlier sequencing that postpones AI is superseded. Do not claim finished until the full documented required capabilities have meaningful integration/E2E and independent verification. Required and proposed work must remain visible; preserve the historical specifications below and the original ZIP. This update does not authorize spending, outreach, merchant writes or public production deployment.

## Highest-priority founder update — 25 October 2026: SEARCH-FIRST, not signup-first
**Binding UX sequence:** public visitor `SEARCH (name/site/social) → source-backed website/business research → useful mini-report + optional actual organization-level lead preview → CTA create free account → secure report claim and private workspace → Ayo sourced lead discovery & operations → OPTIONAL Shopify or other integrations`. E-commerce only; Africa-first for Nigeria, Ghana and later countries. Ayo must also work for businesses with NO website, via permitted public listings or owner-supplied labeled facts. **Never require Shopify or signup to see the initial public mini-report.** Public research never grants site ownership, OAuth permissions or marketing consent. Model recommendation: Gemini for cited web discovery and URL analysis; Claude optional behind an evaluated adapter for complex planning; actual execution through Ayo's typed approval/policy engine. DO NOT confuse AI model chat subscriptions with API credentials or provider spend. Detailed contracts: `docs/25–28`, `architecture/search_first_journey.json`, `architecture/ai_provider_routing.json`, `architecture/mini_report_schema.json`. These are target specs; providers NOT YET CONFIGURED.

**CANONICAL 25 OCT 2026 OVERRIDE: PUBLIC SEARCH → VERIFIED SITE RESEARCH → SOURCED MINI-REPORT → CREATE ACCOUNT → SAVE/CLAIM REPORT → OPTIONAL PROVIDERS (SHOPIFY) → SOURCED LEADS & GOVERNED ACTIONS. Shopify is NOT required to use Ayo, and public assessment precedes signup. Read `docs/25_SEARCH_FIRST_DISCOVERY_TO_SIGNUP_CANONICAL.md`. Every available feature remains FREE to the first 500 USER accounts. Gemini is a provisional primary engine; Claude is an optional adapter pending evaluations. None of this newly specified workflow is live in the current alpha.**

**Founding access rule (founder-confirmed 25 Oct 2026): ALL AVAILABLE FEATURES ARE FREE FOR THE FIRST 500 DISTINCT CUSTOMER USERS (ACCOUNTS), not 500 businesses. There are NO feature paywalls, operator tiers or paid add-ons for their Ayo capabilities, including features shipped later. Preserve founding-user entitlement across their authorized workspaces. Safety/anti-abuse safeguards and independently disclosed external provider fees are not permission to silently add an Ayo feature paywall. No automatic expiration or billing is authorized; lifetime contractual wording remains a founder/legal decision. See `docs/09_LAUNCH_AND_FREE_500_POLICY.md`.**

# Mandatory founder update 2026-10-25 — Africa-first + sourced website intelligence + real lead development
**Ayo is Ayo.** The product is specifically optimized for African e-commerce: Nigeria and Ghana first. See `START_CODEX_HERE.md`, `docs/18_AFRICA_FIRST_COMMERCE_STRATEGY.md` to `docs/23_IMPLEMENTATION_SLICES_AND_VERIFY_FIRST.md`, plus country/skill manifests under `architecture/`. Later country profiles and integrations are not live by declaration.

Before connecting Shopify a merchant must be able to **search or paste a public website** for source-backed research after the compliant search/crawl stack exists. Building the research stack must include SSRF-safe egress, robots/terms, source provenance, tenant scope, rate/cost budgets and prompt-injection-resistant low-trust data boundaries. Public research **never** implies domain ownership or a token to modify a site.

**Ayo Leads** is a separate researched business lead workflow for Ghana/Nigeria and future markets: company discovery → normalized cited candidate → fit evaluation → drafted outreach → optional lawful approved provider send → actual reply/opportunity/verified sales. Separate prospect discovery from authorized existing-customer retention data. Public phone/email is not permission to market; compliant lawful basis, opt-in and opt-out controls, provider authorization and receipts gate every send. No automatic mass marketing or fake send/sale outcomes.

For Codex, implement Slice S00 then security foundations, not an exhaustive agent fantasy; reviews must include end-to-end evidence and tests. Merchant money metrics use country/currency-specific definitions; don't assume bank-transfer or MoMo pending equals paid. LLM is strictly a planner/explainer behind deterministic tool permissions and audit.

---

# SUPERSEDING FOUNDER UPDATE — Website Intelligence / 25 October 2026

**Mandatory:** Ayo's founder now also requires a **business website search-and-research capability**. The merchant can search by business name or enter a site URL; Ayo discovers real public website evidence, examines product pages and customer experience, gives source-backed findings and uses this context through its unified intelligence. The site can be researched *without Shopify*; however website research must never be confused with merchant ownership, private account authorization or write permission. Polsia is only an inspiration for persistent research/orchestration; never call Ayo a clone or copy third-party code.

**Read in order:** `FOUNDER_BRIEF.md`, `docs/11_WEBSITE_INTELLIGENCE_PRODUCT_AND_UX.md`, `docs/12_ARCHITECTURE_BLUEPRINT_AND_TRUST_BOUNDARIES.md`, `docs/13_WEBSITE_CRAWLER_SECURITY_AND_RESEARCH_PIPELINE.md`, `docs/14_DATA_MODEL_AND_API_CONTRACTS.md`, `docs/15_CODEX_PHASE_PLAYBOOK.md`, `docs/16_SKILL_REGISTRY_AND_SECURITY_CONTROLS.md`, `docs/17_REPOSITORY_HANDBOOK_AND_DECISIONS.md`. The latest docs **supersede earlier read-only Shopify-only release sequencing**. Implement via reviewable PRs according to phase acceptance tests.

**Critical boundary:** Never fetch a user-supplied URL via generic HTTP client after only parsing or DNS-prechecking it. Prevent SSRF through pinned-public-IP controlled egress and per-hop validation, obey robots/terms, cap budgets, isolate crawling workers and resist prompt injection. The new `ayo/website_research.py` is **pure parsing/input classification only and does not make any network request**; tests are offline. Do not expose a 'Scan completed' state until verified network fetch and evidence persistence exist. `research` is not an `action`. All merchant writes need separate ownership, OAuth, approval, scope and audit.

**GitHub:** The intended private repository account is `drippyxx12`. No repo and no installation were accessible on 25 Oct 2026. Never upload to the previously connected wrong account. Do not claim a push without actual GitHub repo URL, `private` status and commit SHA.

---

# Current founder requirements (supersede narrower earlier release assumptions)

**Read `FOUNDER_BRIEF.md` FIRST.** Founder-confirmed: e-commerce only at launch, Shopify first (other commerce integrations/custom installation later), one unified Ayo orchestrator coordinating dynamically available verified skills, no comparison-based brand positioning, first 500 DISTINCT USER ACCOUNTS receive ALL available features free; no premium-tier feature gates. Ayo is its own product. Nigerian storefront builder is an uncommitted future possibility, not first-release scope.

**Distinguish two milestones:** A first **technical Shopify integration proof** may be read-only, but the **first substantial customer V1** targets multiple genuine read capabilities and at least one verified, merchant-approved external write with policy enforcement. Catalog copy optimization is recommended as first write, pending founder decision and proper permissions. Do not portray unbuilt skills as already active. Never create mock revenue in production accounts.

# Ayo — engineering instructions for Codex

## Product identity and non-negotiables

Ayo is an AI-driven growth operating system for African businesses, launching first with Shopify merchants. Build a real SaaS: real merchant accounts, a real Shopify OAuth installation, secure tenant-scoped data import, transparent business metrics, and eventually governed actions. Do **not** create a seeded fictional dashboard in the actual merchant workspace. No fabricated orders, revenue, customer accounts, integrations, AI analysis, or agent execution.

The repository contains a **FastAPI/SQLAlchemy/Jinja Shopify-connected alpha**. Inspect all existing implementation and tests before proposing changes. Keep working parts rather than doing a blind framework migration. If a React/Next.js front end would materially improve the product, document migration tradeoffs and implement incrementally on a separate branch with preserved backend contracts. Do not rename the product or fork into a different app.

## Important source modules

- `ayo/app.py`: routing, auth/session, Shopify authorization, token encryption/refresh, GraphQL ingestion, per-account snapshot storage, webhooks, and basic deterministic questions.
- `templates/` and `static/ayo.css`: existing merchant interface; no fake data.
- `tests/test_app.py`: integration tests with mock Shopify API responses.
- `.env.example` and `README.md`: configuration and deployment requirements.
- `WHAT_IS_REAL.md`: evidence of current functionality and known limitations.

## Standards

1. Start with a security-and-dataflow audit. Summarize actual behavior, potential bugs, Shopify API scopes/privacy obligations, and the highest-risk issues. Do not call something production-safe without evidence.
2. Maintain strict tenant isolation on every query, cache entry, job, and external Shopify connection. Encrypt provider tokens using server-side secrets; never log tokens or store them in client/browser storage.
3. Use Shopify's supported OAuth patterns, versioned GraphQL Admin API, current token expiry/refresh rules and verified HMAC state/callback/webhook checks. Validate technical requirements against current Shopify documentation, not assumptions. Require least-privilege scopes.
4. Do not hardcode credentials, data, billing results or customer identities. Environment variables are configuration, not example real secrets.
5. Never impersonate a provider integration. Only show `Connected` after verified OAuth and an authenticated API read. Distinguish disconnected, installing, authenticated, syncing, partial, failed, needs reauthorization, and fresh data.
6. Financial values must be defined precisely: distinguish total paid order amount from revenue, refunds, sales tax, discounts, gross/net profit, currency conversions and cash collections. Show provenance, freshness and any Shopify permission or pagination limitations.
7. Before handling merchant/customer PII in production, assess Shopify protected customer data permissions, retention and GDPR obligations, webhook deletion events, and access logging. Request consent and appropriate scopes. Never invent that approval was received.
8. Domain AI must use deterministic, permission-scoped read tools and only interpret returned facts. Provider writes/actions require server-side policy checks, an authenticated merchant approval and audit trails. Do not implement silent external messaging or campaign changes.
9. UI brand is premium editorial: Ayo black `#0A0A0A`, beige `#EDE5D8`, warm white `#F8F5EF`, charcoal `#252525`; Syne headline, DM Sans UI, DM Mono figures. Home/Ayo/Work/Grow/Business navigation may be staged. Avoid repetitive generic admin-card designs and green status-pill clutter.
10. Add tests for auth, tenant isolation, OAuth replay/HMAC validation, token encryption and refresh, webhook verification/idempotency, sync paging/failures, missing data, and critical business metrics. Run tests after each coherent change and report evidence. Keep merchant data and credentials out of tests.
11. Work in reviewable PR-sized increments. Do not deploy publicly, connect real merchants or alter external resources without explicit confirmation. The repo currently has no production secrets or verified third-party merchant installation.

## Development approach

Read `CODEX_BUILD_TASK.md` for the ordered milestones and acceptance criteria. Start with Phase 0 and Phase 1. Prioritize a reliable single live Shopify development-store connection before adding broad integrations, operators, or marketing automation. For each phase: implement, run tests, document what works vs what is blocked, and leave clear next actions.

## Verified Shopify baseline and current Python SDK (24 October 2026)

Read `docs/06_CONNECTED_SHOPIFY_BASELINE.md`. Shopify is now connected to ChatGPT for read-only merchant queries, and the identified store is a **trial-plan empty store**, not an Ayo OAuth install. Its zero products/orders/sales are a genuine baseline for validating empty states only; no Shopify store data was written. Do not assume this plugin supplies Ayo's app credentials, install or OAuth token.

Shopify released the official `shopifyapp` Python v1.0 package in Aug 2026, supporting webhook/request verification, token exchange and Admin GraphQL retries for FastAPI. **Evaluate using the maintained official package** instead of bespoke HMAC/OAuth code, and verify current API contracts in shopify.dev. New public apps after April 1, 2026 require expiring offline access tokens. Avoid embedding copied Shopify secrets into code or tests.
