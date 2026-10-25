# Ayo feature status

Updated: 2026-10-25. **Overall goal: PARTIALLY COMPLETE.** A functional landing page/prototype is not the completion criterion.

Labels: **LOCAL VERIFIED** means code executed locally with the stated evidence; **IN PROGRESS** means implementation/integration is active but acceptance is outstanding; **BLOCKED LIVE** means real external verification requires named setup/permission; **NOT IMPLEMENTED** means no working capability is claimed. A fixture test never upgrades a feature to live.

| Feature | Current implementation status | External/live status | Acceptance gap |
| --- | --- | --- | --- |
| Search-first name/URL/social/marketplace intake | LOCAL VERIFIED; public input and no-website paths exist | Input only; search/fetch currently unavailable | Actual provider-backed discovery and report workflow being integrated |
| Owner-assisted no-website profile | LOCAL VERIFIED; escaped, explicitly unverified input | No independent research claimed | Persist selected owner facts with provenance within authorized business workflow |
| Business candidate discovery/disambiguation | LOCAL VERIFIED WITH FIXTURES | BLOCKED LIVE: permitted search provider/key and spend authorization | Actual sourced matches, empty/error behavior and explicit candidate selection |
| Public page research | LOCAL VERIFIED WITH FIXTURES | BLOCKED LIVE: configured safe provider-managed fetch/egress policy | Permitted retrieval, bounded source receipts, robots/terms and adversarial tests |
| Source evidence and actionable report | LOCAL VERIFIED WITH FIXTURES | No live report verified | Stored URLs/times/hashes/excerpts; per-claim evidence; observed/inferred/unknown classification and limitations |
| Anonymous report access and secure signup handoff | LOCAL VERIFIED ON SQLITE + POSTGRESQL | No live claim verified | Scoped expiring capability, verified account binding, atomic one-time claim and replay/IDOR denial |
| Registration/login/logout | LOCAL VERIFIED: database sessions, revocation and persisted throttling | No production identity deployment | Server-revocable sessions, persistent DB, rate limiting and current integrated tests |
| Email verification/password reset | LOCAL VERIFIED WITH FIXTURES | BLOCKED LIVE: verified sender/delivery credentials | One-time hashed token expiry/replay tests and actual delivery receipts |
| Persistent PostgreSQL and migrations | LOCAL VERIFIED: Alembic upgrade/downgrade and persistence | No production DB configured | Local PostgreSQL upgrade/downgrade, restart persistence and transaction tests |
| Business workspaces/memberships | LOCAL VERIFIED: membership and foreign-report/lead denial | No production workspace verified | Server-derived tenant selection; cross-user/role/report/lead denial |
| First 500 distinct user accounts: all features free | LOCAL VERIFIED: atomic persistent grants and PG concurrency | No live cohort or billing created | Atomic immutable user grants; 499/500/501 concurrency; future-feature access; multiple businesses consume one user slot |
| Merchant dashboard/research/opportunities/activity | LOCAL VERIFIED WITH STORED RECORDS AND FIXTURE EVIDENCE | No live merchant data | Query actual persisted records; reconcile displayed sources; honest empty states |
| Genuine lead discovery/qualification/deduplication | LOCAL VERIFIED WITH FIXTURES | BLOCKED LIVE: permitted organization source | Per-candidate evidence and fit, deduplication without invented entities/contacts |
| Discovered/qualified/contacted/replied/converted pipeline | LOCAL VERIFIED: discovery/qualification persisted; further stages evidence-gated | No messages, replies or conversions claimed | Authorized event-driven transitions and provenance; private tenant scope |
| Unified Gemini/Claude-compatible intelligence | LOCAL VERIFIED WITH FIXTURES | BLOCKED LIVE: API keys/model configuration/spend permission | Structured validated output, evidence citations, bounded cost, no unsupported facts or tool authority |
| Shopify authorization/token/read sync | Existing alpha LOCAL VERIFIED WITH MOCKS; preserved | BLOCKED LIVE: Ayo app/dev-store install/scopes | Official SDK/contract assessment, replay/refresh/webhook identity, durable sync and live reconciliation |
| NG/GH business localization | LOCAL VERIFIED: explicit NG/GH, currencies, timezones, pending-payment contract | No payment connection claimed | Explicit country, NGN/GHS/timezone rules and provider capability checks |
| Payment integration boundaries | LOCAL VERIFIED CONTRACTS; no provider adapter | BLOCKED LIVE: approved sandbox/provider credentials | Verified webhook/receipt, pending/success/settlement distinction and deduplication |
| Governed provider writes/outreach | NOT IMPLEMENTED as an executable capability | Not authorized | Exact approval, legal basis/consent, provider scopes, suppression and verified receipts; remain blocked |
| Syne headings, DM Sans UI, DM Mono metrics | IMPLEMENTED: self-hosted fonts and merchant screens | Browser verified at 390/768/1440px | Self-hosted assets, accessible responsive screens and consistent font roles |
| CI/dependency/secret checks | LOCAL VERIFIED foundation | Current-code GitHub runs 40222814711 and 40222788012 passed | Rerun after integrated changes; attach actual remote workflow and commit receipts |
| Deployment and public availability | No completed deployment | Not authorized by current request | Concrete reviewed deployment approval, production DB/secrets and launch gates |

## End-to-end completion gate

| Journey step | Required proof | Status |
| --- | --- | --- |
| Search a real NG/GH public business | Permitted provider query and actual candidate sources | BLOCKED LIVE |
| Receive a useful sourced report before signup | Captured evidence and independently checkable citations | IN PROGRESS / BLOCKED LIVE |
| Register/verify and claim the exact report | Tested HTTP flow against SQLite and real local PostgreSQL; actual email delivery missing | LOCAL VERIFIED WITH FIXTURES |
| Reopen saved report after login/restart | PostgreSQL persistence, re-login, tenant-isolation and browser checks passed | LOCAL VERIFIED WITH FIXTURES |
| Discover genuine relevant organizations | Actual provider results, deduplication and per-lead source/fit | IN PROGRESS / BLOCKED LIVE |

The overall goal cannot be marked complete until these steps have meaningful integrated test evidence **and** real permitted-source verification. Missing setup must produce truthful errors, never fabricated customers, dashboards, research, leads, AI answers or integration results.

Durable research jobs and an operator-run worker are implemented. Jobs use encrypted input, an expiring lease, bounded retries, session-bound status access and explicit failure states. Public requests do not run crawls. Live fetch remains blocked by source-policy/egress review and credentials.

## Latest evidence checkpoint

**219 tests pass with PostgreSQL enabled**, with no skipped cases and one upstream deprecation warning. Browser workflow tests passed on mobile/tablet/desktop using PostgreSQL and explicit offline provider fixtures, including source-backed reports, account verification via the encrypted test outbox, private saving/reopening and lead qualification. Actual email delivery and actual public-provider evidence remain BLOCKED LIVE.

Password-confirmed local account removal is implemented with shared-ownership protection and a disabled pseudonymous founding ledger. Workspace switching is membership-checked and does not allocate a second founding slot. HTTP password recovery revokes old cookies/sessions. Expired anonymous/security artifacts have a cleanup command; claimed reports and permanent grants are preserved. Verification-mail supersession and request-body bounds are tested. No public deployment or paid call occurred.

Public research now extracts bounded product-name/listed-price/currency observations from returned public markup and identifies publicly linked selling channels. Invalid/nonfinite/oversized prices stay unknown; no inventory, sales or functioning-checkout claim is inferred. HTML and sanitized evidence hashes are retained. These adapter paths remain fixture-tested, not live-provider verified.
