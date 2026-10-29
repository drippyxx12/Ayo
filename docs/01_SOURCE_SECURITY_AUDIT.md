# Alpha starter: source and security audit
**Reviewed:** 24 October 2026, original `ayo_real_mvp` files in `ayo_codex_build_starter.zip`. This is static/code-level review, not a penetration test.

## Exact code found
- Python FastAPI / SQLAlchemy in one `ayo/app.py` module (~26 KB), HTML templates, CSS, SQLite default, Dockerfile and five pytest tests.
- User registration / password hashing / login/logout and signed cookie session.
- One Shopify store per user, unique domain lock, OAuth callback with state+HMAC+timestamp validation, encrypted token pair and refresh logic.
- Shopify GraphQL `shop`, paginated `products`, `orders`; synchronous on-request data import capped at 10 pages × 75 records each.
- `Snapshot` contains recent paid-order value and a 25-product preview; local Ask Ayo uses question keywords, not LLM orchestration.
- Four webhook topics are routed with HMAC checks; deletion runs for `app/uninstalled` / `shop/redact`; customer request/redact topics are acknowledged without an auditable processing workflow.
- No real developer-store connection, public deployment, approval or live merchant evidence.

## Baseline test result (local)
Run `cd ayo_real_mvp && python -m pytest -q` → **5 passed** on 24 Oct 2026. These tests mock all external Shopify HTTP calls and use an isolated SQLite file; they are not a real store or multi-worker test. In this environment plain `pytest -q` failed importing `ayo`; `python -m pytest` succeeds. Add `pyproject.toml`/pytest packaging before CI.

## P0 — protect users and data before onboarding
1. **Auth lifecycle:** no email verification, reset, rate limiting, revocation or account deletion; server-side session store and CSRF strategy needed. Password hashing uses scrypt but no migration or credential abuse control. Signed cookie permits no immediate device revocation without changing session secret.
2. **Database:** `Base.metadata.create_all(engine)` on import, not migration-controlled; SQLite default; `Shop.user_id UNIQUE` prevents multiple shops per merchant and cannot represent shared team workspaces. Define `Business`, `Membership`, `ShopConnection` with tenant keys and robust data constraints.
3. **Metrics:** order value assumes two fractional currency digits (`int(total*100)`), incorrect for some currencies; the order query sorts by CREATED_AT but period filtering uses processedAt; potentially mixed chronological semantics. Refunds, partially paid/refunded, tax, shipping, exchange rates, timezones and cancellations need explicit documented definitions and fixtures. Label currentTotalPriceSet as current order total, NOT accounting revenue/cash.
4. **Data completeness:** pagination stops after 750 records. The current dashboard has an `orders_limited` flag, but analytics may still look authoritative. The 60-day data window and product totals are not fully derived from Shopify filters and may omit stores with >750 recent orders/products.
5. **Sync lifecycle:** HTTP request holds Shopify requests and DB transaction; no durable queue, cursor checkpoints, retry/backoff on throttling, GraphQL API cost accounting, concurrent refresh locking or circuit breaker. Test DB transaction failure after refresh and cancel.
6. **Privacy:** Shopify compliance webhooks for data requests and customer deletion currently return `{'ok':true}` without auditable processing. Although the alpha intentionally avoids customer identities, design and validate mandatory compliance handling and data retention before any merchant pilot. Verify requirements with official docs and conduct legal review.
7. **Webhook:** no delivery ID deduplication, event-time verification and concurrency controls; webhook topic URI uses `/shopify/webhooks/{topic:path}`. Validate and register actual Shopify supported topics and prescribed subscription configuration. Handle uninstall while sync is running.
8. **OAuth:** recheck HMAC canonicalization and duplicate URL query keys against Shopify's current docs, replay semantics and broken/missing session cookies in different browsers; integration tests should cover real URL encoding, redirect hosts and revoked grant. Don't assume current unit `oauth_valid` function is correct because mock test is green.
9. **Token lifecycle:** expiring offline tokens request is currently `expiring=1`; Shopify token refresh rotates refresh tokens, and parallel refresh may lose credentials without locks. Verify refresh responses and 401/403 reauth branches using latest documentation.
10. **Logging & compliance:** no structured audit log, integration failure history, retention ledger, application monitoring, backups or user-facing permission explanations.
11. **Tenant & role tests:** `must_user` and user_id-filtered queries are helpful, but shared role/team model missing. Current test `test_users_cannot_take_over_other_stores` includes an unrelated `user.id == status_code` lookup that is not a valid authorization assertion; replace with explicit two-client isolation tests.

## P1 — after release safety
12. `/ask` uses lexical keyword matching; may return incorrect category to unrelated prompts. Rewrite as deterministic read-tool registry first, then add scoped LLM orchestration behind policy and evaluation; do not improvise financial formulas in LLM text.
13. Frontend is basic Jinja, not the desired premium, responsive product. Preserve operational backend contracts and design carefully. Test on mobile without compromising accessibility.
14. No real merchant instrumented analytics, business memory, saved opportunity/work objects or permissions for action execution. Plan schemas before attempting those features.

## Evidence rules
- **Code exists** ≠ works against Shopify live API.
- **Five mocked tests pass** ≠ tenant security, data correctness or production readiness proven.
- **Shopify installed** ≠ Shopify API scopes, protected data and app review approved.
- **Successful read** ≠ full/fresh/compliant data.

## Official references
- Access tokens: https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens
- Expiring offline tokens: https://shopify.dev/docs/apps/build/authentication-authorization/migrate-to-expiring-offline-access-tokens
- Privacy webhooks: https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance
- Authentication: https://shopify.dev/docs/apps/build/authentication-authorization
- GraphQL products: https://shopify.dev/docs/api/admin-graphql/latest/queries/products
