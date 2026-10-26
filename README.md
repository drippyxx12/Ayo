# Ayo — Africa-first commerce intelligence

**Status: PARTIALLY COMPLETE.** Ayo is one commerce intelligence application for Nigeria and Ghana. It preserves the supplied FastAPI/SQLAlchemy/Jinja source; it is not a framework rewrite. A landing page is not its completion criterion.

**Current stopping point:** [MEMORY.md](MEMORY.md) records the latest milestone, preview, verified work, blockers and next action. Read it first when returning to the project; it is updated at each handoff.

Read [PRODUCT_VISION.md](PRODUCT_VISION.md) for the complete product and [ROADMAP.md](ROADMAP.md) for the path beyond the MVP. They consolidate the original architecture package and distinguish required capabilities, current verification, incomplete work and proposed expansion. Gemini must participate in the first functional business-research milestone; the initial worker now persists evidence before Gemini synthesis, while real provider acceptance remains blocked.

The current code implements persistent identity and workspaces, source-backed report contracts, a research worker, private merchant screens, sourced leads, and guarded Gemini/Claude-compatible analysis. The full HTTP journey passes against SQLite and real local PostgreSQL with explicit offline provider fixtures. **Real public-business research, model quality, email delivery, Shopify and payments have not been verified live.** No production deployment or charged provider call has been performed.

## What is implemented

- Public search-first name/URL/social/marketplace intake, explicit candidate selection, and a clearly unverified no-website owner-description path. No Shopify requirement.
- A fixed-host Firecrawl adapter with server-only keys, explicit spend and source-policy gates, bounded hosted crawl requests, robots compliance requests, source hashes/excerpts/timestamps, public product/price and linked-channel observations, and validated citations. No arbitrary URL fetching from the web process.
- Durable encrypted research jobs commit a hidden source checkpoint before Gemini synthesis. Validated public analysis is persisted with citations/model/policy/usage; missing or rejected AI yields an explicitly partial report. Leases fence stale publication and crash recovery reuses evidence without recrawling.
- PostgreSQL-ready relational models and three explicit Alembic migrations. Existing alpha account/store/snapshot data is preserved by tested upgrade paths.
- Hashed database sessions, server revocation, persisted throttling, normalized accounts, business memberships, email verification/reset capabilities, encrypted transactional outbox and recovery that revokes old sessions.
- Browser-bound, expiring, single-use report claims into verified accounts; private dashboard, reports, opportunities, activity, lead records and workspace switching.
- Real-provider organization candidate contracts, evidence and domain/profile-aware deduplication. Qualification records a review; contacted/replied/converted require separate evidence. There is no send endpoint or invented outcome.
- Interchangeable Gemini/Claude HTTP adapters, structured output validation, tenant-scoped excerpts, literal source checks, bounded requests and no execution tools or write credentials.
- Permanent, transactional first-500 distinct-user grants covering all available and future features. Extra workspaces do not consume slots; no automatic billing or expiry.
- Optional preserved Shopify alpha under Connections, with server-consumed OAuth state, signed webhook identity binding, encrypted rotation, private server-held answers and currency-aware money validation. Payment-state contracts distinguish pending MoMo/transfers from settled cash.
- Premium editorial UI: Syne headings, DM Sans UI, DM Mono metrics, self-hosted fonts, responsive forms and evidence views.

## Run locally

Use Python 3.12 and a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install --require-hashes -r requirements.lock
```

Create a private, ignored `.env` from `.env.example` without overwriting an existing configuration. Set a generated durable `SESSION_SECRET` and Fernet `TOKEN_ENCRYPTION_KEY` securely. Set `DATABASE_URL` to PostgreSQL for durable multi-worker operation; SQLite is supported for local development/tests only. Load the environment in your shell, then:

```sh
python -m alembic upgrade head
uvicorn ayo.app:app --host 127.0.0.1 --port 8000
```

Run the research worker separately with the same database and encryption key:

```sh
python -m ayo.worker
```

Provider execution stays unavailable with the example defaults. Setup, policy gates, encrypted mail delivery, retention cleanup, legacy migration procedure and operational limitations are in [RUNBOOK.md](RUNBOOK.md). Do not use a production database, enable spend or deploy without approval.

## Verify

```sh
python -m pytest -q
python -m ruff check .
python -m pip_audit --require-hashes -r requirements.lock
sh scripts/check-secrets.sh
```

Set `AYO_TEST_POSTGRES_URL` to a disposable local PostgreSQL database to include migration, concurrent founding-allocation and full HTTP journey checks. Tests use isolated schemas. GitHub CI provisions its own test PostgreSQL service.

The latest integrated suite has **583 passing tests** with PostgreSQL enabled. Browser checks cover 390/768/1440px search → committed evidence → offline Gemini synthesis → cited report → signup → verification-token fixture → private save → reopen → sourced lead discovery/qualification. These are fixture-backed application tests, not live business or merchant evidence.

## Delivery records

- [PLAN.md](PLAN.md): ordered milestones and acceptance gates.
- [PROGRESS.md](PROGRESS.md): test/browser/GitHub receipts and blockers.
- [FEATURE_STATUS.md](FEATURE_STATUS.md): code-versus-live status per capability.
- [RISK_REGISTER.md](RISK_REGISTER.md): remaining release gates.
- [Latest repository audit](docs/LATEST_REPOSITORY_AUDIT.md): original source and architecture audit.

The original ZIP and its SHA-256/file manifest are preserved. Older architecture documents contain historical requirements and unimplemented targets; the current status files and latest founder instructions take precedence.

M2 provider setup: [controlled live-test runbook](docs/M2_LIVE_TEST_RUNBOOK.md). Run `python scripts/check-provider-readiness.py --mode prepare --scope provider` for a safe offline configuration check. It never verifies live credentials or authorizes spending. Durable reservations are conservative authorization debits, not measured provider invoices.

Secure preparation: [exact environment/model/setup instructions](docs/M2_SECURE_SETUP.md), [draft founder review](config/m2-live-test-review.json) and [.env.m2-prepare.example](.env.m2-prepare.example). Keep both provider/mail switches 0 while preparing; only the reviewed configuration shape is checked, with no calls or implicit authorization.

The founder-authorized workspace credentials are loaded without displaying values using `.venv/bin/python scripts/with-private-runtime.py`. The owner-only file is outside Git; managed/deployment secret bindings remain separate. Spending/mail stay disabled and data/source/budget approvals remain pending.
