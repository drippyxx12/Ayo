# Country capability engine — runtime localization without hard-coded stereotypes
**Machine-readable design source:** `architecture/country_capabilities.json` (proposal; no country payment connector is active). The service must validate and version the configuration before use.

## Country profile and selection
Country is an attribute of the **merchant business and location**, not the founder's passport, user language, skin color, phone dial code, or browser IP. A merchant can have businesses or stores in multiple countries. Currency and timezone belong to *each* commerce account/market. Merchant selects country explicitly during onboarding and may update it via authorized administrative settings with an audit trail. The operating system uses country rules only after platform and legal review.

### Nigeria
- First target businesses: digital D2C commerce, WhatsApp-first sellers with public web presences, e-commerce brands selling nationwide, wholesalers targeting resellers.
- Supported design concepts: `NGN`, `Africa/Lagos`, delivery-region transparency, bank transfers and associated pending states, USSD where authorized checkout supports it, cards, content clarity on mobile. No claim that any Ayo-specific payment integration is live.
- Leads: identify business buyers/resellers with public evidence, suitability, business contact route and consent/legal gate for outreach.
- Payment reconciliation: pending bank transfer does not equal received sales; separate attempted transaction, authorized, successful, settled, reversed/refunded states. Cross-source order/payment dedup key.

### Ghana
- First target businesses: e-commerce brands, boutiques, distributors and resellers, online shopkeepers using mobile money/social buying.
- `GHS`, `Africa/Accra`, MoMo availability and checkout clarity as observed. Provider may issue asynchronous completion; webhook verification is mandatory when implemented.
- Lead finding supports geography/subregion searches without assuming language/nationality or consent from website pages.
- Direct marketing rules (especially consent to send individual marketing messages) must be reviewed with Ghana DPC and provider policies before deployment.

### Kenya / South Africa
Deferred profiles to ensure architecture extensibility; mark country availability `future_research_only` until actually supported with localized integrations and regulator/provider review. Avoid silently extending Nigeria/Ghana payment assumptions.

## Pattern for country-specific modules
`MarketPack` includes ISO country/currency, timezone, merchant-language preferences, formats, **verified** provider capability matrix, payment states, logistics fields, explicit legal/compliance checks, holidays/seasonal shopping vocabulary only when user selects relevant locale or trusted campaign evidence. All capability checks call `isEnabled(country,provider,merchant,permissions)` rather than looking solely at `country`.

### Currency and reporting invariants
- Use DECIMAL or integer ISO-minor-unit-aware representation. Never use floating point for money, and never assume all currencies have two decimals.
- Preserve source amount/currency, foreign exchange source/time (where used), cost vs revenue and gross vs net metrics. Show local time windows with explicit IANA timezone and UTC storage.
- Ayo must label financial figures **not available** when a payment source is not connected, and avoid incorrectly labeling order totals as cash received. Do not show invented ROAS or profit in absence of ad-spend/cost data.

## Country-specific product test cases
1. `NG`: pending bank transfer → not counted as settled payment; can be an unpaid order with source status.
2. `GH`: MoMo authorized but final status pending → revenue field stays pending until provider-confirmed success.
3. `NG` + `GH` shops → dashboard shows split currency buckets; aggregated converted totals only with dated authorized FX source.
4. Nigeria user with Ghana business → **Ghana** rules based on verified store/merchant selection, not personal location.
5. Currency mismatch between site public prices and Shopify data → conflict warning, never silent normalization.
6. Unavailable country provider → explicitly unsupported, no fake 'connected' state.
7. Language/tone changes → user controls defaults; AI cannot infer ethnicity, tribal language or identity from name.

## Product research sources (check version at implementation time)
- Paystack supported countries (Sept 2026): https://support.paystack.com/en/articles/2130562
- Paystack official channel matrix: https://paystack.com/docs/payments/payment-channels/
- Paystack Ghana mobile money guidance: https://support.paystack.com/en/articles/2128386
- Flutterwave regional payment methods: https://flutterwave-website-v3-pilot.f4b-flutterwave.com/us/support/payment-methods/payment-channels
