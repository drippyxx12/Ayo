# 27 — Pre-signup evidence, privacy, provenance and report-claim security

**Status:** architecture specification; no private customer onboarding, anonymous research storage or active claims are implemented yet.

## Data layers
1. **Anonymous research query:** opaque correlation ID, input kind (name, URL, public social link, no website), selected market and optional city. Capture minimal metadata; no required identity. Browser/IP anti-abuse data segregated with short retention and privacy notice.
2. **Candidate entity:** evidence URL, provider query and display title, location hints, actual timestamps, match/ambiguity score. Candidate is PUBLIC_UNVERIFIED, not merchant-owned.
3. **Citable source document:** fetch URL, canonical URL, retrieval time, allowed-use policy, content hash, extractor version, denied/partial reason. No silent invented PDFs, screenshots or text. Scraped page text is hostile input, never trusted instructions.
4. **Evidence claim:** observed/inferred/unknown, source/document pointer, anchor/quote locator, date, confidence, constraints and language. Unsupported claims MUST be excluded. Do not infer orders, profit, customer counts, ad spend or conversion from a public website.
5. **Mini-report:** anonymous capability-scoped preview ID, expiration, visible report sections, recommended actions as unexecuted draft hypotheses, and optionally 2–3 organization-level lead previews each with citations. No personal contacts or actual outbound events in unclaimed report.
6. **Claim token:** random cryptographic high-entropy, hashed at rest, purpose=`claim_report`, scoped to a single report, one-time, short expiration, server-bound to verified new user's signup flow. Sending email alone not a domain or public site ownership proof. Never put long-lived access tokens in query analytics/referrers.
7. **Authenticated business workspace:** user ID, role/membership, claimed report source, merchant-entered preferences, optional verified site domain, saved lead shortlist, updated reports, provider connections. Enforce tenant-scoped row-level or query-level security.
8. **Merchant verification:** separate DNS/email/approved platform verification step before any site-controlled mutation or claims about business ownership. Shopify OAuth grants only approved store scopes to the connected merchant, independent of prior research.
9. **Outreach:** prospect business ID and provenance, legal basis/consent separately established, opt-out/suppression evidence, channel state, merchant-approved immutable message hash, send receipt, reply provenance, verified deal state. Never auto-message targets after a public report.

## Threat model
- **SSRF:** allow only public HTTPS URLs with no credentials, block IP literals, localhost/link-local/metadata/cloud addresses, validate DNS every redirect, prevent rebinding, enforce resolved-IP and network egress restrictions. User input normalization alone insufficient.
- **Search injection:** public HTML/social copy cannot set system instructions, override model policy or invoke tools.
- **Anonymous enumeration:** random opaque IDs and scoped capability tokens; no predictable report access; rate limit with budget. Mask candidate contact PII; honor source terms.
- **Claim replay:** atomic claim transition and ownership check, expiry test, concurrent claim conflict; claims to same report by unrelated users cannot access original private notes.
- **Wrong business:** candidate choice does not imply verification; allow explicit corrections and multiple same-name businesses.
- **Provider privacy:** vendor routing shows which providers receive customer data, retention policies, country support; honor deletion requests, log prompt/source access without storing raw sensitive text in telemetry.
- **Data access:** tenant isolation on search results enriched privately, leads, summaries, workspace notes, vector retrieval and job logs; owner cannot access another merchant by changing IDs.
- **Unauthorized outreach:** public email/contact info alone is NOT consent; policy enforces local laws, permitted channels, suppression, scopes, human approval.
- **Billing:** anonymous limited preview and founding 500 all-feature access are separate. No credit-card gate for cohort, no fabricated counter; background provider cost caps must not silently remove features.

## Retention defaults for engineering review (PROPOSED, not legally final)
- Anonymous query/session artifacts: short-lived, e.g. 24 hours; report claim tickets 30 minutes; expire tokens on claim; raw HTML source retention bounded by legal/source terms. These are **recommendations** pending product/legal review.
- Merchant-selected report can persist in tenant workspace with source citations and versioning until owner deletion/retention policy.
- Immutable audit proves who approved each real provider action; PII minimized and appropriately retained/expunged.

## Test matrix
- No account can request merchant-private Shopify data while anonymous.
- Anonymous mini-report does not show factual claims without source IDs.
- Report claim token expired/reused/cross-session or invalid business match → denied.
- An anonymous visitor may research a competitor but cannot claim verified ownership automatically.
- Shopify remains optional through all paths.
- Search unavailable, website blocked, ambiguous search, no website, and incomplete report are truthful working states.
- Business ownership, user signup and outbound marketing permission are *independent* state changes.
