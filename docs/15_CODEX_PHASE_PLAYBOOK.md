# 15 — Codex implementation plan with exact phase gates

**Codex instructions:** Work PR-by-PR; never claim progress based on specs alone. Read `AGENTS.md`, `FOUNDER_BRIEF.md`, `docs/11...` through `docs/17...`, the existing source and test suite. Start with **Phase 0**. Preserve working source. Favor small reviewable changes and production security.

## Phase 0 — Baseline and source-of-truth verification
**Goal** remove ambiguous competing app histories before refactoring.
- Establish correct **private GitHub repo** under account `drippyxx12` (founder instructed; **not yet created/verified**). No secrets. Check branch protections and access.
- Verify historical Emergent source, if accessible, before replacing alpha. Log unknowns and architecture decision record.
- Run current tests; inspect `ayo/app.py` and identify auth, OAuth, math, webhook, sync, tenant risks; lock/synchronize dependencies. Add CI for Python tests/lint + secret scan.
- Deliverables: `docs/ADRs/0001-source-of-truth.md`, `BASELINE_TEST_RESULTS.md`, `RISK_REGISTER.md`. **Exit:** tests reproducible, private repo owned, no secrets, no accidental rewrite.

## Phase 1 — Architecture skeleton and tenant security
- Split monolith into routers/domains/adapters with tests, or document retained-module design for smallest safe delta.
- PostgreSQL/Alembic, business memberships, CSRF, email verification/recovery, authentication rate limits, session invalidation, tenant-scoped access and deletion. Avoid user-selected unrestricted business ids.
- **Tests:** cross-tenant read, search, report, approval and background job isolation; forged sessions; migration upgrade/down.
- **Exit:** authenticated users cannot read or mutate another tenant's private data. Secure staging instance is provisioned behind HTTPS.

## Phase 2 — Real Shopify authorization and data correctness
- Implement supported app setup, official Python `shopifyapp` SDK evaluation, expiring offline tokens and refresh lock, scopes/privacy webhook path.
- OAuth install with **merchant-authorized development store**; read actual shop/products/orders and optional inventory. No imported PII unless approved. Background full/incremental sync, retries/rate-limit; currency/refund/tax reconciliations.
- **Tests:** OAuth callback HMAC/state/replay, concurrent refresh, encrypted token never logged, uninstall/reconnect, partial sync failures, Shopify side-by-side numbers, zero data.
- **Exit:** actual authorized Shopify development store displays correct source-provenance, no imaginary statistics, and a real successful API read.

## Phase 3 — Website Intelligence foundation: search/URL
- Implement search provider interface; if API key absent return honest `search_not_configured`. Provide direct URL analysis first as a small operational slice; **never secretly substitute a static search result list**.
- Controlled egress proxy / DNS IP pinning and SSRF tests *before allowing any user URL to be fetched*. Robots/terms/HTTP and legal policy; crawl job queue and budgets.
- Bounded extraction of actual permitted homepage + selected products/category/policy pages; source evidence, limits, errors, timestamps. No LLM necessary to prove core correctness.
- **Tests:** deceptive addresses, DNS rebinding, redirects to internal services, robots disallow, oversized and malformed responses, mixed internationalized domains, malformed price structured data, empty/non-HTML page.
- **Exit:** entering a public test website produces a citeable observed report and cannot access private/internal resources. No invented website conclusions.

## Phase 4 — Site/merchant knowledge integration
- Domain claim verification via DNS TXT or verified provider OAuth, explicitly separated from public search; never infer `this is your store` from website text.
- Public research evidence store, source versions, retention, tenant-scoped report access, public competitor compare. Link verified site to connected Shopify entity after deliberate merchant action.
- **Tests:** false business ownership claim, stale report, conflicting public/private catalog, cross-tenant vectors, poisoned page prompt injection.
- **Exit:** merchant can view evidence-backed site report and connected store facts side by side with classification.

## Phase 5 — Unified Ayo intelligence
- Add approved read skill registry: `website.search`, `website.research`, `website.report`, `commerce.trend`, `catalog.inspect`, `inventory.risk`, `work.propose`.
- Deterministic metric tools + evidence retrieval. Model adapter only after approved provider contract and budget; safe typed outputs, prompt-injection resistance, provenance and confidence. No hallucinated financial claims.
- **Tests:** missing data, correct citations, tenant boundary, bad source, partial crawl, model attempts to invoke write tools without authorization, budget exhaustion.
- **Exit:** Ayo answers both *What does this website communicate to customers?* and *What happened to my shop orders?* while distinguishing public versus private data.

## Phase 6 — First governed real action
- Propose product description change based on observed public copy and merchant's **authorized** Shopify catalog; original vs proposed diff, capability/scopes, policy, merchant approval, idempotent provider write, receipt, rollback where API supports.
- No outside-merchant changes; website research **never** grants write access.
- **Tests:** before/after, cross-tenant approval, stale scopes, double-click idempotency, canceled/expired approval, Shopify API failure, receipt verification, audit.
- **Exit:** a real Shopify development store is edited exactly once after human approval, with evidence and audit.

## Phase 7 — First 500 verified businesses and pilot
- Build atomic cohort issuance, abuse controls and transparent free usage limits, cost monitoring, export/deletion workflows, terms/privacy, support. Observe reliability/crawl costs/Shopify API quotas.
- Founder-approved external pilot and feedback: prove actual customer use, no unverified claimed traction. Start free but budget research and model invocations.
- **Tests:** concurrent signup limit, quota reset, eligibility, privacy purge, merchant uninstall, backups, incident drills, E2E browsers. **Exit:** release owner signs off with evidence.

## Mandatory per-PR contract
Each Codex PR must contain **Scope, Evidence, Security impact, Data migration impact, Test commands/results, Missing credentials or limitations, Rollback method, Remaining risks, Demo steps**. Update the status board only after tests or verified live proof. `implemented`, `tested-with-mocks`, `verified-on-development-store`, `production-ready` are distinct labels.

## Stop and escalate instead of guessing
Missing Shopify app ID/secret, public search API key, production DNS, hosting environment, email verification domain, legal permission/ownership, privacy data approvals. Build error states and documentation; never fabricate credentials, permissions, production revenue, scan results or executed actions.
