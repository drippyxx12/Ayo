# Ayo — complete product vision

Version: 2026-10-25. Owner: Ayo founder. Delivery status: **PARTIALLY COMPLETE; live core workflow BLOCKED**. This document defines the intended product; it does not certify that the capabilities below work. [ROADMAP.md](ROADMAP.md) defines dependencies and acceptance; [FEATURE_STATUS.md](FEATURE_STATUS.md) and [PROGRESS.md](PROGRESS.md) record implementation evidence.

## 1. The finished product

Ayo is one unified, Africa-first AI commerce intelligence and operations platform. It helps merchants discover opportunities, understand their businesses, find relevant customers and business buyers, decide what to do, and perform authorized work with verifiable results. Nigeria and Ghana are the initial operating markets. The architecture supports additional countries through reviewed country capabilities, without creating separate products.

The complete experience follows **Observe → Verify evidence → Understand → Prioritize → Propose → Authorize → Act → Verify outcome → Measure → Learn**. A merchant deals with one Ayo, while typed specialist capabilities operate behind it. Ayo retains business context and connects public research, private authorized commerce data, opportunities, plans, work and actual outcomes in a single workspace.

A landing page, visual tour, source-only scanner, generic chat, read-only store dashboard, or first working MVP cannot establish completion. Shopify is the first commerce connector, not a condition of using Ayo. Research and leads must serve website, social-led, marketplace and no-website merchants. Initial commercial scope is e-commerce; physical retail/POS is outside that initial scope.

Sources: [FOUNDER_BRIEF.md](FOUNDER_BRIEF.md), [product requirements](docs/07_AYO_V1_PRODUCT_REQUIREMENTS.md), [unified intelligence/action contracts](docs/08_UNIFIED_INTELLIGENCE_AND_ACTION_CONTRACTS.md), [Africa-first strategy](docs/18_AFRICA_FIRST_COMMERCE_STRATEGY.md), [canonical search-first journey](docs/25_SEARCH_FIRST_DISCOVERY_TO_SIGNUP_CANONICAL.md).

## 2. Source authority and recovered package

The original archive `ayo_codex_FINAL_search_first_africa_500_free_2026-10-25.zip` is preserved. Its SHA-256 is `5b8212c4bf45591a037c454f41683495193766554f9a396c4dc409311b871ae5`. For this review, its **49 original Markdown/specification/JSON files** were extracted into a separate temporary directory without overwriting working code. The review covered AGENTS, START_CODEX_HERE, FOUNDER_BRIEF, original README/build/handoff/release documents, docs 00–28 including both 25 documents, and all eight original architecture JSON contracts. The [source audit receipt](docs/evidence/product-vision-source-audit.json) inventories exact paths/hashes. Current code, migrations, tests, ADRs and verification receipts were reviewed separately.

Apply these precedence rules:

1. The latest explicit founder/user instructions govern. In particular, **Gemini must participate in the first functional business-research milestone**, with an authorized real API call before that milestone passes. Earlier language delaying AI until a later iteration is superseded.
2. The canonical 25 October search-first and first-500-user instructions supersede older signup-first, Shopify-first, business-count and paid-tier language.
3. This vision and roadmap consolidate the original package, preserving confirmed requirements and marking proposals. They do not erase original specifications or turn their examples into facts.
4. Source code plus relevant verification receipts establish implementation status. Architecture JSON, screenshots, mocks, an API credential or a deployment URL alone cannot establish a live capability.

Historical statements that GitHub was inaccessible or that the entire app is still the original alpha are dated records. The accessible foundation is now the evolved FastAPI/SQLAlchemy/Jinja app in `drippyxx12/Ayo`. Historical Emergent and builder projects remain unavailable and have not been consolidated. A framework rewrite is not part of this vision.

## 3. Merchant experiences from discovery to operations

### New merchant, before signup

Enter a business name, website, public social profile or marketplace link, with optional market/city. See actual candidate matches and explicitly resolve ambiguity. Receive permitted source-backed research and a useful **Gemini-assisted** mini-report before registration. A report identifies sources, dates, coverage, uncertainty, observations, inferences and unknowns. An optional preview contains at most three genuinely sourced organization prospects; no personal-contact export or outbound action occurs here.

No accessible online presence is a valid path: try permitted public listings, then accept merchant-supplied products, offer, location, goals and channels. Label those facts `OWNER_PROVIDED_UNVERIFIED`; return a starting profile and honest evidence gaps when independent research is impossible. Do not invent a website, customer base or external assessment.

### Create an account and retain the work

Register, verify email and claim the exact anonymous report with a browser-bound, expiring, one-use capability. Save it in a tenant-isolated business workspace; return after logout/restart and reopen it. Report saving proves access to a saved copy, not ownership of the researched company. Domain/business verification is separate; a workspace can remain explicitly unverified. The same user can participate in multiple authorized businesses without consuming another founding slot.

### Run the business with one Ayo

Home displays real recorded facts, source freshness, important observations, opportunities and pending decisions. Ayo answers questions, explains evidence and uncertainty, compares permitted sources, creates plans and prepares Work. Business holds offer, goals, catalog, orders, inventory and metrics when their sources are authorized. Grow contains researched prospects, qualified opportunities and available growth capabilities. Connections and Settings show actual provider status, scopes, market settings, privacy and account controls. The exact routes may evolve; the experience must cover **Home / Ayo / Work / Grow / Business**, alongside Research, Leads, Connections, Settings and Help.

### Develop customers and sales

Define offer, ideal business audience, geography, sector, campaign purpose and resource limits. Discover actual organizations, deduplicate, research fit and inspect citations. Qualify and shortlist; draft editable, evidence-grounded pitches. Contact only after applicable permission/legal checks, provider setup, sender identity, suppression and exact merchant approval. Track confirmed sends, replies, opportunities and sales as distinct events. Merchant-entered results remain labeled `merchant_reported` until independently reconciled.

### Connect and operate with permission

Optionally install Ayo's Shopify app, authorize least-privilege scopes and inspect actual import progress, coverage and failures. Connect other supported sources independently. Ask Ayo about public evidence and authorized merchant facts without collapsing their trust boundaries. Review a proposed action's exact effects, risk, target, source freshness, cost and permissions. Approve the frozen proposal; the server rechecks policy, performs an idempotent operation, verifies the provider result and offers controlled undo where supported. Later impact measurement remains distinct from successful execution.

### Return, monitor and improve

Opt into bounded refresh/monitoring, receive evidence-grounded changes and pending decisions, inspect prior versions, correct outdated facts, revisit work and compare actual outcomes. Retain inspectable business memory with provenance and retention controls. Revoke integrations, stop jobs, export permitted workspace data and request deletion with accurate provider/backup limitations.

## 4. Required capability inventory

The IDs below remain stable across the roadmap/status board. They express the complete core platform, not only its MVP. A capability must not disappear from completion criteria because its provider or implementation is difficult.

| ID | Capability required in the complete platform | Required behavior and proof |
| --- | --- | --- |
| C01 | Identity, businesses and team access | Registration, verification, recovery, revocable sessions, secure account lifecycle, role-scoped memberships/invitations, multi-workspace access and tenant isolation across HTTP, jobs, storage, retrieval and exports. Privileged-account security and abuse controls must be reviewed. |
| C02 | Search-first business identification | Name/URL/public profile/marketplace inputs, market/city disambiguation, correction, permitted no-site lookup and labeled owner facts; useful research before login, optional Shopify. |
| C03 | Safe evidence acquisition | Licensed/permitted search, controlled public fetch, per-hop network safety, robots/terms/opt-outs, bounded queue, deadlines, byte/page/cost budgets, partial/error states, immutable redacted snapshots and provenance. Social restrictions remain enforced. |
| C04 | Gemini-assisted intelligence reports | Gemini in the first functional research slice; typed source-bound observations, product/offer/channel analysis, positioning, trust/buyer-path and discoverability findings, competitors, prioritized gaps/opportunities and next steps. Every factual statement has support; inference and unknowns remain visible. |
| C05 | Research workspace and ownership | Secure anonymous-to-account claim, saved reports, source inspection, history/versioning, correction/refresh, permitted report comparison and export; explicit proof before identifying a researched site as merchant-controlled. |
| C06 | One Ayo and specialist tools | Intent routing to a real versioned registry, deterministic read tools, bounded plans, evidence retrieval, capability availability, provider routing/usage records and safe responses to missing/stale/conflicting data. Models cannot create privileges or executable skills. |
| C07 | Persistent merchant application | Responsive Home/Ayo/Work/Grow/Business and supporting screens driven by real persisted data, real jobs, activity, recommendations, filters and truthful empty/stale/partial/unavailable states. |
| C08 | Lead research and qualification | Business audience/campaign definitions, genuine organization discovery, source freshness, identity resolution/deduplication, relevance reasons/disqualifiers, review, shortlist/notes and correction. Fit is not buyer intent or a purchase probability. |
| C09 | Lead-to-sale operations | Sourced editable pitches, approvals, permission records, suppression/opt-out, authorized channel adapters, delivery/reply reconciliation, opportunities/deals, merchant-reported vs provider-verified outcomes and attribution limits. No invented contact or sale. |
| C10 | Optional commerce connectivity | Shopify first: independent OAuth, verified connection states, encrypted expiring credentials, revocation, durable full/incremental sync, products/orders/variants/inventory where permitted, idempotent events, privacy processing and reconciliation. Extensible commerce/custom-site adapter contract. |
| C11 | Business metrics and commercial diagnosis | Deterministic versioned order/payment/refund/discount/tax/shipping definitions, catalog/merchandising and inventory insights, period comparisons, coverage/freshness and appropriate stock-risk analysis. Costs/ad spend/attribution are required before profit/ROAS claims. |
| C12 | Nigeria/Ghana commerce and payments | Explicit business market; NGN/GHS, local IANA timezones, social/WhatsApp buyer paths and delivery information; verified regional payment reconciliation for supported methods. Separate attempted/pending/authorized/successful/settled/refunded/reversed. No double counting or unsupported mixed-currency sums. |
| C13 | Governed Work and execution | Persistent proposals/diffs, role and provider checks, immutable expiring approvals, risk/budget/consent policy, durable jobs, idempotency, conflict detection, verified receipts, failure/uncertainty recovery, cancellation and reviewed undo. First substantive customer release includes at least one real approved external operation. |
| C14 | Monitoring, memory and outcomes | Merchant-approved recurring research/sync, source/price/product change evidence, alerts and review queues, goals/preferences, inspectable provenance-based memory and measured before/after outcomes without unsupported causal claims. Any autonomy is opt-in and policy-bounded. |
| C15 | Founding-user entitlements | Persistent atomic first-500 distinct legitimate-user grants, no second slot per workspace, every released/future feature free, transparent protective limits and independent provider charges. Eligibility abuse review and reinstatement/deletion audit must preserve awarded rights. |
| C16 | Privacy, security and governance | Separate public/owner/private/derived/AI/receipt classifications; business ownership distinct from provider consent and outreach consent; minimized PII, export/deletion/retention, provider DPAs and jurisdiction review, secret rotation, audit integrity, privacy requests and incident response. |
| C17 | Production operation and assurance | Explicit PostgreSQL migrations, separate environments, stable secrets, API+worker operation, bounded queues/recovery, redacted correlated logs, metrics/traces, alerting, backups/restore, release/rollback, support and meaningful automated plus independent live verification. |
| C18 | Ayo design and accessibility | Consistent editorial identity, responsive mobile/desktop, keyboard/focus/screen-reader semantics, readable evidence and decisions, slower-network resilience and honest progress. Quality applies throughout merchant workflows, not just acquisition. |

Sources: docs [07](docs/07_AYO_V1_PRODUCT_REQUIREMENTS.md), [08](docs/08_UNIFIED_INTELLIGENCE_AND_ACTION_CONTRACTS.md), [11](docs/11_WEBSITE_INTELLIGENCE_PRODUCT_AND_UX.md)–[16](docs/16_SKILL_REGISTRY_AND_SECURITY_CONTROLS.md), [18](docs/18_AFRICA_FIRST_COMMERCE_STRATEGY.md)–[23](docs/23_IMPLEMENTATION_SLICES_AND_VERIFY_FIRST.md), [25](docs/25_SEARCH_FIRST_DISCOVERY_TO_SIGNUP_CANONICAL.md)–[28](docs/28_SEARCH_FIRST_CODEX_ENGINEERING_SEQUENCE.md), and the [original skill registry](architecture/skill_registry.json).

## 5. AI architecture and evidence contract

The reference system remains an incremental modular monolith: responsive web UI → HTTPS/authenticated API/BFF → scoped command/query domain services → research/commerce/intelligence/Work/provider adapters → durable workers and PostgreSQL. Versioned typed API contracts, stable error codes, pagination, queued-command status and correlation IDs must remain consistent with UI behavior. Source snapshots may use private bounded-retention object storage; queue/cache, secrets management and observability services are chosen as operational needs justify them. Domain entities include businesses/memberships/ownership claims, sources/evidence/reports, connections/sync/entities/metrics, lead campaigns/permissions/outcomes, tools/plans/Work/approvals/attempts, founding grants and privacy/audit records. Existing database entities are a starting subset, not proof this full architecture is implemented. [Layered architecture](docs/12_ARCHITECTURE_BLUEPRINT_AND_TRUST_BOUNDARIES.md), [data/API contracts](docs/14_DATA_MODEL_AND_API_CONTRACTS.md).

Gemini is the primary initial research/reasoning provider under the latest instruction. Claude is an optional compatible adapter for evaluated planning workloads. Model IDs must be explicitly configured and available; personal chat subscriptions are not API credentials. A provider change cannot silently transmit private merchant data to another vendor.

Keep business search, content retrieval, evidence storage, reasoning and action execution as distinct services. Google Search grounding and URL Context are possible evaluated Gemini tools, not substitutes for Ayo's source licensing, safe acquisition, retained citations or business-identity checks. URL Context does not imply a whole-site crawl. The current Firecrawl acquisition adapter is an implementation choice, not a permanent product dependency.

Every material report claim carries source IDs/URL, capture time, excerpt or structured locator, source classification, extraction/model version, coverage and uncertainty. Deterministic services produce money metrics. Gemini interprets actual evidence and proposes next steps; unsupported observations are rejected. Inaccessible sources, no matches, conflicting facts, unavailable models and exhausted budgets remain explicit outcomes. A rules-only extraction/report is useful infrastructure but does **not** pass the Gemini-assisted milestone.

The completed orchestrator must select only registered tools with typed inputs/outputs, server-derived business scope, roles, required permissions/data, version, freshness, cost/risk budget, timeout and audit policy. Research/model processes receive no write credentials. Low-trust page content, prompts and model outputs never approve actions or override policy. Retrieval/memory, including any future vector index, remains tenant- and purpose-scoped.

Evaluate at least the original proposed 20 diverse Nigeria/Ghana cases on matching, citations, unsupported claims, product/competitor accuracy, lead fit, no-site/blocked-social behavior, locale readability, injection resistance, latency and total provider cost. Use independently checked sources and blind review where comparing models; record failures and thresholds before release. [AI contract](docs/26_GEMINI_CLAUDE_ROUTING_AND_PROVIDER_ARCHITECTURE.md).

## 6. Integrations and broader capability areas

Named vendors below have different commitment levels. Supporting a functional area does not mean every candidate vendor is integrated. No candidate may be displayed as connected without actual authorization and a verified read/result.

| Area | Intended role and commitment | Dependencies / present boundary |
| --- | --- | --- |
| Gemini developer API | Required primary for the first functional research report and unified intelligence | Server key, available model, data policy, bounded authorized usage, citations and real-call evaluation. Not live verified. |
| Claude developer API | Optional adapter for evaluated planning/quality needs | Separate credential/policy/consent/budget; no silent fallback. Adapter exists with offline tests only. |
| Public search/content providers | Required functional acquisition layer; vendor replaceable | Permitted source coverage, terms/robots, egress/redirect proof, retention and cost limits. Firecrawl adapter is fixture-tested. |
| Transactional email | Required verification/recovery delivery; Resend is current adapter | Verified sender, server credentials, delivery permission, retries/idempotency and actual delivery. Not marketing authorization. |
| Shopify | Committed first optional commerce connector and candidate first Work action | Ayo app, own OAuth grant/scopes, official contract/SDK assessment, durable sync/privacy and real store tests. Existing alpha remains incomplete. |
| WooCommerce / other commerce platforms | Proposed subsequent commerce adapters; custom-site integration is intended later connectivity | Merchant demand/priority decision, own auth, normalized data, signed events, privacy and full connector acceptance. Not implemented. |
| Paystack / Flutterwave / Ghana-specific provider | Regional payment integration candidates; Hubtel needs vendor research | Verify actual NG/GH/country/channel availability, sandbox authorization, signatures, async states, fees/refunds/settlement and order deduplication. No payment adapter implemented. |
| WhatsApp Business / approved email channels | Intended permissioned communication capability; exact vendor/rollout selected after review | Official sender, applicable opt-in/templates/legal basis, suppression/opt-out, frozen approval, provider receipts/replies. No sender implemented. |
| Meta/Google Ads and marketing sources such as Klaviyo | Proposed growth domains and sources, not active skills | Separate OAuth/scopes, ad-spend/attribution data, explicit budgets and approvals. No campaigns, spend or ROAS available by declaration. |
| Custom website SDK/API, analytics and signed events | Later platform-independent merchant connectivity | Ownership proof, scoped service/OAuth credentials, signed events, replay protection and domain normalization. Not implemented. |
| PostgreSQL, durable workers, optional Redis/object store/KMS and monitoring | Required infrastructure capabilities; specific services selected by evidence | Persistent operation, security, cost approval, restore/rollback and observability. Local DB/jobs exist; production environment is absent. |
| Product analytics/support | Intended real funnel/capability/cost/support measurement; PostHog/Sentry are candidates | Privacy-safe opt-in where applicable, no raw merchant data or fake events. No complete production operation evidenced. |

The original vision also names customer retention, campaigns/advertising, attribution, finance, merchandising, inventory and customer-support/communication assistance as possible specialist domains. Catalog/inventory and accurate financial interpretation are covered in C10–C11; compliant sales communication is C09. **Customer-retention programs, paid-campaign operation, advanced attribution/finance and broader support automation remain proposed expansion domains (E01–E04 in ROADMAP)**. Their first use cases, providers and rollout require explicit product selection and evidence. Keep them visible; do not claim their absence means the whole long-term vision has shipped. Existing-customer retention data and public prospect data must remain separate.

Possible **Ayo Storefront** creation is an uncommitted product-discovery track, not a substitute for intelligence or a dependency of the committed platform. Native mobile apps and new countries such as Kenya/South Africa are later discovery/expansion, not promised current support. Physical retail scope changes require a founder decision. [Provider/skill contracts](docs/08_UNIFIED_INTELLIGENCE_AND_ACTION_CONTRACTS.md), [country profiles](architecture/country_capabilities.json).

## 7. Nigeria/Ghana behavior and design

Nigeria defaults to NGN and `Africa/Lagos`; Ghana to GHS and `Africa/Accra`. Business/country/provider support is explicitly selected and verified as appropriate, never inferred from ethnicity, name, IP or presumed language. Support public social/WhatsApp purchase paths without reading private DMs. Recommendations consider observed delivery/returns/payment information, product clarity, local buyer paths and mobile usability. Tone/language preferences are merchant-controlled.

Payment/source amounts retain their currency and provenance. Pending bank transfer or MoMo is not received/settled cash. Order value, paid amount, revenue, fees, refunds, settlements and profit remain distinct. No GHS+NGN aggregate without authorized dated FX and preserved originals. Local policy packs require versioning and jurisdiction/provider review before enabling actions.

Visual identity: black **#0A0A0A**, beige **#EDE5D8**, warm white **#F8F5EF**, charcoal **#252525**. **Syne headings, DM Sans UI, DM Mono metrics**, self-hosted with licenses. Use generous whitespace, deliberate typography and clear hierarchy; avoid generic KPI-card farms, decorative AI activity and misleading success states. Mobile, tablet, desktop, keyboard and screen-reader paths must work across reports, actions and errors, including slower connections.

## 8. Founding 500: binding all-feature entitlement

The first **500 distinct legitimate customer user accounts**, not businesses/stores/installations, receive **all available Ayo features free, including those released later**. Persist grants server-side using immutable unique user/slot records and atomic allocation. A user's extra authorized workspaces do not consume or remove slots. No Ayo premium feature tiers, operator add-ons, required credit card, automatic expiry/downgrade or later billing for this cohort. Do not advertise a lifetime legal term that has not been approved.

Technical availability, country support, role, consent, provider scope and transparent anti-abuse protections remain independent. Disclosed external vendor fees need separate opt-in; the founding entitlement does not authorize spending. Legitimate-account eligibility, fraud review, deactivation/reinstatement and legal terms require reviewed policy; email uniqueness alone does not prove a distinct legitimate customer. Later-user prices remain undecided and cannot be applied automatically. [Founding policy](docs/09_LAUNCH_AND_FREE_500_POLICY.md), [enforcement contract](docs/24_FREE_FIRST_500_USER_ENTITLEMENT_CONTRACT.md).

## 9. Current verified baseline and incomplete work

At the latest implementation checkpoint, **256 automated tests passed with real local PostgreSQL enabled, zero skipped**, plus an upstream deprecation warning. They verify controlled fixtures, not real provider outcomes. Browser workflow evidence at 390/768/1440px covers committed sources → offline Gemini fixture analysis → report → registration → verification-token fixture → secure claim/reopen → lead discovery/qualification, workspace isolation and local deletion. Local container/security/dependency checks have receipts in PROGRESS. The public-Gemini implementation is published as GitHub commit `a5a2fd78ddeebdc83bba2cfb7f0080111701d6b1`, with both source-code CI runs passing; PROGRESS records the receipts.

Implemented components include explicit migrations; persistent identity/sessions/memberships/throttling; encrypted mail outbox; report and claim isolation; durable research jobs; bounded public-research adapter and deterministic single-page report; product/channel extraction; stored-source merchant screens; lead discovery/deduplication/qualification contracts; Gemini synthesis in the initial report worker after committed hidden evidence, plus compatible private-analysis adapters; user-based founding allocation; currency/market contracts; strengthened preserved Shopify alpha; local retention/account removal.

The protected Vercel preview is **intake plus a labeled screenshot walkthrough**. It forces no storage/provider execution and disables accounts/private routes. It is not a hosted full merchant application or a live research proof. [Preview receipt](docs/evidence/protected-preview.json), [initial offline browser evidence](docs/evidence/offline-browser-workflow.json), [public Gemini fixture journey](docs/evidence/public-gemini-browser-workflow.json).

Significant implementation remains: full multi-source/multi-page analysis, competitors and verification; persistence of owner facts; domain-control proof; team-invitation lifecycle; complete skill router and deterministic commerce tools; normalized durable commerce sync; payment adapters; Work/policy/approvals/execution; campaign/draft/consent/suppression and provider send/reply/deal reconciliation; recurring monitoring, richer business memory, exports and outcome measurement; complete privacy/operational control plane. Existing alpha Shopify storage remains user-keyed and is not yet the full business-scoped multi-connection architecture. Simple limits and token caps are not a complete per-tenant spend ledger. Current audit rows are not a tamper-evident operational audit system.

Live verification is blocked by missing secure research/Gemini/mail configuration and permissions, approved source/egress policies and spending limits, production PostgreSQL/worker/secrets and operations readiness, Ayo-specific commerce/provider permissions, and independent security/privacy/pilot reviews. No real NG/GH research report, Gemini response, delivered registration mail, discovered live lead, approved merchant write, reply or sale has been verified by Ayo. Architecture documents and provider adapters do not close those gaps.

## 10. Completion and change control

The first real working milestone must prove **anonymous real NG/GH business research → permitted retained evidence → sourced Gemini-assisted report → real registration/email verification → secure save → logout/login/reopen → genuine relevant sourced leads**, without mandatory Shopify. Reproducing it with mocks does not pass the live gate.

The first substantive customer release additionally proves useful authorized commerce reads and at least one genuinely approved, idempotent, provider-verified operation, plus operational/privacy readiness. The proposed initial action is catalog-copy improvement, subject to product/permission selection. That release still does not complete C01–C18.

The platform may be called finished only when every **required** C01–C18 acceptance gate in ROADMAP has passed, the NG/GH workflows and supported integrations are independently verified, no release-critical security/privacy/reliability issue remains, and the release owner reviews the evidence. Proposed expansion tracks must be explicitly resolved or separately scheduled with founder acceptance; they cannot be silently removed to justify a completion claim. New countries, vendors or scope additions receive versioned roadmap changes, not invented launch promises.

Each acceptance receipt names the code commit, environment, source/record/job IDs, model/provider/version, permissions, checks and results, reviewer, limitations and residual risks, with secrets/PII excluded. Independent verification means source/provider reconciliation plus a reviewer who did not merely accept the generating model's statements. A screenshot, dispatch/HTTP 202, mock result or green unit suite alone is insufficient.

Until these conditions hold, report **PARTIALLY COMPLETE**, with separate locally verified, partial, planned and blocked capabilities. Update this vision when the founder changes scope; update ROADMAP, FEATURE_STATUS and PROGRESS together. Never relabel the MVP as the full product.
