# Shopify connection baseline — verified in ChatGPT, not inside Ayo

**Checked:** 24 October 2026. Data from the user's newly connected Shopify plugin, queried read-only through `get_shop_info`, `list_orders`, `search_products`, and `run_analytics_query`.

## Actual connected account
- Store name: `My Store 3`
- Shop domain: `yyjydd-4y.myshopify.com`
- Store market: Poland
- Currency: PLN
- Timezone label returned: CEST
- Plan: trial
- First read-only data check: **zero products**, **zero orders**; sales analytics covering the prior 30 days: orders = 0, gross sales = 0, discounts = 0, net sales = 0, taxes = 0, total sales = 0.

The current Shopify connection is a **ChatGPT user-level app connector**, not Ayo's own authorized Shopify app. It does not provide Ayo with an install token, credentials, permanent authorization, hosted callback, customer data permission, or a production verification. Do not copy credentials from the connector or treat its read-only results as proof that Ayo's OAuth implementation works.

The store is a practical *empty-state reference*: Ayo should show correct authorized shop identity when installed, no products/orders, and zero or unavailable sales based on completeness, freshness and source. Once the proper Ayo developer app and verified install are set up, compare Ayo's figures for the same period with Shopify's analytics, which currently report zeros. Later test nonzero transactions through authorized sandbox/development-store testing; do not create products or orders in the connected account without the merchant's explicit instruction.

**Platform limitation:** Shopify returned the required customer-facing notice: `Plan: trial — you'll need to upgrade before you can start selling and unlock full features`. This may constrain live selling and testing until trial restrictions are resolved.

## Updated engineering guidance from official Shopify docs, August/October 2026
Shopify released **official framework-agnostic Python package `shopifyapp` v1.0** (Aug 26, 2026) for token exchange, webhook signature/request verification and GraphQL calls with automatic retry handling. Evaluate adopting it inside FastAPI rather than maintaining bespoke low-level OAuth helpers. Source: https://shopify.dev/changelog/posts/build-shopify-apps-in-php-and-python-with-new-official-packages

New public apps created on or after April 1, 2026 are required to use expiring offline access tokens for GraphQL Admin API use. Source: https://shopify.dev/changelog/posts/expiring-offline-access-tokens-required-for-public-apps-april-1-2026

Shopify security update Oct 20, 2026 emphasizes vulnerability scanning, cross-shop isolation, authenticated routes, verified webhooks and short-lived tokens. Source: https://shopify.dev/changelog/blog/securing-your-app-together

## Meaningful next verifications
1. Recover canonical Emergent Ayo source and connect its authorized GitHub repository.
2. Register developer Ayo app, configure official least-privilege scopes, expiring offline token authentication, HTTPS staging and compliance topics.
3. Install Ayo app separately into an approved developer/test Shopify store and validate live shop identity and data queries.
4. Exercise a controlled nonempty data scenario only in a permitted sandbox or development store; compare order metrics to Shopify's UI/analytics.
5. Keep current merchant's empty account intact. No source data has been written by this analysis.
