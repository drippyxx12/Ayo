> **25 Oct search-first supersession:** Customer acquisition starts from **public business/site SEARCH**, actual evidence, a cited mini-report, then account creation and private claimed report; Shopify is optional after account. Businesses with no website use permitted public profiles or labeled owner-supplied facts. `docs/25–28` override older signup-first/Shopify-first sequences. Research and model integrations are **not yet implemented**. First 500 distinct customer users receive all released features free, without Ayo feature paywalls.

# Ayo V1 — product requirements (24 Oct 2026)
**Stage:** approved founder direction + specifically marked recommendations, engineering requirements; NOT a delivery claim.

## A. The customer-facing product

A completely new customer:
1. **Before signup**, searches their business by name/market or submits an accessible website, public social or marketplace link; Ayo presents real candidate matches, requires selection and conducts permitted public research.
2. Receives a cited **mini-report**, honest limitations and a few organization-level potential lead previews **only if actual evidence/provider results exist**; account signup and Shopify are not required for this preview. Businesses without websites get permitted business lookup or labeled owner-provided starting facts.
3. Chooses **Create your free Ayo account**, completes verified signup and securely claims the specific preview into a private business workspace; optional Shopify integration lives in Connections. Only after choosing to connect Shopify does the merchant authorize the actual Ayo app against their own store. Ayo validates shop identity, requested scopes, callback and ownership, handles expiring offline tokens and safely persists integration state.
4. Sees distinct stages: connecting, authorized, importing, connected/fresh, partial/stale, permission denied, needs reconnection, and removed. Show the last successful sync time and completeness.
5. Sees actual orders, correctly defined commerce metrics, products, available inventory (where permitted), real period comparisons, and issues inferred ONLY from imported facts; no revenue/profit figure can be invented.
6. Opens **Ayo**, a unified intelligence interface; asks “What changed this week?” or “What needs attention?”; receives answers with actual time-window, currency, data source and support, or a candid “not enough data.”
7. Views an evidence-grounded **Work** item: issue, recommendation, affected records, predicted upside explicitly marked an estimate, risk, connection/scope needs and operational policy. Ayo may prepare a draft without executing.
8. Reviews and explicitly approves an action. For the first V1 write, proposed product-listing optimization, Ayo should present an exact **before → after** product description/title diff (with change limits). Only if Shopify's required write scope was approved does a background job attempt the update. Its receipt records actual provider success/failure and time; rollback from captured previous values where supported.
9. Returns to see actual action history, source freshness and any observable outcomes. An executed edit is NOT proof of increased conversion; impact requires later evidence and honest attribution limits.
10. Can disconnect a store and request account/data deletion; retention/deletion workflows must comply with Shopify and other applicable obligations.

## B. Navigation and information architecture

- **Home**: merchant pulse and Ayo's most useful current observation; real data, pending decisions, work completed, and clear truth about source freshness. Avoid generic four-KPI card farms.
- **Ayo**: one intelligent control surface coordinating domain capabilities; contextual conversation, evidence and recommended work, not generic hallucinating chat.
- **Work**: recommended action → draft → permission evaluation → merchant approval → provider execution → verified result → later measurement. Actual records, not a storyboard.
- **Grow**: capabilities such as product conversion, merchandising, sales opportunities, customer retention and advertising are surfaced based on **available provider data and authorized skill maturity**. Unconnected/undeveloped skills do not pretend to run.
- **Business**: connected catalog, store health, orders, inventory, goals, metrics, source freshness and inspectable memory; tenant-scoped.
- **Connections & Settings**: true provider state, requested permissions, owner policy, privacy controls, account management, billing/free-access terms and connection removal.

## C. V1 capability availability matrix

| Capability | Target for customer V1 | Gate |
|---|---|---|
| Accounts, businesses, roles and sessions | **Functional** | Production auth, tenant-isolation, email verification |
| Shopify OAuth and secure tokens | **Functional** | Real developer-store installation, compliance |
| Orders, product catalog and inventory reads | **Functional where permitted** | Durable sync, GraphQL scopes, protected data handling |
| Sales and product-performance analysis | **Functional** | Metric definitions, reconciliation, provenance |
| Unified Ask Ayo | **Functional on actual store facts** | Deterministic read tools, data safety, optional LLM orchestrator |
| Opportunity detection and work drafts | **Functional** | Only grounded, tenant-scoped facts; permission checks |
| First approved real action (product copy optimization proposed) | **Functional before external V1 launch** | Shopify write scope, before/after diff, explicit approval, audit, idempotency, rollback process |
| Merchant memories, learning and outcomes | **Lightweight verified version** | Track facts and honest measurement only |
| WhatsApp/Meta/Google/WooCommerce/payments | **Planned, not promised at V1** | Integration, compliance and real customer demand |
| Ayo Storefront builder | **Discovery only** | No founder commitment, separate product and large engineering cost |
| Physical point-of-sale/retail operations | **Out of scope** | Explicit founder direction |

## D. Trust and merchant acceptance

A release fails acceptance if: a new user sees made-up sales; a fake connection is labelled connected; one merchant can query another's data; an order result is wrong without a completeness flag; action approval silently triggers another write; action executes without credentials or consent; provider success is assumed from request dispatch; missing capabilities appear operational; Shopify uninstall leaves inappropriate access or data; unsupported currency is rendered as 2-decimal fixed point without currency rules; first-500 free terms are inconsistent or hidden; or a staging build is called production-ready on mock tests alone.

## E. Founder decisions still open, nonblocking for foundation work

- Which three business actions will matter most for merchants? Propose catalog optimization, sales diagnosis and stock-risk analysis pending direct customer research.
- How autonomous should Ayo be? Proposed safe initial default: ask before acting, with future explicit opt-in limits.
- First executable action choice: product listing optimization recommended because it fits Shopify without customer-level marketing consent, subject to merchant testing and least-privilege review.
- Free 500 access: **count by distinct legitimate user account (CONFIRMED)**, not business; all available features free for those users without feature gates. Lifetime promise legal wording and later-user pricing remain unresolved.
- Whether and when to build Ayo Storefront and custom-site connectors.

Do not block engineering source audit, auth, tenant isolation and genuine Shopify read permissions on these future decisions.
