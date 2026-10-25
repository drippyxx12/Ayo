> **Milestone naming correction:** Builds 0–5 can produce a valuable **technical prototype / read-only proof**. To call the product **Ayo's full first customer release**, also complete Build 7's real merchant-approved write (with policy, scopes, verified receipt and audited undo if available), finish security/compliance gates and publish the approved first-500 early-access terms. Pilot invitations may validate read-only milestones; do not advertise this as fully operational V1 before the write succeeds. The founder's current decisions are in `../FOUNDER_BRIEF.md`.

# Codex execution sequence and hard acceptance gates

## Build 0 — Source ownership and reproducible baseline
- Obtain canonical Emergent Ayo repository; compare architecture to separate FastAPI alpha ZIP. Avoid creating a second source of truth.
- Run `python -m pytest -q`, save output; configure deterministic CI, lint, typing, dependency vulnerabilities.
- Record versions/entrypoints, license status, environment/secret setup. Create threat model, code audit and decision log. **Gate:** no code lost and a branch with repeatable CI exists.

## Build 1 — Identity and tenant safety
- PostgreSQL/Alembic, business/membership roles, verified email, password reset, secure sessions with server-side revocation, rate limiting and accounts/deletion.
- Tests: two independent merchants, unauthorized access to other tenant's IDs/data/jobs, session fixation/replay, reset expiry, concurrent login and CSRF. **Gate:** security tests pass in actual PostgreSQL; user data is isolated.

## Build 2 — Shopify development-store OAuth
- Create Shopify app in appropriate distribution mode and configure callback/permissions using current official docs, `expiring=1` offline token exchange, token refresh rotation and rate limits.
- Tests: nonce+HMAC, URL encoding, timestamp, replay, missing scope, token rotation, malformed/cancelled install, uninstall idempotency.
- **Live gate:** authorized development-store install and authenticated shop identity read with redacted evidence. Do not state connected without this.

## Build 3 — Durable sync and metrics
- Initial sync products, order facts, inventory when permitted. Cursor checkpoints, durable queue, retry/backoff, webhook events and incremental reconciliation. Store timezone/currency, definitions and completeness.
- Tests: 0 / 1 / >750 orders; 0 / 1 / >750 products, throttled GraphQL, partial failures, canceled orders, refunds, partial payments, zero-decimal currency, boundary-timezone orders, reinstall while syncing, duplicate webhook, permission revocation.
- **Live gate:** compare at least two merchant report periods against Shopify source with documented formula, scope and expected rounding; no fantasy revenue.

## Build 4 — Premium but truthful product shell
- Home, Ayo, Work, Grow, Business, Connections and Settings; real data on Home, read-only evidence with source/freshness. No fabricated ROAS/margins/customers.
- Empty states for no business, no store, unverified store, syncing, sync failed, partial, insufficient scope, no records; accessibility and mobile layouts.
- **Gate:** keyboard and screen-reader smoke tests and 390px/768px/1440px UI checks.

## Build 5 — Grounded merchant questions
- Tool registry and validated business query interface. Ask Ayo can explain observed trends and limitations; no off-tenant prompt injection or fabricated metrics.
- Tests: unsupported topics, missing permissions, stale data, conflicting currency, unsupported periods, contradictory source records, date boundaries, prompt injection and “do it” requests when no action capability. **Gate:** deterministic evidence in answer with no phantom actions.

## Build 6 — Read-only staging / invited integration proof (after prior gates)
- HTTPS staging/production setup, backups/restore drill, monitoring, privacy/compliance process, support and Terms/Privacy, Shopify distribution approvals. Invite consented merchants only when ready.
- Human pilot: sign up → verify → connect → see real data → ask question → reconnect/uninstall → check deletion.

## Build 7 — First real Ayo operator (required for complete customer V1)
- Choose exactly one merchant problem from pilot evidence. Add saved action draft, policy rules, preview, approval, provider-specific execution only with permitted scopes and opt-in, receipts and measured outcomes. Never release unrestricted autonomous mode first.

## Definition of successful **technical** prototype (not yet full V1)
Not a static landing page or fake demo: **one real merchant logs in, authorizes their own Shopify development store, sees a mathematically reconciled statement about actual data, asks a grounded question, and can view freshness and disconnect cleanly.** Production launch requires further security/privacy approval.

## Engineering task format
For each change: (1) state observed problem, (2) write failing test, (3) implement smallest safe change, (4) run tests/build/security checks, (5) submit PR/diff, (6) attach evidence and limitations, (7) update backlog with actual status. Never mark a phase done because prose was generated or mocks passed.
