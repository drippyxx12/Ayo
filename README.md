## Current development slice — 25 October 2026

The uploaded ZIP has been extracted into a local `codex/search-first-foundation` branch. The original archive and its hashes are preserved. See [baseline evidence](BASELINE_TEST_RESULTS.md), [risk register](RISK_REGISTER.md) and [source decision](docs/ADRs/0001-source-of-truth.md).

This slice adds public name/URL/no-website intake before signup, with explicit unavailable states while search and secure fetching remain unconfigured. It does **not** generate sourced reports or leads, fetch websites, claim domains, connect live Shopify, or send messages. Existing account/store flows remain an alpha. Shopify is optional.

For a reproducible Python 3.12 environment, install `pip install --require-hashes -r requirements.lock` in a virtualenv and run `python -m pytest -q`. Running locally with no secrets creates ephemeral development keys; set durable secrets securely before real use. Never put real provider credentials into committed files. See the setup below for environment names.

GitHub currently reports `drippyxx12/Ayo` as public. No new source has been pushed or deployed from this slice; the handoff calls for a private canonical repository. Historical connection/status paragraphs below describe the original archive and are not current access checks.

## Highest-priority founder update — 25 October 2026: SEARCH-FIRST, not signup-first
**Binding UX sequence:** public visitor `SEARCH (name/site/social) → source-backed website/business research → useful mini-report + optional actual organization-level lead preview → CTA create free account → secure report claim and private workspace → Ayo sourced lead discovery & operations → OPTIONAL Shopify or other integrations`. E-commerce only; Africa-first for Nigeria, Ghana and later countries. Ayo must also work for businesses with NO website, via permitted public listings or owner-supplied labeled facts. **Never require Shopify or signup to see the initial public mini-report.** Public research never grants site ownership, OAuth permissions or marketing consent. Model recommendation: Gemini for cited web discovery and URL analysis; Claude optional behind an evaluated adapter for complex planning; actual execution through Ayo's typed approval/policy engine. DO NOT confuse AI model chat subscriptions with API credentials or provider spend. Detailed contracts: `docs/25–28`, `architecture/search_first_journey.json`, `architecture/ai_provider_routing.json`, `architecture/mini_report_schema.json`. These are target specs; providers NOT YET CONFIGURED.

**CANONICAL 25 OCT 2026 OVERRIDE: PUBLIC SEARCH → VERIFIED SITE RESEARCH → SOURCED MINI-REPORT → CREATE ACCOUNT → SAVE/CLAIM REPORT → OPTIONAL PROVIDERS (SHOPIFY) → SOURCED LEADS & GOVERNED ACTIONS. Shopify is NOT required to use Ayo, and public assessment precedes signup. Read `docs/25_SEARCH_FIRST_DISCOVERY_TO_SIGNUP_CANONICAL.md`. Every available feature remains FREE to the first 500 USER accounts. Gemini is a provisional primary engine; Claude is an optional adapter pending evaluations. None of this newly specified workflow is live in the current alpha.**

## October 25 engineering revision (Codex handoff)
Read **`START_CODEX_HERE.md`** first. This ZIP now contains a layered reference architecture, public website search/crawl source contracts, business-lead discovery and sales approval pipeline, Nigeria/Ghana country capability design, privacy/gating and implementation slices. Only URL input classification, URL syntax checks and local HTML observation extraction are implemented for website research; **no live public crawling, search provider, lead discovery, messaging or sales execution works yet**. The manifests in `architecture/` are design-only; they are not live providers. Shopify remains unverified outside mocks. Run `python -m pytest -q` locally to reproduce the app and spec checks; user credentials and external vendor permissions are not included.

---

# Ayo engineering handoff — 25 October 2026

**Ayo is Ayo:** unified intelligence for e-commerce, with independent public **Website Intelligence** (search a business by name or paste URL) and **authorized connected commerce intelligence** (Shopify first). These are separate capabilities and permission boundaries. Read `FOUNDER_BRIEF.md`, `docs/11_WEBSITE_INTELLIGENCE_PRODUCT_AND_UX.md`, `docs/12_ARCHITECTURE_BLUEPRINT_AND_TRUST_BOUNDARIES.md`, and `docs/15_CODEX_PHASE_PLAYBOOK.md` before building.

**Current status:** local FastAPI Shopify alpha + pure no-network website-intelligence parsing/input primitives; actual search provider, secure fetch/crawl workers, Shopify app installation, email verification, production Postgres and unified LLM executor are **NOT implemented**. 26 local tests pass with mock responses and pure fixtures; no real Shopify or website has been fetched by this app. Tests are **not** production validation.

**Private repository:** Intended account `drippyxx12` currently has no accessible repository or GitHub App installation through the connector. No private repo or GitHub push has occurred. Review `docs/17_REPOSITORY_HANDBOOK_AND_DECISIONS.md` before upload and avoid pretending that this ZIP is a GitHub repository.

---

> **Founder update — 24 Oct 2026.** This repository is a security/data-connection ALPHA and **not the intended full Ayo V1**. Read [`FOUNDER_BRIEF.md`](FOUNDER_BRIEF.md) for founder-confirmed requirements and [`docs/10_CODEX_DELIVERY_GATES.md`](docs/10_CODEX_DELIVERY_GATES.md) for what Codex must implement. Ayo is its own AI-native e-commerce business operating intelligence, not defined by Shopify or other platforms. A first integration proof can be read-only; commercial V1 needs a unified intelligence plus at least one genuine approved external action. **All released features are free for the first 500 distinct customer user accounts**; no Ayo capability paywalls for them. Count users, not workspaces. Detailed policy is in docs/09. **None of these additions are currently implemented merely because they appear in the specifications.**

# Ayo — Real Shopify-connected Alpha (not a mock dashboard)

A working, backend-driven **starter application** for an independent Ayo merchant SaaS. Accounts, store connections, and Shopify reads are real code paths; no dummy business data is seeded. This is **not yet a production-grade or publicly deployed product**.

## What actually works in the code

- Registration / login / logout with password hashing and signed SameSite cookies.
- Per-user isolated workspace: no one user's store data is shown to another.
- Shopify standalone-app OAuth authorization code flow with state nonce, timing, shop domain allowlist, HMAC validation.
- Encrypted Shopify offline access token & refresh token (Fernet key supplied through env), expiring tokens and refresh rotation.
- Server-side read-only GraphQL queries: store currency/name, products, orders. No fake numbers.
- Shop sync stores aggregates, a daily order-value series and a compact product list. It deliberately avoids storing customer identities.
- Uninstall/shop redact webhook endpoint verifies the raw-body Shopify HMAC and deletes local connection and snapshot.
- Scoped approval handling: no write scopes, no send buttons, no imaginary AI actions.
- Zero-data initial view until a Shopify store is genuinely connected and synced.

## Quick start on a developer machine

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
# Paste generated values into SESSION_SECRET and TOKEN_ENCRYPTION_KEY of .env
# Set Shopify client ID and secret, APP_ORIGIN, DATABASE_URL (if using Postgres)
set -a; source .env; set +a
uvicorn ayo.app:app --host 127.0.0.1 --port 8000 --reload
```

Visit `http://localhost:8000`. Shopify requires the exact HTTPS redirect for hosted testing. For local store authorization use an HTTPS development tunnel and set `APP_ORIGIN` to its fixed, authorized URL. Do not authorize unknown tunnels.

## Shopify configuration (must be completed in Shopify Dev Dashboard)

Create an app for external merchant installations. Configure the app URL and allowed redirect to:

```
https://your-real-domain.example/shopify/callback
```

Request least-privilege scopes `read_products,read_orders` and set the env values `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `APP_ORIGIN`. Request protected customer data approval and app distribution/review as required for order-level analytics and public installation. For a public app use **expiring offline tokens**, refreshed server-side; this code asks for `expiring=1`. Shopify's requirements evolve, so validate on a development store with current docs before onboarding real merchants.

API version defaults to `2026-10` (change by env as Shopify versions advance). The code is built as a standalone app (not embedded in Shopify Admin), hence authorization code flow rather than App Bridge token exchange.

Configure webhook endpoints in the Dev Dashboard (required privacy topics):

- `/shopify/webhooks/app/uninstalled`
- `/shopify/webhooks/shop/redact`
- `/shopify/webhooks/customers/data_request`
- `/shopify/webhooks/customers/redact`

Send the raw signed Shopify webhook payload; this app validates the signature against the Shopify app secret. Privacy events are currently acked because Ayo stores no customer personal records. **Production requires retention/deletion policies, auditable handling, retry/reconciliation and compliance validation before serving merchants**. Shopify recommends app template based authentication for safety; this standalone implementation should undergo code/security review.

## Important data limitations

- Shopify order access may be limited to 60 days by default, and can be restricted by protected data permissions. Order totals are **paid order value from current order totals**, not official net revenue, cash receipts, or accounting-grade reconciliation. Currency is read from Shopify.
- Sync queries up to 10 pages of 75 records each for products and orders. A limitation notice appears if it reaches this cap. No background queue yet. For large stores use bulk operations and incremental webhooks.
- Gross profit, net profit, ROAS, customer loyalty and AI recommendations **are intentionally absent**, because the connected data isn't sufficient to support them. Profit requires costs; advertising requires ad platforms; retention needs consented customer-level access with approval.
- The app offers one Shopify store per workspace and a single account owner. Full team membership/roles need to be built.
- There is no seeded data and there are no simulated provider connections.

## Production launch blockers — do not skip

- Provision production managed PostgreSQL (set `DATABASE_URL`), database migrations, backups and connection management. The alpha currently uses `create_all()` rather than migrations.
- Email verification, password recovery, bot/rate limiting (distributed), suspicious-login detection, user/account deletion, session revocation.
- Detailed GDPR/privacy policy, consent requirements, Shopify review & protected customer data approval, deletion auditing and supported legal terms.
- Reliable background incremental sync, pagination/bulk import, idempotent webhook delivery, queue/retry, rate-limit backoff, app/uninstall cleanup race conditions and job monitoring.
- Token refresh concurrency locks and robust error-handling across multi-instance workers (the included refresh logic is functional but lacks inter-process serialization).
- Financial metric and timezone definitions, refunds/tax/discount reconciliation, multi-currency support, accounting review.
- A real AI/agent orchestrator with per-merchant authorization, deterministic tool contracts, approval policy, audit logs, human approval and safe provider adapters. It is **not** implemented in this initial alpha.
- Independent security testing and staged customer trials before public availability.

## Tests

```bash
ENVIRONMENT=test SESSION_SECRET=test-secret-that-is-over-32-characters-123456 TOKEN_ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())') pytest -q
```

The tests mock Shopify's network responses. They do not claim to have connected a real merchant or completed an end-to-end public installation.

## Deployment

Can deploy on a Python ASGI host such as Render or Fly.io with managed PostgreSQL, HTTPS and long-lived environment secrets. Before production, resolve blockers above. This archive has no actual merchant credentials or private keys.

Official docs: https://shopify.dev/docs/apps/build/authentication-authorization , https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens , https://shopify.dev/docs/api/admin-graphql/latest/queries/orders , https://shopify.dev/docs/apps/build/webhooks/subscribe
