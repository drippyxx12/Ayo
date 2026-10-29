# Codex delivery brief — Ayo product V1, not a fake demo

## Strict instructions

Read `FOUNDER_BRIEF.md` first, then `AGENTS.md`, `CODEX_BUILD_TASK.md` and docs 07–09. Ayo has a distinct brand and mission; Shopify is its initial data/provider integration. Do not make an unrelated demo UI or narrow the product definition to a read-only analytics dashboard. The existing FastAPI code is an **unverified standalone alpha** and the original Emergent project may already contain architecture worth retaining. Recover/audit before choosing the foundation.

## Stage gates — implement incrementally, with tests

**Gate 0: Code ownership and audited foundation.** Inspect original Emergent repo if accessible; inspect alpha source, run existing tests, list gaps, define migration path and mark what cannot be verified. Propose and implement highest-risk critical fixes; no fictional success claims.

**Gate 1: Identity and businesses.** Build/manage real merchant signup, verification, account recovery, business workspaces, membership/roles, safe sessions, tenant isolation, deletion and production DB migrations. Prove cross-tenant denial with tests.

**Gate 2: Shopify connection.** Use maintained official SDK after technical assessment, expiring offline token auth, exact callback and secure store domain validation, connection state machine and webhooks. Validate with a real authorized development store, after merchant installs Ayo separately. The ChatGPT Shopify connector is not a substitute.

**Gate 3: Durable data and truthful metrics.** Background sync, deep pagination and Shopify throttling, reconciliation, financial definition and currency/timezone testing, honest loading/zero/stale/partial states. Explicit data freshness. Never invent profit if costs unavailable.

**Gate 4: Unified Ayo core.** Business-centric Home/Ayo/Work/Grow/Business; deterministic tenant-scoped tool registry, contextual Ayo intelligence, evidence, task drafts, capability availability by actual permissions. LLM provider may be added only with secure credentials, cost controls and guardrails. Product must not feel like disconnected agent cards.

**Gate 5: One REAL governed external operation.** Begin with merchant-approved Shopify listing copy improvement as provisional implementation. Exact-before-after preview, immutable approval, least-privilege write scope, durable queue, idempotent adapter, read-after-write verification, audit receipt and safe undo. This should be completed before proclaiming the first full customer release.

**Gate 6: Launch pilot and reliability.** Webhook and session security audits, data deletion, Shopify distribution/permission review, monitored staging, 390/768/1440px accessibility, instrumented onboarding, support, fair-use and free-500 policy finalized. Complete real signup + install + sync + Ask Ayo + approved write + verification with a consented test merchant before marketing a commercially available V1.

## Acceptance and honest report

Report: files changed, migrations, scopes, test command/result, Shopify developer-store evidence (or “NOT TESTED LIVE”), screenshots if generated, threat/security issues, permissions not granted and external setup the founder must do. Never mark “running”, “connected”, “approved”, “executed” or “measured” unless the matching external evidence exists.

If Shopify credentials, a protected-data scope, official app registration, test store or hosting access are unavailable, build/test the safe interfaces with mocks **and label them mocked**, document exact missing setup, and proceed with independent work. Don't request passwords or secrets in chat; configure vault/environment. Do not deploy production or send external messages without explicit authorization.

## First Codex prompt

“Inspect this repository and read FOUNDER_BRIEF.md, AGENTS.md, CODEX_BUILD_TASK.md and docs/07–10. Ayo is its own AI-native e-commerce intelligence and action product: one assistant, real merchant accounts and Shopify data, approved external work, all Ayo features free for the first 500 distinct user accounts with no premium-tier feature gates, while observing independent permissions and safe provider usage. Do not create a dummy dashboard. Audit the current code and the canonical Emergent baseline if accessible. Execute code-quality/security/tenancy Gate 0 and Gate 1 now, implementing working code and regression tests rather than only planning. Continue Shopify Gate 2 where external credentials are not needed; report live tests honestly.”
