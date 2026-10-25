# 14 — Canonical data design / API contracts

**Target PostgreSQL model** (migration names and actual DB choice require source audit). Use UUIDs in public API, authoritative server membership, indexed tenant FKs. This is a proposal to implement, not current database schema.

## Identity and organization
- `users(id, email, verified_at, password_hash, disabled_at, created_at)`
- `businesses(id, name, country, currency, timezone, created_at)`
- `memberships(user_id, business_id, role, state, joined_at)`; unique `(business_id, user_id)`; roles `owner/admin/editor/analyst`, principle of least privilege.
- `business_domain_claims(id, business_id, domain, verification_method, challenge_hash, status, verified_at, expires_at)`; no auto-claim from public search.

## Web research (public evidence separated from private commerce)
- `research_searches(id, initiated_by_user_id, search_text, locale, provider, cost_units, created_at)`
- `research_candidates(id, search_id, title, domain, url, source_ref, score, discovered_at)`
- `research_runs(id, initiator_id, business_id nullable, selected_domain, status, kind, crawl_policy_version, budget_json, scope_json, queued_at, started_at, completed_at, error_code, completeness)`; explicit ownership in initiator/tenant fields.
- `research_pages(id, run_id, canonical_url, requested_url, status_code, robots_status, fetched_at, last_modified, content_hash, content_type, metadata_json, snapshot_key nullable)`; unique per run/canonical URL, private storage retention policy.
- `research_evidence(id, run_id, page_id, extractor_version, evidence_type, excerpt_redacted, structured_value_json, observed_at, source_confidence, access_class)`.
- `research_findings(id, run_id, finding_type, claim, classification, confidence, policy_version, created_at)`
- `research_finding_sources(finding_id, evidence_id)` junction; every material claim has evidence or explicit uncertainty.
- `site_change_observations(id, business_id nullable, domain, old_run_id, new_run_id, changes_json, created_at)`.

## Private commerce and execution
- `connections(id, business_id, provider, external_account_id, state, encrypted_secret_ref, scopes, expires_at, last_verified_at, created_at)`
- `provider_events(id, connection_id, provider_event_id, event_type, received_at, processed_at, result, checksum)`
- `sync_runs(id, business_id, connection_id, cursor, status, completeness, counts_json, started_at, completed_at, error_code)`
- `products(id, business_id, connection_id, provider_id, title, description, currency, metadata_json, last_seen_at)`
- `orders(id, business_id, connection_id, provider_id, currency, processed_at, financial_status, gross, discounts, refunds, shipping, tax, total, last_seen_at)` with money as DECIMAL and explicit per-currency display policy; customer PII minimized/approval gated.
- `inventory_levels(id, business_id, connection_id, provider_inventory_id, location_id, quantity, updated_at)`
- `metric_snapshots(id, business_id, metric_id, value_decimal, currency, period_start, period_end, definition_version, source_sync_run_id, completeness, computed_at)`
- `tool_registry_versions(name, version, io_schema, data_classification, required_scopes, risk_level)`
- `intelligence_runs(id, business_id, actor_id, input_ref, purpose, tool_versions_json, status, token_cost, created_at)`
- `intelligence_claims(id, intelligence_run_id, statement, fact_class, evidence_json, confidence)`
- `work_items(id, business_id, capability, status, evidence_json, proposed_change_json, provider, external_target_id, created_at)`
- `approvals(id, work_item_id, approver_user_id, policy_version, authorization_scope, valid_until, decision_at)`
- `action_attempts(id, work_item_id, idempotency_key, status, provider_request_id, provider_result_redacted, attempted_at, confirmed_at)`
- `audit_events(id, business_id, actor_user_id, resource_type, resource_id, event_type, redacted_details, occurred_at)`; tamper-evident ledger target
- `privacy_requests(id, business_id, provider, request_type, source_request_id, deadline, state, processed_at, evidence_ref)`
- `free_access_grants(id, business_id, sequence_number, cohort_name, valid_from, terms_version, limits_json)`; unique sequence; atomic claimed slot logic, anti-abuse review

## API version `v1` (target)
Public website investigation:
- `GET /api/v1/research/search?q=...&locale=...` → candidates with `candidate_id`, `title`, `website`, source, disclaimer; search-provider key required. If no provider configured: `503 search_not_configured`, not made-up candidate domains.
- `POST /api/v1/research/runs` `{"website_url":"https://...","mode":"quick"}` or `{"candidate_id":"...","mode":"quick"}` → `202 {run_id, status, status_url, remaining_budget}`; access/terms/abuse checks server-side.
- `GET /api/v1/research/runs/{id}` → status, scope, pages visited/skipped, errors, and provenance; anonymous views use unguessable ephemeral bearer tied to request, authenticated views use tenant membership.
- `GET /api/v1/research/runs/{id}/report` → findings, evidence links, source freshness and limitations.
- `POST /api/v1/businesses/{id}/domain-claims` and `POST .../verify` → challenge state/verification; no ownership implied from search results.
- `POST /api/v1/research/runs/{id}/compare` → explicit allowed research reports (not arbitrary cross-tenant data).

Merchant private:
- `POST /api/v1/businesses` + role-protected membership APIs.
- `GET /api/v1/connections`, `POST /api/v1/shopify/install`, `GET /api/v1/shopify/callback`, `POST /api/v1/webhooks/shopify/{topic}` with HMAC/nonce and idempotency.
- `POST /api/v1/sync-runs` (authorized, 202), `GET /api/v1/commerce/sales?period=...`, `GET /api/v1/commerce/catalog`.
- `POST /api/v1/ayo/ask` → `{answer, claims:[{text,evidence_ids,classification}], warnings[], tool_runs[], data_window, currency, last_synced_at}`.
- `POST /api/v1/work/drafts` → proposal + exact before/after when writing; `POST /api/v1/work/{id}/approve` → policy decision; `GET /api/v1/work/{id}` → provider receipt.

## API failure semantics
Use standard status + stable machine codes `authentication_required`, `forbidden_tenant`, `invalid_input`, `ambiguous_domain`, `blocked_private_address`, `robots_disallowed`, `site_unavailable`, `rate_limited`, `quota_exceeded`, `search_not_configured`, `shopify_credentials_missing`, `reauthorization_required`, `sync_partial`, `permission_missing`, `provider_failure`. Clients never show a successful scan/connection/action on 202, timeout or partial response without a verified terminal status.

## Data boundaries and retention
Research snapshots: separate by run and permitted access classification, redact email/phone as required for persisted snapshots; introduce bounded TTL and delete requests. Private merchant raw source data: scoped by business, access logged, retained only as necessary under contract/permission. Provider tokens: encrypted vault reference, never business report text or LLM prompt. Use backups with deletion propagation policy. Public `research_evidence` may have source licensing conditions; retain URLs/excerpts responsibly, avoid copying whole websites into output.

## Migration approach
Create `001_identity_and_membership`, `002_research_pipeline`, `003_connections_and_sync`, `004_merchant_normalization`, `005_intelligence_work_audit`, `006_free_access` with **reversible migrations** and verification. Never turn on production migrations automatically without backup, staged dry run and explicit approval.
