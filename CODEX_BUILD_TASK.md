## Highest-priority founder update — 25 October 2026: SEARCH-FIRST, not signup-first
**Binding UX sequence:** public visitor `SEARCH (name/site/social) → source-backed website/business research → useful mini-report + optional actual organization-level lead preview → CTA create free account → secure report claim and private workspace → Ayo sourced lead discovery & operations → OPTIONAL Shopify or other integrations`. E-commerce only; Africa-first for Nigeria, Ghana and later countries. Ayo must also work for businesses with NO website, via permitted public listings or owner-supplied labeled facts. **Never require Shopify or signup to see the initial public mini-report.** Public research never grants site ownership, OAuth permissions or marketing consent. Model recommendation: Gemini for cited web discovery and URL analysis; Claude optional behind an evaluated adapter for complex planning; actual execution through Ayo's typed approval/policy engine. DO NOT confuse AI model chat subscriptions with API credentials or provider spend. Detailed contracts: `docs/25–28`, `architecture/search_first_journey.json`, `architecture/ai_provider_routing.json`, `architecture/mini_report_schema.json`. These are target specs; providers NOT YET CONFIGURED.

**CANONICAL 25 OCT 2026 OVERRIDE: PUBLIC SEARCH → VERIFIED SITE RESEARCH → SOURCED MINI-REPORT → CREATE ACCOUNT → SAVE/CLAIM REPORT → OPTIONAL PROVIDERS (SHOPIFY) → SOURCED LEADS & GOVERNED ACTIONS. Shopify is NOT required to use Ayo, and public assessment precedes signup. Read `docs/25_SEARCH_FIRST_DISCOVERY_TO_SIGNUP_CANONICAL.md`. Every available feature remains FREE to the first 500 USER accounts. Gemini is a provisional primary engine; Claude is an optional adapter pending evaluations. None of this newly specified workflow is live in the current alpha.**

**Founding access rule (founder-confirmed 25 Oct 2026): ALL AVAILABLE FEATURES ARE FREE FOR THE FIRST 500 DISTINCT CUSTOMER USERS (ACCOUNTS), not 500 businesses. There are NO feature paywalls, operator tiers or paid add-ons for their Ayo capabilities, including features shipped later. Preserve founding-user entitlement across their authorized workspaces. Safety/anti-abuse safeguards and independently disclosed external provider fees are not permission to silently add an Ayo feature paywall. No automatic expiration or billing is authorized; lifetime contractual wording remains a founder/legal decision. See `docs/09_LAUNCH_AND_FREE_500_POLICY.md`.**

# 2026-10-25 CODEx ADDENDUM — founder requirements, supersedes a Shopify-only framing
Start at `START_CODEX_HERE.md`. Read `docs/11–23` plus the machine manifests in `architecture/`. These include **Africa-first country-aware commerce**, **public website search & research**, and **real B2B business lead discovery and pipeline workflows**. Website research and lead execution are NOT implemented in the current alpha; they are critical target capabilities. Treat original Shopify steps below as a necessary commerce stream, not as Ayo's entire product. Do not turn proposed country adapters into working buttons. Follow `docs/23_IMPLEMENTATION_SLICES_AND_VERIFY_FIRST.md` for the complete ordered, testable engineering path.

---

# CRITICAL REVISED CODEX BUILD SEQUENCE — 25 OCTOBER 2026

Do not begin from a narrow Shopify analytics plan. Ayo's new required **Website Intelligence** lets people search for a public e-commerce website by brand/business name or paste a URL and receive an evidence-backed, cited site report, even before Shopify installation. Separately, Shopify OAuth imports actual authorized merchant data. Unify insight in one Ayo assistant while strictly separating site research (public, no ownership implied) from merchant operations (authenticated, approved). Read `docs/11–17` and follow `docs/15_CODEX_PHASE_PLAYBOOK.md` as the authoritative phase gates. Phase 0 baseline source/security audit; Phase 1 auth/tenancy; Phase 2 search-first UI and public website/company discovery; Phase 3 URL and name research with secure egress and evidence; Phase 3b sourced mini-report and account handoff; Shopify OAuth/data is optional integration in a subsequent phase; Phase 4 claims/linkage; Phase 5 grounded intelligence; Phase 6 merchant-approved real action; Phase 7 free-500 launch governance. Coding acceptance requires tests and real API/store/site evidence, never screenshots of fictional metrics.

**Current local code** has `ayo/website_research.py` pure URL classification and real supplied-HTML extraction with no live fetching and `tests/test_website_research.py`. This is a safe foundation, not a working website scanner. Do not plug a raw `httpx.get(user_url)` into it. Before network research, deploy hardened controlled egress + robots + budgets and tests. Public search by business name requires a licensed search provider; when missing show `search_not_configured` rather than imaginary website candidates.

---

# Product direction update — 24 October 2026

**This build task must be interpreted together with `FOUNDER_BRIEF.md` (new founder decisions) and docs/07–10.** Ayo is a standalone, unified AI operating intelligence for **e-commerce businesses only**; Shopify is the first live provider, not the product's identity. Custom sites and a Nigerian storefront builder are **future/discovery**, not first-release prerequisites. Founder wants all available features free for the first **500 distinct customer user accounts** without feature paywalls; safety safeguards and third-party provider costs are separate; pricing for later users is undecided. Premium design is necessary but must not replace real integrations.

**Milestone distinction:** Existing Phase 0–4 requirements are the **technical foundation/proof**; the first strong **customer-facing V1** ALSO needs evidence-grounded Ayo Work and **one real merchant-approved executable action**, proposed as Shopify catalog copy optimization. Existing Phase 5 launch/trial acceptance should not be read as permission to commercially launch a passive read-only dashboard while claiming the full Ayo experience. Implement action gate after safe read/sync, before full commercial launch. See `docs/10_CODEX_DELIVERY_GATES.md`.

# Codex build task — turn Ayo from alpha into a real merchant SaaS

## Mission

Build **Ayo** into a secure, working multi-tenant web application that allows a merchant to register, sign in, connect **their own Shopify store** through an official authorization flow, sync **real permitted Shopify data**, view accurate business KPIs that were computed from those records, and ask grounded business questions. No pre-populated or fictional data appears as merchant truth. Do not create a separate demo-only product.

## Starting point

Use the existing repository as canonical source. It currently uses Python/FastAPI/SQLAlchemy, Shopify GraphQL Admin API, Jinja templates and pytest. The auth and OAuth paths are implemented but have not been proven against a real Shopify store. Read README, WHAT_IS_REAL, existing tests and `AGENTS.md`; audit before editing. Preserve working behavior.

## Phase 0 — inspect and stabilize (first coding task)

- Run tests and capture results; lint/type-check where feasible.
- Inventory routes, models, config, external API calls, callbacks, and webhook workflows. Flag any overclaims in documentation.
- Validate against **current official Shopify docs** that OAuth parameters, `expiring` offline tokens, refresh behavior, GraphQL order/product queries, required privacy webhooks and API version are correct. Identify gaps. Do not guess compatibility.
- Make a concrete threat model for CSRF, callback replay, SSRF, sessions, refresh races, webhook impersonation, data leakage between tenants, API rate limits, and credential handling.
- Output a short audit report and prioritize corrections in a tracked checklist.

**Acceptance:** Existing tests remain green, critical defects get regression tests and there is a clear risk/implementation plan.

## Phase 1 — production-worthy authentication and tenancy

- Replace `create_all()` with reproducible database migrations and a managed PostgreSQL-ready configuration; don't silently migrate data.
- Build email verification and safe password reset, normalized email uniqueness, brute-force protection and session revocation with secure cookie settings.
- Define a `Business`/workspace and ownership model; enforce unique account/business boundaries and index tenant IDs appropriately. Tests should prove merchant A never sees merchant B data, even with guessed IDs.
- Support secure deletion of account and business data.

**Acceptance:** A new merchant can create and verify a real account, log in/out, recover access, and access only their workspace. Test flows with PostgreSQL, not just SQLite.

## Phase 2 — genuine Shopify connection and reliable sync

- Complete supported standalone Shopify app authorization: redirect, state/nonce, HMAC, callback replay rejection, token expiry and refresh with concurrency controls, least-privilege scopes, uninstall and mandatory privacy topics.
- Build a connection-state UI: Not connected → Redirecting → Authorized → Syncing → Connected / Sync error / Permission limitation. Never say Connected without a successful API read.
- Read store details, currency, products, variants/inventory where scope permits, and orders within approved date ranges. Handle Shopify GraphQL cursors, throttling, backoffs, retries, partial syncs, API errors, scopes and app uninstall.
- Introduce a persistent background job for imports and incremental reconciliation. Store sync timestamps, errors, status and data lineage. Avoid blocking page request workers on long imports.
- Create a safe idempotent webhook workflow; comply with protected customer data approval and mandatory privacy webhooks before external merchant access.
- Add Shopify development-store integration instructions and real-store smoke tests that can run after credentials are supplied via secure secrets; NEVER use test data to claim a live connection.

**Acceptance:** In a real development store, a user clicks Connect Shopify, authorizes, and sees the correct shop identity, product count, paid order amount and sync timestamps. Disconnect and reinstall behave safely. Real connection proof must be obtained before claiming completion.

## Phase 3 — accurate merchant Home, not a demo

- Empty state prior to connection: “Connect Shopify to see your actual business.”
- Business Home: real orders, paid order amount and trend, product and stock status with timestamps and factual definitions. Never claim gross profit, ad ROAS or customer loyalty unless supporting data and permissions are present.
- Explain missing data/limits, permissions, timezones, currencies, refunds and date ranges. Support filtered periods.
- Premium responsive Ayo UI inspired by the established design tokens; accessible and usable on iPhone and desktop. Screens: Home, Ayo, Work, Grow, Business, Connections and Settings, with unavailable capabilities labeled rather than faked.

**Acceptance:** Every displayed KPI can be reconciled against an authorized Shopify development store for the same period/currency under a documented formula. Freshness and missing-data states work.

## Phase 4 — grounded Ayo intelligence

- Implement a deterministic per-tenant read-tool layer for actual orders, products, sales trends, stock and supported metrics. Put business calculations server-side.
- Add an LLM orchestrator behind clearly defined and validated tool contracts only when API credentials and budget are explicitly supplied; guard hallucinations and cross-tenant exposure. Avoid filling unknown facts with assumptions.
- Support questions such as “How are sales this week?”, “Which products are running low?” and “Why did sales change?”; reply accurately or “Not enough data.” Include provenance and the analysis time.
- For future actions, initially create a **draft only**. External writes require a deterministic permission engine, real provider capability, merchant approval, logged audit trail and idempotency.

**Acceptance:** Ayo answers from the merchant's own Shopify data with testable calculations. No real-world external action occurs without approval.

## Phase 5 — staging engineering & invited integration trials (technical proof, not final customer V1)

- Configure separate development, staging and production environments, backups, secrets, migrations, logs, Sentry/observability, uptime and error monitoring.
- Document data processing, user deletion, retention, GDPR responsibilities, Shopify distribution/protected data review, billing eligibility and legal blockers. Do not claim approval by Shopify.
- Build a comprehensive QA matrix for auth, Shopify install, reauthorization, uninstalls, revocation, multiple businesses, failure recovery, rate limiting, data correctness and mobile UI.
- Connect a real test/dev shop first. Prepare first pilot merchant onboarding only when operational and privacy requirements are satisfied.

**Acceptance:** User can independently register, connect their own store, import data, see correct analysis and securely disconnect. Automated tests, a live dev-store verification log and a deployable staging environment are provided. Production release remains gated on review/approval.

## Phase 6 — unified governed Work and first real action (required before full customer V1)

- Implement permission-aware specialist read skills coordinated by a single Ayo intelligence. Each capability must report its actual availability, data freshness and provider scopes.
- Build a Work proposal/action draft with exact target, affected product ID, before/after copy diff, server policy, merchant approval and immutable approval evidence.
- Add the **first merchant-approved actual Shopify write** (proposed catalog copy optimization), only with verified write scope and an authenticated merchant action. Verify the resulting provider state, audit idempotency and offer safe merchant-reviewed undo where supported.
- Add tests covering deny-before-approval, missing provider, revoked scope, stale product version, duplicate execution, cross-tenant action IDs, Shopify API error, successful read-after-write and no invented ROI.
- Keep Ayo brand and visual identity independent; use actual data and event-driven status, not fabricated operator activity.

**Acceptance:** At least one genuine external action is evidenced against an authorized test store, with approval, policy, provider receipt and a verified resulting state. Unverified actions remain unavailable. Then advance to the first complete customer V1 pilot after compliance and operational QA.

## Initial Codex instruction

**Execute Phase 0 and Phase 1 now.** Follow with Phase 2 where possible without Shopify secrets. Do not stop after producing a plan; implement code, tests and documentation. Do not deploy publicly or claim a real Shopify connection until verified with development-store credentials. When credentials are unavailable, leave secure configuration hooks and report the exact external setup step. Maintain one coherent repository and meaningful commits/PRs.

## New verified Shopify connection evidence (24 October 2026)

See `docs/06_CONNECTED_SHOPIFY_BASELINE.md` for observed empty-store data via the separate ChatGPT Shopify plugin. Do not mistake the connected ChatGPT plugin for an Ayo OAuth grant. Use actual zeros to test honest empty states once an Ayo app install is authorized. Also audit the newly released official Python `shopifyapp` SDK before extending this FastAPI integration; favor maintained request verification/token management clients where sound. See the Shopify security changelog of Oct 20, 2026 for cross-shop boundary testing priorities.
