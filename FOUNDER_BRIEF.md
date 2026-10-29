## Highest-priority founder update — 25 October 2026: SEARCH-FIRST, not signup-first
**Binding UX sequence:** public visitor `SEARCH (name/site/social) → source-backed website/business research → useful mini-report + optional actual organization-level lead preview → CTA create free account → secure report claim and private workspace → Ayo sourced lead discovery & operations → OPTIONAL Shopify or other integrations`. E-commerce only; Africa-first for Nigeria, Ghana and later countries. Ayo must also work for businesses with NO website, via permitted public listings or owner-supplied labeled facts. **Never require Shopify or signup to see the initial public mini-report.** Public research never grants site ownership, OAuth permissions or marketing consent. Model recommendation: Gemini for cited web discovery and URL analysis; Claude optional behind an evaluated adapter for complex planning; actual execution through Ayo's typed approval/policy engine. DO NOT confuse AI model chat subscriptions with API credentials or provider spend. Detailed contracts: `docs/25–28`, `architecture/search_first_journey.json`, `architecture/ai_provider_routing.json`, `architecture/mini_report_schema.json`. These are target specs; providers NOT YET CONFIGURED.

**CANONICAL 25 OCT 2026 OVERRIDE: PUBLIC SEARCH → VERIFIED SITE RESEARCH → SOURCED MINI-REPORT → CREATE ACCOUNT → SAVE/CLAIM REPORT → OPTIONAL PROVIDERS (SHOPIFY) → SOURCED LEADS & GOVERNED ACTIONS. Shopify is NOT required to use Ayo, and public assessment precedes signup. Read `docs/25_SEARCH_FIRST_DISCOVERY_TO_SIGNUP_CANONICAL.md`. Every available feature remains FREE to the first 500 USER accounts. Gemini is a provisional primary engine; Claude is an optional adapter pending evaluations. None of this newly specified workflow is live in the current alpha.**

**Founding access rule (founder-confirmed 25 Oct 2026): ALL AVAILABLE FEATURES ARE FREE FOR THE FIRST 500 DISTINCT CUSTOMER USERS (ACCOUNTS), not 500 businesses. There are NO feature paywalls, operator tiers or paid add-ons for their Ayo capabilities, including features shipped later. Preserve founding-user entitlement across their authorized workspaces. Safety/anti-abuse safeguards and independently disclosed external provider fees are not permission to silently add an Ayo feature paywall. No automatic expiration or billing is authorized; lifetime contractual wording remains a founder/legal decision. See `docs/09_LAUNCH_AND_FREE_500_POLICY.md`.**

## Founder's additional confirmed direction — 25 October 2026
**The core difference is built specifically for African e-commerce operators (Nigeria, Ghana and future markets), not generic global SaaS with a translated UI.** Ayo must understand regional buyer journeys, mobile-first and social-led selling, WhatsApp-first customer touchpoints, bank transfers, Mobile Money and regional payment statuses, NGN/GHS money, local commerce and operational language. Tailor recommendations from actual market and merchant facts, never presumed demographic or cultural traits.

**Founder now also wants:** website search and public website reading *before* connecting Shopify, plus capabilities inspired by researching tools' prospect-finding/real-leads/sales workflows. Ayo must discover **real source-backed businesses**, assess fit for the merchant's products and country, prepare appropriate outreach and track actual pipeline outcomes. Sending messages and real sales remain distinct, permissioned, regulated phases. No fabricated leads or revenue.

**Codex required reading order:** `START_CODEX_HERE.md` → `FOUNDER_BRIEF.md` → `AGENTS.md` → `docs/11–23` → source/test audit. Preserve Ayo as its own identity. The architecture directory holds **design contracts, not live providers**. Explicitly mark website crawler and lead system as UNBUILT. The first coherent product will have both public site investigation and authenticated commerce as independent, securely joined paths.

---

# Ayo — founder's product decisions and developer brief
**Decision date:** 24 October 2026 · **Artifact:** real product engineering handoff, not finished SaaS

## Identity — founder-confirmed
**AYO is AYO.** It must have its own identity, voice, experience, software architecture and product strategy. Do not market, describe, name, or implement Ayo as “a version of” or “a competitor clone of” any other platform. Third-party platforms are merely **integration providers** and references for technical compatibility, never Ayo's definition.

**What Ayo is:** an AI-native operating intelligence for e-commerce businesses. Each merchant signs up for their own private workspace, authorizes their own sources, receives analysis grounded in their actual business data, and can empower Ayo to prepare and perform governed work. One Ayo coordinates available, verified skills rather than making a merchant manually orchestrate many artificial characters. Observe → Understand → Prioritize → Propose → Authorize → Act → Verify → Measure → Learn.

## Founder-confirmed addition — site search and website intelligence (25 October 2026)

Customers should be able to **search by company/site name** or **enter a website URL**, ask Ayo to read the publicly accessible site, and use Ayo's unified intelligence to analyze public products, positioning, web UX and evidence-based improvement opportunities. Unlike connection-based Shopify analysis, this works without account installation. To join public website facts to a merchant's private commerce data, first verify site ownership and independently authorize data providers. The user's reference to Polsia was for the *research/orchestration capability*, not product branding, copying its architecture or granting automatic autonomy. Treat this as a V1 customer capability with safe-read and provenance acceptance, while connected store data and approved writes follow their own gates.

## Founder-confirmed requirements

| Topic | Decision |
|---|---|
| Initial customer category | **E-commerce only.** No brick-and-mortar or physical retail operations in initial scope. |
| First e-commerce integration | **Shopify**, with official merchant-facing installation and independent Ayo account login. |
| Broader connectivity | Custom website integration and installations **later**. Other e-commerce platforms can follow; never require every customer to use Shopify forever. |
| Nigerian site-builder concept | A possible future Ayo Storefront experience, **not committed for V1**. Research feasibility once the operating intelligence works. |
| Interaction paradigm | **One unified Ayo assistant**, which dynamically selects and coordinates specialized capabilities based on real business context and integration permissions. |
| Capability accessibility | **Every released Ayo feature is free for each of the first 500 real registered users.** No premium feature/agent/add-on tiers for founding accounts. Security/provider limitations are separate from billing. Never imply undeveloped functions work. |
| Commercial model | **First 500 distinct customer user accounts: all Ayo features free.** Count users, not businesses or stores. Later-user pricing requires founder approval; founding-user access must not silently change. Lifetime legal language remains undecided. |
| Ambition | The most complete and polished **honestly working** first customer release feasible; not a passive mock dashboard or fake AI workforce. |
| Product identity | “Ayo is what it is” — its own brand, not positioned as another product. |

## Proposed engineering defaults — NOT final founder answers

- **Initial work priorities** (Q1 still not explicitly answered): grounded e-commerce diagnosis, product/catalog optimization and prepared sales/growth actions. Use merchant interviews to reprioritize.
- **Autonomy** (Q2 not answered): **Ask before acting**, with explicit granular permissions and deterministic server-side checks. Autonomous within limits is a future opt-in, not V1 default.
- **First external write** (recommended, not approved): Shopify product-title/description optimization, presented as a diff requiring merchant approval. Only after official write permissions, exact product targeting, audit, rollback/versioned snapshot and external-result verification. NO hidden automatic change.
- **Other integrations**: after Shopify, consider WooCommerce, Paystack/Flutterwave, WhatsApp Business, Meta/Google ads, and custom sites. Order depends on practical usage, merchant demand, security and provider permissions; proposals, NOT shipped or mandatory for day one.
- **Launch location**: Nigeria-first product and support; permitted e-commerce merchants in other supported countries can join as infrastructure/compliance allow. Platform design must not assume NGN currency or African geographic data for every store.

## Product versus technical milestones

A **real technical prototype** means an actual merchant can register, log in, authorize Shopify, reconcile real business data and see truthful empty states. This can be achieved without a write action and is a *technical proof*, not the final customer V1.

A **meaningful customer V1** must additionally include a useful unified Ayo experience, multiple real **read** capabilities (sales trends, product catalog, inventory where permissions allow, business diagnosis), and **at least one genuine merchant-approved external action** that succeeds and can be verified through the provider. It must include clear error states, a signed approval/audit trail, and no imaginary agent work. A capability not connected/authorized must be disclosed as unavailable.

A **future full vision** encompasses more external systems, proactive governed monitoring, richer business memory, and more specialized skills. Do not pretend the product can run everything before integrations are built.

## Forbidden failure modes

- Calling Ayo “Shopify analytics software” or positioning it as a clone of an existing platform.
- Pre-populating a new customer's production account with fictional merchant sales, demo logos, fake status chips, or fabricated operator activity.
- Showing “Connected” before completed OAuth + authenticated API read, or calling an approved action “executed” without verifying a provider result.
- Letting an LLM issue writes, choose authorization scopes, or decide limits outside deterministic policies.
- Marketing actual connected data as live-streaming when the most recent sync is stale or partial.
- Putting any available feature behind a paywall for any of the first 500 users; counting 500 businesses rather than users; or asserting a lifetime contractual commitment that the founder has not yet finalized.
- Building a storefront builder as a substitute for Ayo's core business intelligence.
- Replacing the canonical Emergent codebase without inspecting it. This ZIP is a separate alpha, not necessarily the production foundation.

Read `docs/07_AYO_V1_PRODUCT_REQUIREMENTS.md`, `docs/08_UNIFIED_INTELLIGENCE_AND_ACTION_CONTRACTS.md`, `docs/09_LAUNCH_AND_FREE_500_POLICY.md` and `docs/10_CODEX_DELIVERY_GATES.md` before starting feature development.
