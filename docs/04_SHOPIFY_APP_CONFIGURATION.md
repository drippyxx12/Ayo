# Shopify developer configuration and test checklist

1. Create/confirm a Shopify developer account and an eligible **development shop** owned by the founder. Only test on a store you control or have permission to access.
2. Choose the correct app distribution and installation mode for independent Ayo merchants. The Alpha code uses a **standalone authorization code flow** (`/shopify/connect` → `/shopify/callback`), not an embedded App Bridge session flow. Confirm this matches the app created in Shopify's Dev Dashboard.
3. Configure the exact HTTPS callback `https://<staging-domain>/shopify/callback` and verified application URL. Do not configure an unknown redirect or insecure HTTP for merchant testing.
4. Keep `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SESSION_SECRET`, `TOKEN_ENCRYPTION_KEY`, database credentials and webhooks in private managed secret storage. Do not commit them or paste them in chat.
5. Start with least-privilege `read_products` and permitted `read_orders`; validate exact required scopes on GraphQL fields, and whether protected customer data review/access is necessary. Do not request marketing messaging rights in first release.
6. Implement expiring offline access tokens (`expiring=1` in authorization-code token exchange), protected rotation/retry and time-based refresh; confirm API version availability at build time.
7. Implement mandatory compliance webhook endpoints and verify `customers/data_request`, `customers/redact` and `shop/redact` topics according to current Shopify guidance. `app/uninstalled` handling is also critical; use idempotency + audit to handle retries.
8. Confirm sync correctness using GraphQL cursor pagination and `extensions.cost` throttling info. For larger catalogs, evaluate bulk operations and incremental events. Document order retention/60-day access constraints where applicable.
9. Before inviting a merchant: privacy policy, Terms, data retention/deletion, per-merchant access restrictions, incident handling, secret rotation, backups, logging and a real install/uninstall test. Never claim Shopify app review approvals that have not occurred.
10. Explicit smoke evidence to capture **without tokens or PII**: signed-in Ayo workspace; redirected Shopify authorization; exact Shopify shop domain and granted scopes; successful authorized shop query; product/order reconciliation for chosen period; last sync; failure state; clean disconnect/uninstall.

**Docs:**
- https://shopify.dev/docs/apps/build/authentication-authorization
- https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens
- https://shopify.dev/docs/apps/build/authentication-authorization/migrate-to-expiring-offline-access-tokens
- https://shopify.dev/docs/apps/build/compliance/privacy-law-compliance
- https://shopify.dev/docs/api/admin-graphql/latest/queries/products
