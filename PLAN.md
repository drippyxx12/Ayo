# Ayo delivery plan

Updated: 2026-10-25. Overall goal: **PARTIALLY COMPLETE**.

Build one Africa-first commerce intelligence application from the existing FastAPI/SQLAlchemy/Jinja source. Preserve the imported ZIP and working Shopify alpha contracts. The acceptance path is **search a real public business → cited report → register/verify → securely save the report → reopen it in a tenant-isolated dashboard → discover genuinely sourced prospects**. A landing page, provider mock, or successful local test alone does not complete that path.

## Binding scope

- Nigeria and Ghana first, with explicitly selected business country, NGN/GHS and the corresponding IANA timezone. Never infer identity or geography from a name or browser address.
- Search accepts a name, URL, permitted public social/marketplace link, or a no-website owner-assisted path. Initial evidence must precede signup; Shopify stays optional.
- Public observations, owner-provided statements, AI inferences, private authorized commerce records and provider-confirmed outcomes remain distinct.
- The first 500 distinct legitimate customer **user accounts** receive all released and future Ayo features free. Persistent entitlement is separate from business membership, provider permission, safe usage and third-party charges. No automatic expiration, upgrade wall or later-user billing is authorized.
- Latest design: Syne headings, DM Sans UI, DM Mono metrics; black `#0A0A0A`, beige `#EDE5D8`, warm white `#F8F5EF`, charcoal `#252525`.
- Implement and test continuously. Commit verified milestone changes to the designated `drippyxx12/Ayo` repository; record actual remote commit SHAs. Do not deploy, incur provider charges, send outreach or modify merchant systems without permission.

## Milestones and acceptance

| Milestone | Work | Required evidence | Current state |
| --- | --- | --- | --- |
| M0 — Audit and source preservation | Read founder/instruction files and all architecture documents; audit actual source, dependency/secret posture and dataflow; retain original archive/hashes and reviewed working code | Audit in `docs/LATEST_REPOSITORY_AUDIT.md`, reproducible baseline, migration decisions and Git history | Audit documented; new-build integration in progress |
| M1 — Persistent identity and businesses | PostgreSQL-ready models, explicit migrations, normalized registration, business memberships, server-side revocable sessions, CSRF, rate limiting, verification/reset tokens, user-based founding grants and audit events | Migration upgrade/downgrade; PostgreSQL integration; two-tenant denial; reset/verification replay/expiry; 499/500/501 concurrency; restart persistence | Implemented and locally tested; production gates remain |
| M2 — Real research and secure report handoff | Configured permitted search/fetch adapter; explicit ambiguity selection; bounded immutable evidence; deterministic cited reports; anonymous capability/TTL; one-time claim into authorized workspace | Provider error/empty/malformed cases; source/citation validation; hostile input; claim expiry/replay/cross-session/cross-tenant; actual NG/GH research receipts before live claim | Implemented and fixture-tested; live provider access blocked |
| M3 — Merchant dashboard and lead intelligence | Real saved reports/opportunities/activity; source-inspectable leads; domain deduplication; evidence-based fit; tenant-scoped persistence; protected status transitions | Dashboard/source reconciliation; duplicate/empty candidates; no fabricated contacts; foreign-record denial; contacted/replied/converted require matching evidence | Implemented and fixture-tested; live lead discovery blocked |
| M4 — Unified AI and optional commerce | Gemini/Claude-compatible structured gateway; evidence validation and read-only orchestration; preserve optional Shopify; country/payment contracts separating pending, successful and settled amounts | Invalid model/citation/numeric claims denied; credential/permission errors; tenant boundary tests; NGN/GHS/payment status tests; real provider calls only after configured permission and budget | Implemented and fixture-tested; live provider evaluation blocked |
| M5 — Complete workflow and delivery evidence | Integrate all layers; browser and API workflow tests; source/security checks; deployment-ready configuration and precise limitations | Search→report→signup→claim→reload→leads in meaningful integration tests, plus live NG/GH provider evidence; mobile/desktop accessibility; verified GitHub commits | Pending integration; not complete |

## Implementation rules

1. Keep source, models, services and routes reviewable; avoid a framework rewrite. Use server-derived membership for every tenant query and command.
2. Treat website/model content as low-trust data. Validate citations against retrieved evidence; models cannot grant permissions, create tools or call write adapters.
3. Never fetch arbitrary user URLs with a generic client after a syntax/DNS precheck. Use an explicitly configured provider-managed fetch boundary or controlled pinned-IP egress with verified robots/terms and resource limits. Missing setup fails closed.
4. Preserve source URL, capture time, content hash, excerpt, classification and report limitations. Owner-provided facts cannot become independently observed claims.
5. Persist only necessary research/organization data. No raw credentials in prompts, logs, browser storage or committed artifacts. Verification/reset/claim secrets are opaque, hashed at rest and purpose-scoped.
6. Keep contacts, sends, replies and conversions separate. No outreach execution is in this authorized build. A discovered organization is not a customer or sale.
7. Existing Shopify remains an alpha until its separate install, token lifecycle, webhook identity, scope, sync and privacy gates are verified. Pending transfers or MoMo states are never counted as received funds.
8. Report test fixtures separately from real external evidence. Update `PROGRESS.md` and `FEATURE_STATUS.md` only after the relevant code and checks exist.

## External blockers and setup

| Blocker | Safe configuration/action required | Work that continues independently |
| --- | --- | --- |
| Licensed public search/content provider not configured | Server-only provider key, permitted source/egress policy, explicit authorization for provider charges and bounded budgets | Typed adapters, evidence/report services, failure states and offline contract tests |
| Gemini/Claude API access not configured | Server-only API key, currently available pinned model ID, approved data policy and spend limits | Model gateway, output/citation validators and orchestration tests |
| Transactional email delivery not configured | Verified sender/domain and approved delivery provider credentials | Purpose-scoped verification/reset tokens and delivery interface; no false “email sent” result |
| Production PostgreSQL and long-lived application secrets not configured | Approved DB, backup/restore policy, durable session and token-encryption secrets | Local PostgreSQL tests, migrations, tenant/services and documented configuration |
| Live Shopify/payment access absent | Actual Ayo developer app and consenting dev-store install; separately approved payment sandbox credentials/scopes | Existing integration regressions, optional connection UI and country/payment contracts |
| Historical Emergent source unavailable | Supply authorized source for a separate evidence-based comparison | Preserve and extend the accessible alpha; do not overwrite other projects |
| Deployment/spend permission absent | Explicit approval for a concrete reviewed deployment or charged provider action | Local implementation, tests, source commits and operational preparation |

Completion remains **PARTIALLY COMPLETE** until the required workflow runs on real permitted sources and persistence, with evidence recorded. Do not replace a blocked capability with fabricated production data.
