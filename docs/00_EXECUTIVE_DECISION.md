> **Founder alignment revision 24 Oct 2026:** This memo predates direct founder clarification. The founder chose **e-commerce only**, a **unified Ayo** with dynamic specialist skills, **Shopify as first provider**, **all available features free for first 500 distinct customer USERS, not businesses, with no premium feature tiers** and a comprehensive, genuinely functional customer V1; the Nigerian website-builder idea is optional and later. Read `../FOUNDER_BRIEF.md` and `07_AYO_V1_PRODUCT_REQUIREMENTS.md` before treating the older “narrow read-only wedge” as the full V1. Read-only integration remains a critical **engineering proof**, but commercial V1 must also contain at least one verified approved external action. Autonomy level and first action are proposed defaults, not yet founder-confirmed.

# Ayo real merchant SaaS — product decision memo
**Prepared:** 24 October 2026  
**Status:** approved baseline for engineering planning; some choices still need merchant/user validation.  
**The current ZIP is an alpha starter, not a customer-ready SaaS.**

## Explicit customer promise
1. A real merchant creates an Ayo account, verifies their email, and gets a private business workspace.
2. They connect their own Shopify store through Shopify's official app authorization, not by sharing a password or API token.
3. Ayo imports their authorized data and shows **their own** real orders, catalog, inventory availability and accurate, defined metrics — or an honest loading/error/permission state.
4. Ayo answers what changed, why, and what they can do next using deterministic read tools on **their** data. Missing information is never invented.
5. As the integration foundation becomes reliable, Ayo coordinates verified specialist capabilities, creates evidence-backed work drafts, enforces merchant policy, requests approval and completes at least one genuine external action **before full customer V1 launch**. It records provider verification and measures later outcomes without guessing attribution.

There must be **no pre-populated fictional dashboard in a real merchant account**. A separate, clearly labeled sample workspace is optional for sales demonstrations only.

## Engineering milestones versus first complete customer release
**Technical proof A — real merchant connection:** Verified multi-tenant identity, official Shopify authorization, reliable data synchronization, honest metric reconciliation and grounded Ayo questions. This is a **technical prototype**, not the entire customer V1.  
**Engineering milestone B — intelligence and Work:** Unified Ayo coordination, deterministic domain skills, evidence-based prioritized opportunities, merchant policies and frozen approval-ready action drafts.  
**First substantial customer V1 — permitted external work:** All safe and verified milestones above **plus one genuinely authorized, user-approved, externally verified action** (proposed: catalog listing copy edit), complete audit/undo where possible, and later evidence-grounded outcome tracking. Additional skills/providers launch only when actually connected and implemented.

Shopify data is not sufficient to calculate ROAS, net profit, customer consent or attributed campaign conversions. Never label such numbers as calculated without explicit and suitable data sources. ROI/paid order amount does not automatically equal net revenue.

## Product user journeys
**New merchant:** Ayo landing → sign up → verify email → name business / select market/currency/timezone → Connections → Connect Shopify → Shopify consent screen → callback → background import → confirmation of shop identity → accurate Home.

**Returning merchant:** Secure login → Ayo Home with last successful sync/time/coverage → revenue/order/product pulse (with metric definitions) → drill into data → Ask Ayo → view supporting data → optional draft recommendation.

**Failed install:** Return to a precise, non-leaking explanation of missing scopes/invalid HMAC/token expiry. No phantom “Connected”. Resume or restart safely.

**Disconnected:** Revoke integration where possible, delete/de-identify data according to retention and applicable requirements; display unconnected empty state, not old store metrics.

## Product navigation
Primary: **Home / Ayo / Work / Grow / Business**. Secondary: Connections / Settings / Help. Not all surfaces need all capabilities in the first build: disabled ones must explain exactly what would unlock them. A polished marketing homepage cannot be mistaken for a functioning merchant interface.

## Design principles
Ayo Black #0A0A0A, Beige #EDE5D8, Warm White #F8F5EF, Charcoal #252525. Syne (display), DM Sans (UI), DM Mono (numbers). Premium editorial layout, generous whitespace, carefully measured typography; no default shadcn “card farm,” rainbow success pills, AI-glow decoration or misleading animations.

## Out of scope for the initial technical proof and not promised in first customer V1
Unapproved autonomous WhatsApp/email outreach, unconnected Meta Ads actions, payment processing, live customer PII analysis without protected-data permission, a fictitious catalog of always-active operators, guaranteed profit numbers, customer attribution without evidence, native mobile applications, physical retail operations, the full storefront builder, or arbitrary provider integrations. A **single governed and verifiable product edit is targeted for the full customer V1**; this does not authorize other writes. These exclusions describe sequencing, not limits on Ayo's future vision.

## Milestone that changes status from code to reality
A merchant signs up using verified email, authorizes an Ayo Shopify development app, the server confirms shop identity, background sync completes, an Ayo metric reconciles with Shopify for a known timezone/period/currency, a relevant question returns accurate evidence, and disconnect + privacy handling are verified. After security/compliance sign-off, repeat with an invited merchant.
