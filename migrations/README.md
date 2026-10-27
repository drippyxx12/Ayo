# Explicit database migrations

Run with Python 3.12 and the installed locked requirements. Schema creation never runs when models or database configuration are imported.

For a **new empty database**, configure `DATABASE_URL` securely and run:

```bash
python -m alembic upgrade head
python -m alembic check
```

Use PostgreSQL in persistent environments. `postgres://` and `postgresql://` URLs are normalized to the installed psycopg driver; SQLite remains for development/tests. The optional local Docker Compose file requires a developer-supplied `POSTGRES_PASSWORD`, binds only localhost port 15432, and keeps its volume. Running a local test database does not provision a hosted service.

## Existing original alpha database

Do not run `upgrade head` against unstamped existing tables or stamp an unknown schema. Back up the DB and verify that its `users`, `shops` and `snapshots` tables match revision `0001_alpha` exactly (column types, indexes, foreign keys). Confirm there is no `alembic_version` or additional active migration history. After reviewing that exact original baseline, explicitly adopt it with:

```bash
python -m alembic stamp 0001_alpha
python -m alembic upgrade head
python -m alembic check
```

The platform migration preserves users, encrypted provider fields and snapshots; widens minor-unit monetary storage to BIGINT; adds identity/workspace/research/lead/audit tables; and grants the earliest 500 existing distinct user records their ordered founding slots. Existing users' business country is **not guessed**; they must choose Nigeria/Ghana in onboarding before a business workspace can be created. Existing email addresses must already be normalized; review and resolve colliding identities before adoption. No production schema is adopted or migrated automatically.

## Rollback and validation

Test `upgrade head → downgrade 0001_alpha → upgrade head` on a disposable restored database before production. Downgrading removes the new feature data and should only occur after explicit backup/review. It cannot safely narrow financial values larger than a PostgreSQL INTEGER; PostgreSQL rejects that downgrade rather than truncating. SQLite downgrade requires SQLite 3.35 or newer for native user-column removal.

`tests/test_migrations.py` verifies fresh round trips, baseline-user/provider/snapshot preservation, model parity, large monetary values and constraints. Set `AYO_TEST_POSTGRES_URL` to a disposable PostgreSQL test database to run the same tests with isolated schemas; without it, PostgreSQL checks are explicitly skipped. PostgreSQL tests never erase the configured database's public schema.

## Merchant platform additions

`0005_merchant` adds owner-provided profiles and internal tasks. `0006_lead_crm` adds prospect lists, notes and review-only drafts. Its unique `(business_id,id)` lead index avoids copying populated SQLite parent tables, preserving lead events and task references. `0007_assistant` adds private conversations/messages and versioned read-tool snapshots with composite tenant/user foreign keys. These are internal workspace records; they do not authorize provider actions, outreach or payments. Downgrade removes these new records. The explicit upgrade/downgrade/parity and populated-parent preservation tests run on SQLite and PostgreSQL.
