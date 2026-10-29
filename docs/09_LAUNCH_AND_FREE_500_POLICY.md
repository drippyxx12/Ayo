# Ayo — founder-confirmed all-features-free policy for the first 500 users
**Last clarified by founder: 25 October 2026. Binding product requirement.**

> **ALL features are FREE for ALL of the first 500 Ayo users.** There are no paywalled capabilities, paid operator tiers, or subscription upgrades for this founding cohort. New capabilities added while they are founding users become available to them without a feature fee as soon as the capabilities actually launch and are supported in their country/provider configuration.

## Definition: count individual USERS, not businesses
- Eligibility is the **first 500 distinct legitimate customer user accounts** (not 500 merchants, stores, Shopify installations or workspaces). A user may create/manage several permitted business workspaces; those must not consume multiple founding slots or negate their entitlement.
- Assign cohort slots **server-side** in an ACID transaction, using an immutable, ordered cohort number (1–500) and unique user ID; concurrency must never over-issue. Provide replay-safe welcome flow and administrative audit trail. Prevent automated signup abuse without changing an existing user's slot silently.
- Keep actual founder entitlements separate from global pricing plans, country capability/eligibility checks, company memberships, per-workspace permissions and provider install scopes. The founding-user entitlement does not authorize them to act on someone else's business.

## Every released feature, no paywall
- Grant the founding cohort **all available Ayo features**: Website Intelligence, unified Ayo intelligence, connected-commerce analytics, leads, drafts, sales workflows, approved actions and future capabilities once those are actually implemented, supported and safely enabled.
- Do not put a founding user in a `free/basic` tier that disables skills, lead research, integrations, exports, operator tools or autonomous action functionality when those are otherwise available.
- No subscription payment, paid add-on, compulsory trial upgrade, credit card requirement or locked capability merely to use an Ayo product feature. Do not charge a founding user later by default or silently remove this entitlement.
- **Security/anti-abuse/provider capacity safeguards are still allowed** and should be applied transparently to everyone. They must not be disguised pricing tiers that deny the first 500 access to features. External providers may impose their own costs or require their own paid accounts; disclose these separately and require opt-in. The free Ayo promise is not permission to spend a merchant's money.
- Technical feature availability is independent of pricing: a not-yet-built or not-authorized integration is unavailable for *everybody*, even founding users, rather than mocked or claimed connected.

## Pending founder/legal commercial detail — do not invent it
- The founder said **all features free for the first 500 users**, but did not expressly specify a lifetime term. Codex must not set an expiry or future automatic billing and must not advertise "lifetime free" without a further explicit decision.
- Once 500 founding users are enrolled, the founder may choose pricing for later users. **The 500 founding accounts remain free and fully feature-enabled unless the founder expressly approves a new published commercial commitment that lawfully preserves promises already made.** No unilateral downgrade.
- Terms/privacy/user deletion and refunds (if any) must be reviewed before launch. Founder can later decide fair-use operational thresholds; do not silently implement feature-denying usage credits or confusing quotas.

## Engineering data contract (not implemented by this document)
See `architecture/founding_500_entitlements.json` for a machine-readable proposed contract. Implementation should use durable tables with `user_id`, `cohort_position`, `status`, `awarded_at`, entitlement history, immutable audit, transactional uniqueness; keep feature availability resolved by (feature built + country/provider supported + merchant permissions), **not** paid tier for users 1–500.

## Acceptance tests required
1. Concurrent registration at positions 499, 500 and 501 awards exactly one slot 500, no duplicate slots, and handles 501 according to the later pricing policy without disrupting account creation.
2. One founding user creating multiple businesses still uses one cohort slot and has all feature access in each authorized workspace.
3. Existing founding user gains access to newly shipped Ayo capability without billing migration/upgrade prompt.
4. Founding user is not shown a paid upgrade wall for Ayo capabilities; provider configuration/access controls remain truthful.
5. Security safeguards and third-party fee consent operate regardless of founder status; a merchant cannot execute another merchant's work.
6. Deactivation/reinstatement does not silently reassign a founder slot; log operator actions.

## Business tracking
Monitor real user signups (not store count), legitimate cohort awards, capability uptake, AI/provider costs, onboarding, retention, revenue from later users only after founder-approved pricing, provider error rates, and support. Do not fabricate traction or claim pricing was implemented based only on this file.
