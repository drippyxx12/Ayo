# 28 — Codex execution sequence: search-first core (engineering playbook)

**Founder-approved product direction 25 Oct 2026.** This sequencing overrides earlier signup-first/Shopify-first UX milestones. No implementation should be represented as live without run logs, test results and consented real integrations.

## Iteration 0: audit/architecture fit
- Run all tests and reproduce alpha. Audit stale mocks, wrong frontend home (Shopify-first), security, source ownership and Emergent original (when accessible). Set up `pre-commit`/CI, static security, dependency checks and secret detection; write explicit ADR for primary model and provider adapters.
- Exit: baseline tests and documented data-source truth. No pretend integration.

## Iteration 1: acquisition shell without invented content
- Build responsive search-first homepage: enter business name + optional location/country, URL or accessible public/social link; `No website` owner-provided alternative. Include founder identity and secondary Login link.
- Search provider absent state and zero-data reporting; no user accounts required for discovery.
- Exit: UI tested mobile/desktop; no default business; no mandatory Shopify button.

## Iteration 2: genuine public research
- SearchProvider behind API and merchant-country disambiguation. Hardened fetch service, DNS/IP egress and robots/ToS policy, bounded jobs, retries, audit + source snapshot. Real URL lookup with job status and citations.
- Exit: 2 consented/easily accessible public businesses in NG/GH researched; verify each cited fact by reading source. No unsupported claims or scraped private social accounts.

## Iteration 3: useful free mini-report and prospect preview
- Typed mini-report engine with `OBSERVED/INFERRED/UNKNOWN`, strengths, problems, opportunities, evidence and coverage. No fabricated sales metrics. Include 2–3 actual organization-level lead candidates only if live licensed discovery and source receipts exist. If missing, show honest unavailable state.
- Exit: source audit passes. Reports are visibly useful without signup; lead candidate is not sent message or real sale.

## Iteration 4: account handoff and personal Ayo workspace
- Register/verify account and business, apply first 500 USER all-feature-free slots transactionally, safely claim one preview report via scoped one-time token, independent business-site ownership verification. Private merchant membership and secure session recovery.
- Exit: token replay/expiry/foreign user/IDOR tests, report stays bound to correct account, Shopify is skippable.

## Iteration 5: unified Ayo with research and leads
- Gemini ModelProvider adapter with structured output + source verification; optional Claude adapter behind config. Unified intent router and deterministic read tools. Sourced B2B organization lead discovery, relevance and location scoring, merchant-reviewable outreach drafts, CRM statuses; no real sends without permissions.
- Exit: Nigeria/Ghana evaluation set for hallucinations/lead precision, unknowns, permissions, and cost; no manufactured lead emails.

## Iteration 6: optional Shopify + commerce and African integrations
- Independent OAuth, encrypted expiring offline tokens, GraphQL, real site/shop identity match where proven, background sync, exact source/currency/timezone and payment status, privacy law requests. Run on permitted dev stores; never require Shopify to use core site research and leads.
- Exit: zero-order shop and meaningful nonempty shop match Shopify; unconnected merchant can still use all non-Shopify capabilities.

## Iteration 7: governed execution
- Real approved action chosen on merchant availability: e.g. verified Shopify product copy diff, or consented outbound B2B pitch through provider after permissions & suppression. Immutable preview/hash, policy/consent, merchant approval, idempotency, verified receipt, staged QA and rollback where possible.
- Exit: no silent send or mutation; no 'sale' without verified evidence; one real authorized execution at a time.

## Iteration 8: first free-500 launch
- Feature entitlement resolver for 500 distinct accounts, no paid tier gates, analytics, provider-cost and abuse controls (transparent and not disguised paywall). Onboard first real consenting merchant, staged review of privacy/ToS and uptime monitoring, alerting and incident drills.
- Exit: realistic founder path E2E: `SEARCH → EVIDENCE → REPORT → SIGNUP → CLAIM → LEADS → REVIEW`, and separate authorized provider connection & action E2E. Paid billing for later users not auto-created.

## Definition of done per PR
Actual code change, tests, reproducible fixtures, URLs and evidence receipts, tenant boundary review, provider credentials required, country behavior, model version, latency/cost, privacy/deletion, mock vs live distinction, failures, rollback, and screenshots or recordings of actual UI states. A perfect mock UI is NOT an acceptable completion signal.
