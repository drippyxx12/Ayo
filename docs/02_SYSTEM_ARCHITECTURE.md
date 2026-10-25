> **Founder architecture update:** Single Ayo coordinating a versioned, permission-aware skills registry and deterministic merchant-scoped provider adapters; dynamic skills are not freely generated LLM powers. Shopify first and no physical retail. `08_UNIFIED_INTELLIGENCE_AND_ACTION_CONTRACTS.md` defines the intended unified orchestration and first approved product-edit action. Any statement below limiting provider writes to “later release” refers to the **technical read-only milestone**, not a complete customer V1.

# Proposed Ayo engineering architecture
**No production deployment authorized.** This describes a target, not implemented components.

## Components
- **Frontend**: existing server-rendered FastAPI pages as stable baseline; optionally migrate incrementally to React/Next.js after original Emergent repository audit. A route and API map prevents a blind rewrite.
- **API**: FastAPI modules `auth`, `organizations`, `integrations/shopify`, `sync`, `commerce`, `intelligence`, `work`, `audit`.
- **Database**: managed PostgreSQL with Alembic migrations. Money in explicit decimal/currency values rather than universal hundredths. All queries tenant-scoped.
- **Worker**: durable job queue with retry/backoff, idempotency, cursor checkpoints and failure log. Use supported hosting with persistent processing for Shopify full/incremental sync.
- **Secrets**: long-lived encryption key, separate session signing, Shopify app secret, provider tokens encrypted at rest, rotation policy, never browser-exposed.
- **Observability**: structured non-PII logs, action/job audit, error metrics, alerting and backup/restore checks. PostHog for opt-in product events, not merchant financial/customer records by default.

## Data model (minimum proposed)
- `users(id, email, verified_at, hashed_password, created_at, disabled_at)`
- `businesses(id, legal_country, display_name, home_currency, timezone, created_at)`
- `memberships(user_id, business_id, role, invitation_status)` — role checks on every endpoint.
- `connections(id, business_id, provider, shop_domain, state, encrypted_credentials, granted_scopes, last_verified_at, expires_at)`.
- `sync_runs(id, business_id, connection_id, start_at, completed_at, status, cursor, counts, error_code)`.
- `shop_orders(business_id, provider_order_id, currency, created_at, processed_at, financial_status, amounts..., updated_at)` with stable provider IDs and relevant deletion semantics.
- `shop_products(business_id, provider_product_id, title, status, inventory_total, updated_at)` plus variant/inventory location if scope permits.
- `metric_snapshots(business_id, period_start, period_end, metric_name, value, currency, definition_version, source_run_id, computed_at, completeness)`.
- `intelligence_events(business_id, type, evidence_json, observed_at, confidence, state)`.
- `action_drafts(business_id, operator, proposal, evidence_ids, status, approval_policy, expected_effect, created_by, updated_at)`.
- `approvals(action_id, approver_user_id, decision, policy_version, approved_at)`.
- `action_attempts(action_id, provider, idempotency_key, outcome, provider_event_id, timestamps)`.
- `audit_events(business_id, actor_id, action, result, safe_metadata, recorded_at)`.
- `privacy_requests(business_id, provider, topic, provider_request_id, status, due_at, handling_evidence)`.

Unique indexes for connection provider+shop-domain, business+provider-order-id, event idempotency; foreign keys and cascading deletion carefully designed per retention policy. Tenant filtering is mandatory for all relational queries and worker jobs, including cleanup and QA.

## Contract: external connector lifecycle
`unconnected → connecting → authorized → syncing → connected` and precise failure or reauthorization states. The initial display must remain unconnected until a verified API read, not merely OAuth token receipt. Track `last_successful_sync`, `last_attempt`, data age, scope limitations and imported row count. Reinstall and duplicate webhooks must not create orphaned businesses.

## Contract: grounded Ayo intelligence
Read-only tools such as `getOrdersTrend(tenant, period)`, `getProductInventory(tenant)`, `comparePeriods(tenant)`, `getImportHealth(tenant)`. Return structured values with provenance, completeness, report currency and timezone. Deterministic metric code produces numbers; any LLM explains and selects tools, never invents numbers or accesses another tenant. No customer message/send tools in Release 1.

## Contract: governed execution (later release)
`detected → draft → waiting_approval → approved → executing → completed → measuring → measured | failed | cancelled`.
A server-side policy engine checks capabilities, permissions, merchant limits, data freshness and consent before *and* during execution. Action UI shows exact effects and recipient count. Approval generates short-lived authorization; external writes use idempotency keys. “Approved” is not “Executed”; “Executed” is not “Measured”.

## Shopify security boundary
Merchant is redirected to Shopify authorization; server validates HMAC/state/timestamp and exact shop domain. Token exchange and GraphQL calls occur on server. Encrypt tokens, support expiring offline refresh and concurrent workers safely. Follow Shopify's protected customer data and app review requirements. Never ask merchants for Shopify account passwords.
