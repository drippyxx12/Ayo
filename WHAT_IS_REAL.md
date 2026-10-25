# What exists vs what does not — Ayo Alpha (Oct 2026)

## Implemented and locally tested
- Real account sign-up, password-based login, private session and logout.
- Shopify authorization-code flow to an actual merchant store (needs external Shopify app client ID/secret and HTTPS configuration).
- Signed OAuth callback verification, expiring offline access token encryption and refresh.
- GraphQL reads of real products/order amounts and a merchant-scoped persistence layer.
- A real-data-only dashboard. Empty until store data is imported.
- Deterministic Ask Ayo answers using connected merchant records — no fictional numbers.
- Signed webhook verification and uninstall deletion.
- Development-only SQLite database; production configuration requires PostgreSQL.
- Automated tests with mocked Shopify network: run under `pytest`, see tests folder.

## Not connected or validated
- No actual external merchant or Shopify development store installed the app in this run; network Shopify install behavior is **untested live**.
- No public domain, TLS certificate, or production PostgreSQL yet.
- No verified live Shopify app credentials, public distribution approval or protected customer data approval.
- No external AI model or live actions. Ask Ayo currently uses deterministic data-driven answers.
- No production-grade identity lifecycle (email verification, password reset, MFA), rate limiting, security review, data policy/compliance process, data reconciliation, queue, background incremental sync.
- No evidence of real customer traction or external income.
- Not integrated into the older Lovable UI or Emergent repository; those projects were deliberately left unchanged.

## Next dependency for a truly usable hosted alpha
1. Register/configure the Ayo app in the Shopify Dev Dashboard and get client credentials via the appropriate secure environment settings (never commit them or send them through chat).
2. Acquire a domain + HTTPS web hosting and managed PostgreSQL; configure env.
3. Deploy this server behind HTTPS with migrations, password/email protections and data privacy safeguards.
4. Install the app on a Shopify development store, complete a live order/product sync and reconcile against Shopify admin values.
5. Address Shopify approval and data protection requirements before inviting outside merchants.
