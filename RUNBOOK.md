# Local operation and remaining external setup

The platform is **PARTIALLY COMPLETE**: service and HTTP journeys run with controlled fixtures, including PostgreSQL; no real public-business/provider journey or production deployment is verified.

## Database and process setup

Use Python 3.12. Create a virtualenv and install `pip install --require-hashes -r requirements.lock`. Store a durable session signing secret and Fernet encryption key in secure runtime configuration using the names in `.env.example`. Do not commit actual environment files.

Set `DATABASE_URL` to PostgreSQL for durable operation. The optional local-only `docker compose up -d postgres` requires `POSTGRES_PASSWORD` set securely and exposes PostgreSQL on loopback port 15432. Production requires an independently approved managed database, backups, TLS and restore testing; none is provisioned here.

Run `python -m alembic upgrade head`, then `uvicorn ayo.app:app --host 127.0.0.1 --port 8000`. Application imports do not migrate development or production databases. For an existing original alpha database, back it up and explicitly stamp `0001_alpha` only after verifying its exact original schema; then upgrade. Never stamp an unknown database or run automatic schema adoption. Migration regression tests preserve legacy credentials, stores and monetary snapshots.

Run `python -m ayo.worker` separately for durable public research jobs. Jobs require the same database and encryption key as the web process. `--once` handles at most one job. Expired worker leases can be retried up to three attempts; failures are persisted without invented reports. The browser status page has a refresh link and reports actual job state.

## Provider setup — requires owner permission

- **Research:** configure `FIRECRAWL_API_KEY` only after a permitted provider account and spend are authorized. Set `AYO_PROVIDER_SPEND_AUTHORIZED=1` only with that authorization. Hosted fetching additionally requires reviewed robots/terms/source policies, verified provider egress/redirect controls, `AYO_RESEARCH_EGRESS_POLICY=provider_managed_verified`, and exact source hosts in `AYO_RESEARCH_APPROVED_HOSTS`. The flag records an operator acceptance decision; it does not independently prove network controls. Ayo never locally fetches arbitrary submitted URLs. Without these checks, fetch fails closed.
- **AI:** set `AYO_AI_PROVIDER` to `gemini` or `claude`, the appropriate server-only API key, and an available evaluated model ID (`GEMINI_MODEL` or `ANTHROPIC_MODEL`). Calls require the same explicit spend authorization. Model output is validated against tenant-scoped evidence; no model has an execution tool or write credential. No automatic vendor fallback occurs.
- **Account email:** verify a sender/domain, configure `RESEND_API_KEY` and `MAIL_FROM`, then authorize transactional delivery with `AYO_MAIL_SEND_AUTHORIZED=1`. Run `python -m ayo.worker --mail`; `--once --mail` handles one message. The encrypted outbox uses provider idempotency keys. Until configured, the UI says queued, never sent. Verification/reset links are not displayed to visitors. Mail credentials are not outreach permission.
- **Shopify:** separately configure Ayo app credentials, HTTPS origin, approved read scopes and a consenting development-store install. Public research grants none of these. The old Shopify code is preserved under Connections, strengthened with server-consumed state and signed-payload identity checks, but official SDK/privacy/durable sync and live reconciliation gates remain.
- **Payments:** NG/GH country/payment-state contracts exist; there is no live Paystack/Flutterwave connection, collection or settlement receipt. Pending bank transfers/MoMo are not counted as collected cash.

## Evidence and access

Anonymous reports expire after 24 hours; claim capabilities expire after 30 minutes and are hashed at rest and browser-session-bound. A verified account can claim once into its authorized business. Saving research does not prove site ownership. A new user receives a private business membership; all report, lead and AI queries derive that membership server-side.

The first 500 distinct normalized customer accounts receive persistent all-feature grants, including future releases. Grants survive additional business creation and have no automatic expiry. Email verification, abuse prevention, third-party charges and provider authorization remain independent. Anti-abuse and legitimate-account policy still need launch review; later-user prices are not applied automatically.

Lead discovery stores only sourced organization candidates, with source snippets/times and deduplication. Qualification records merchant review. Contacted/replied/converted require separate matching evidence; this build exposes no send endpoint, no automatic messaging and no invented conversions.

## Verification

Run `AYO_TEST_POSTGRES_URL=<disposable-local-postgres-url> python -m pytest -q`. PostgreSQL tests create isolated schemas. The normal suite uses offline vendor fixtures and cannot prove real research, model quality, delivery or merchant integration. See `PROGRESS.md`, `FEATURE_STATUS.md` and `docs/LATEST_REPOSITORY_AUDIT.md` for exact evidence and outstanding gates. No deployment or paid call is authorized by running tests.
