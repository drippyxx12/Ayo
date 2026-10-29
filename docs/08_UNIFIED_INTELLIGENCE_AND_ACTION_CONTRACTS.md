# Ayo — unified intelligence and governed action contracts

## Experience model

**ONE AYO**, many behind-the-scenes, deterministic skills. Skill capabilities may include commerce analytics, merchandise/catalog, inventory, customer retention, campaigns/advertising, messaging, attribution, finance and growth—but each skill runs ONLY if implemented and required provider permissions/data are available.

Ayo chooses a supported read tool; it does not manufacture a new executable tool by improvising a prompt. Example: a merchant asks why sales fell. Ayo requests authoritative order/product/time-window facts; attributes a trend only where evidence supports it; proposes a concrete action; and hands off a reviewed Work draft.

## Recommended architecture


authenticated_merchant → tenant_scoped_ayo_orchestrator → skill_registry/read_tools → deterministic business metrics with provenance → explanation/opportunities → action draft → server_policy_engine → explicit merchant approval → provider_adapter/write → provider receipt → outcome tracking/memory.

No direct LLM-to-Shopify credentials or raw unscoped SQL. Every tool checks tenant and business ID on the server; structured outputs include business_id, provider, scope, source_timestamp, import_run_id, completeness, units/currency, calculation_version, and limitations. Prefer domain adapters to provider-specific data shaping in React.

## Skill registry contract (conceptual; adapt to audited code)

- `Skill`: stable ID, domain, data_requirements, provider_capabilities, permission scopes, allowed read/write operations, availability state, cost/risk class, policy requirements, metrics/outcome definitions, version and owner.
- `ToolCall`: tool ID and version, authenticated user/business, validated parameters, idempotency/correlation key and trace ID; for read tools enforce bounds/time windows and redacted output.
- `ToolResult`: typed facts and source IDs, freshness and completeness, confidence where relevant; error/limitation instead of dummy figures.
- `Intent`: a constrained merchant request, with a machine-checkable authorized business target; “do it” resolves only against a current explicit proposal.
- `PolicyDecision`: `ALLOWED | APPROVAL_REQUIRED | BLOCKED`, reason, policy version, data freshness, provider scope and risk assessment; **server is authority**.
- `Approval`: merchant identity, exact frozen action parameters/diff, affected product(s), expiry and audit metadata. Must be invalidated if target scope/values change.
- `Execution`: queued → attempted → verified provider success/failure; rate-limit backoff, webhook reconciliation, idempotency, safe rollback/compensating action if supported.
- `Measurement`: distinct timestamps/metric definitions, baseline and comparison data; don't claim incremental revenue from correlation alone.

## First allowed real write (recommended)

**Merchant-approved Shopify catalog listing improvement**:
1. Get current product title/description via official authorized Shopify API.
2. Generate suggested copy clearly marked as a *proposal* based on real product facts; don't add invented specs or claims.
3. Display exact before/after, affected product, optional SEO fields, and required `write_products` scope. If scope missing, present reauthorization, not a fake execute button.
4. Evaluate limits/permissions; merchant explicitly approves the **exact frozen diff**; recheck product version and scope.
5. Enqueue one idempotent write through server adapter, log provider response; compare Shopify read-after-write, handle conflicts and retries safely.
6. Record versioned prior content and support controlled rollback/undo with merchant approval and API permission.
7. Report “Listing updated at [time]” only after verification. Product views/conversion increase remain unknown until later measured.

## Cross-integration growth plan (not active by declaration)

1. **Shopify**: first supported commerce source and eventually validated write operations.
2. **WooCommerce and other e-commerce platforms**: new domain adapters when demand justifies testing/security burden.
3. **Paystack / Flutterwave**: payments where merchant authorizes and API terms allow; reconcile order vs actual payment/fees without double counting.
4. **WhatsApp Business**: opt-in communication only, template approval and message delivery receipts.
5. **Advertising and marketing**: Meta/Google Ads, Klaviyo or other approved sources with separate scopes and trust boundaries.
6. **Custom site SDK/API**: secure webhooks, signed events, merchant data export and OAuth/service credentials; tenant isolation by default.
7. **Optional Ayo Storefront**: separately evaluated future website creation path for e-commerce sellers, not V1 dependency.

## Operational security rules

No autonomous sends/spends/discounts by default; least-privilege provider scopes; irreversible high-cost actions remain human-gated; clear limits; account and provider token revocation; encryption at rest; webhooks verified; sensitive merchant data minimization; retained decision and execution audit evidence. A real-looking animation is not proof of a real background worker. Display state from jobs only.
