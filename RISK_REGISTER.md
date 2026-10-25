# Remaining release gates

Overall status: **PARTIALLY COMPLETE**. Local tests and GitHub checks are not production acceptance.

| Boundary | Implemented and locally verified | Remaining gate |
| --- | --- | --- |
| Identity | Opaque hashed database sessions, revocation, throttling, one-time email/reset capabilities, encrypted mail queue, HTTP recovery, password-confirmed local account removal and tenant checks | Real verified sender/delivery, account legitimacy/abuse policy, independent security review and provider/backup/legal deletion review |
| Persistence | Explicit Alembic upgrade/downgrade, preserved legacy records, PostgreSQL constraints/concurrency and HTTP persistence | Approved production DB, TLS, backups/restore/deletion propagation; legacy schema stamp must be reviewed manually |
| Founding benefits | Atomic user-based grants, boundary concurrency, future-feature access, no automatic expiry or charges | Legitimate-account/cohort terms and public launch review; no production cohort is claimed |
| Research | Fixed-host API adapter, no local arbitrary URL HTTP, approved-source/egress/spend gates, bounded jobs, source hashes and citations | Permitted provider credentials and actual vendor egress/redirect/robots/terms acceptance; real NG/GH source audit and quality evaluation |
| Reports | Anonymous TTL, hashed/session-bound claim, verified-user membership, atomic consume, replay/expiry/foreign-user denial | Real-source report and actual email-to-claim proof; production retention policy/legal acceptance |
| AI | Initial public Gemini pipeline after committed hidden evidence; source validation, absolute timeout, usage metadata and separate optional private adapters; no write tools/secrets in model context | Configured available evaluated model, approved data/spend policy and live NG/GH hallucination/precision evaluation; rules are not a universal semantic guarantee |
| Leads | Sourced organization contracts, dedupe, persistent reviewed qualification, evidence-gated later statuses | Actual permitted-source precision/location evaluation; no messaging/reply/conversion provider integration is claimed |
| Shopify | Preserved optional alpha, one-time server OAuth state, signed-payload identity binding, encrypted tokens, refresh row locking and currency validation | Current official SDK/contract evaluation, privacy processing/receipts, durable sync/reconciliation, uninstall races and authorized live dev-store proof; legacy store binding remains per user |
| Payments | NG/GH money/method contracts and pending-versus-settled tests | Verified provider sandbox adapter, webhook/settlement reconciliation and actual receipts; no live collection exists |
| Operations | CI with PostgreSQL, hashed dependencies, secret scan, request-body bounds, leased jobs and cleanup command | Deployed monitoring, scheduled cleanup, incident drills and launch approval; no production merchant deployment or hosted schedule was performed |
| JSON release compatibility | New readers accept old report JSON; inference metadata is validated on publication | Old strict readers reject enriched JSON. Coordinate web/worker release; keep a compatible reader or explicitly back up/transform derived fields before approved rollback. No SQL migration does not imply rollback safety |
| Source | Original archive preserved; verified code published only to a review branch in the requested repository | Original Emergent source remains unavailable; repository currently public and visibility was not changed |

No outreach execution or external write is enabled. Public research does not prove ownership, grant OAuth scopes or establish marketing consent. All live-provider and production gates remain explicit, with no fabricated substitute data.
