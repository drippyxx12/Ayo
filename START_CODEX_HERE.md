## Highest-priority founder update — 25 October 2026: SEARCH-FIRST, not signup-first
**Binding UX sequence:** public visitor `SEARCH (name/site/social) → source-backed website/business research → useful mini-report + optional actual organization-level lead preview → CTA create free account → secure report claim and private workspace → Ayo sourced lead discovery & operations → OPTIONAL Shopify or other integrations`. E-commerce only; Africa-first for Nigeria, Ghana and later countries. Ayo must also work for businesses with NO website, via permitted public listings or owner-supplied labeled facts. **Never require Shopify or signup to see the initial public mini-report.** Public research never grants site ownership, OAuth permissions or marketing consent. Model recommendation: Gemini for cited web discovery and URL analysis; Claude optional behind an evaluated adapter for complex planning; actual execution through Ayo's typed approval/policy engine. DO NOT confuse AI model chat subscriptions with API credentials or provider spend. Detailed contracts: `docs/25–28`, `architecture/search_first_journey.json`, `architecture/ai_provider_routing.json`, `architecture/mini_report_schema.json`. These are target specs; providers NOT YET CONFIGURED.

**CANONICAL 25 OCT 2026 OVERRIDE: PUBLIC SEARCH → VERIFIED SITE RESEARCH → SOURCED MINI-REPORT → CREATE ACCOUNT → SAVE/CLAIM REPORT → OPTIONAL PROVIDERS (SHOPIFY) → SOURCED LEADS & GOVERNED ACTIONS. Shopify is NOT required to use Ayo, and public assessment precedes signup. Read `docs/25_SEARCH_FIRST_DISCOVERY_TO_SIGNUP_CANONICAL.md`. Every available feature remains FREE to the first 500 USER accounts. Gemini is a provisional primary engine; Claude is an optional adapter pending evaluations. None of this newly specified workflow is live in the current alpha.**

**Founding access rule (founder-confirmed 25 Oct 2026): ALL AVAILABLE FEATURES ARE FREE FOR THE FIRST 500 DISTINCT CUSTOMER USERS (ACCOUNTS), not 500 businesses. There are NO feature paywalls, operator tiers or paid add-ons for their Ayo capabilities, including features shipped later. Preserve founding-user entitlement across their authorized workspaces. Safety/anti-abuse safeguards and independently disclosed external provider fees are not permission to silently add an Ayo feature paywall. No automatic expiration or billing is authorized; lifetime contractual wording remains a founder/legal decision. See `docs/09_LAUNCH_AND_FREE_500_POLICY.md`.**

# AYO — Codex engineering mission: Africa-first e-commerce operating intelligence
**Build date:** 2026-10-25. **State:** runnable standalone FastAPI alpha plus tested non-network URL parsing/HTML extraction primitives and detailed unimplemented target specs. **No live Shopify, web crawling/search, lead search, outreach or customer sale is yet verified.** Don't mistake documentation or JSON registries for shipped software.

## Founder vision in one paragraph
**Ayo is Ayo.** One unified AI intelligence for African e-commerce businesses, deeply adapted to how Nigerian, Ghanaian and future regional sellers find customers, sell through websites/social and WhatsApp, take payments by cards/bank transfers/Mobile Money, fulfill sales and grow. Customers sign up, own private business workspaces, can investigate public business websites *even without Shopify*, then connect Shopify and other platforms through their own explicit authorization. Ayo can find **real**, documented B2B business lead candidates, assess them for fit, prepare lawful pitches, and eventually perform merchant-approved actions via verified external providers. Sales only count when actually verified. All released Ayo features are free for the first 500 distinct customer USERS (not business workspaces), with no premium feature tiers. Lifetime contractual language remains unfinalized.

## Engineering non-negotiables
- Never brand Ayo as a clone of Polsia, Klaviyo, Shopify, or another company. Their features can be researched as references, not copied.
- Never seed real workspaces with fabricated revenue, orders, merchant names, AI actions, leads, prospects, replies or sales.
- A search-result website, a domain-control proof, Shopify OAuth and approval to send marketing are **four separate security/permission boundaries**.
- No server-side arbitrary URL fetch before SSRF DNS/redirect/egress policy is implemented and tested.
- Every claim and lead must be sourced; every business/currency metric defined; every proposed action explicitly status-labelled.
- Do not automatically email/WhatsApp unsolicited leads. Build a draft and approval pipeline, provider-checked lawful/consent status, suppression and opt-outs, then send only if legitimately allowed and merchant authorized.
- Enforce tenant/authorization limits outside LLM; no raw provider tokens in prompts, browser code or chat logs. A model's suggestion never grants authority.
- Country-aware business rules must be based on merchant-selected/verified market and actual provider support, not guessed from names/ethnicities/where a browser appears to be.
- First 500 means distinct legitimate *customer user accounts*, not verified businesses or stores; all released features are accessible without an Ayo feature fee. Preserve independent security checks, authorized scope and disclosed external vendor charges.

## Read in this order
1. `FOUNDER_BRIEF.md` and `AGENTS.md` (founder direction and safety rules).
2. `docs/11_WEBSITE_INTELLIGENCE_PRODUCT_AND_UX.md` through `docs/17_REPOSITORY_HANDBOOK_AND_DECISIONS.md` (earlier website technical architecture and source handling).
3. `docs/18_AFRICA_FIRST_COMMERCE_STRATEGY.md` through `docs/23_IMPLEMENTATION_SLICES_AND_VERIFY_FIRST.md` (regional product behavior, web research, leads, law, executable gates).
4. `architecture/country_capabilities.json`, `architecture/skill_registry.json`, `architecture/specimen_api_contracts.json` (machine-readable **design** configuration).
5. `ayo/app.py`, `tests/test_app.py`, current configurations, then `docs/01_SOURCE_SECURITY_AUDIT.md` and `docs/15_CODEX_PHASE_PLAYBOOK.md`.

## Immediate first Codex tasks (start work, don't merely re-document)
- **PR-00** establish baseline and fix highest-priority dependency, auth, tenancy, token and financial errors; run tests; set up CI and secret scanning; check original Emergent code if founder supplies it. Write actual commit-level code plus tests.
- **PR-01** canonical PostgreSQL models and scoped memberships; use migrations; prove no cross-tenant leaks.
- **PR-02** introduce stable source/evidence models and secure public URL validation + hostile redirect tests. **Do not enable arbitrary crawling until controlled egress exists.**
- **PR-03** provider-backed website search or clear `search_not_configured`, with honest UI; add sourced URL research pipeline.
- **PR-04** lead campaign + B2B company research + market-aware scoring + draft-only sales pipeline. Never fabricate contacts/consent.
- Continue separately with official Shopify OAuth and live development-store checks; then grounded unified Ayo and approved write workflows. Follow all gates in `docs/23`.

## Per-PR report format
Scope, source files, test command and result, changes to authorization boundaries, provider permissions, currency/localization logic, source evidence, mocked-vs-live result, user-visible truthful states, secrets/deployment impact, risks and next gate. Explicitly state `NOT TESTED LIVE` when no authorized external accounts are available.

## Private GitHub repo handoff limitation
Founder requested second GitHub account `drippyxx12`; connection was verified but **0 accessible repositories and no GitHub App install**. The available GitHub connector lacks repository creation. Ayo has therefore **NOT been uploaded**. Founder's next step is to create a **private** repository on this account and grant access to the connector. Once verified private, push **the extracted files**, not a lone ZIP. Do not make it public to simplify access. Historical Floot/Base44/Lovable/Replit prototypes are separate and **not consolidated** into this source unless audited/imported explicitly.
