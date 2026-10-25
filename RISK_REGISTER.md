# Development risk register — 25 October 2026

Code review and local tests only. **NOT TESTED LIVE** against Shopify, public crawl/search, models, messaging or merchant production data.

| Priority | Boundary | Observation and remaining gate |
| --- | --- | --- |
| P0 | Identity | Signed cookie sessions have no server-side revocation; email verification, recovery, throttling and deletion are missing. No production onboarding. |
| P0 | OAuth | Cookie-contained state is not server-consumed, so captured cookies can replay pending authorization. Duplicate query keys, canonicalization, concurrent refresh and official SDK evaluation remain. |
| P0 | Webhooks | Raw-body HMAC does not authenticate shop-domain/topic headers. Deletion routing needs signed payload identity binding, provider verification, idempotency and auditable privacy handling. |
| P0 | Data | `create_all()` runs on import. PostgreSQL migrations, memberships, worker race handling and robust tenant-scoped repositories are unbuilt. Current isolation is one user per store, not full team tenancy. |
| P0 | Research | No search credentials, safe crawl egress, jobs, evidence persistence or source-backed report. New intake must never fetch submitted URLs or imply a completed scan. |
| P1 | Metrics | Fixed two-decimal storage/display is unsuitable for zero/three-decimal currencies. Refunds, settlements, timezone periods, pagination coverage and currency policy need dedicated reconciliation. New validation rejects malformed and mixed-currency eligible order amounts before replacing snapshots. |
| P1 | Browser data | Existing `/ask` puts its answer in a signed, browser-readable session cookie; signatures do not encrypt it. Move private answers and sessions server-side before merchant trials. New public intake stores no research text in cookies or DB. |
| P1 | Availability | Login input bounds reduce hashing abuse but do not provide rate limiting. Request body limits, per-IP/account quotas, queues, retry and cost controls remain. |
| P1 | Ownership | Account signup and public URL submission do not verify site ownership or grant marketing consent. No automated sends or external writes are enabled. |
| P1 | Repository | GitHub repo is public, while the handoff requires a private repo. No new source push or visibility change was performed. |
| P1 | Source | Original Emergent source, license/compliance decisions and live third-party grants have not been supplied. Preserve the imported archive and track these as separate work. |

Changes in this slice close empty CSRF acceptance, stale/orphan snapshot answers, malformed order amount failures and caching of dynamic responses. They do not establish production readiness or complete identity/security milestones.
