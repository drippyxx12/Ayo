# Repository and architecture audit — 25 October 2026

Audit baseline: original ZIP uploaded in `drippyxx12/Ayo` at `9622fa6`, unpacked locally at `bba5048`, followed by local foundation commits `6758117` and `d6856bf`. This is a source/dataflow review with existing local-test evidence, not an external penetration test or live integration certification. New platform services are being implemented concurrently; milestone acceptance is tracked in root `PROGRESS.md` and `FEATURE_STATUS.md`.

## Sources reviewed

Read `AGENTS.md`, `START_CODEX_HERE.md`, `FOUNDER_BRIEF.md`, the root architecture/build/handoff/status documents, docs **00–28 including both 25 documents**, both existing ADRs, `architecture/REVIEW_THIS_FIRST.md`, and every available architecture JSON: provider routing, country capabilities, founding entitlements, report schema, journey, product contract, skill registry, specimen API contracts and source artifact manifest. Inspected the app/routes/models, pure intake/URL/extraction/contracts, templates/styles, tests, dependency/CI configuration, baseline evidence and risk register.

The accessible foundation is a FastAPI/SQLAlchemy/Jinja alpha. The original Emergent repository and historical builder experiments were not supplied and are not silently consolidated or replaced. Preserve the imported archive and exact hashes while extending the working code incrementally.

## Requirement precedence and contradictions

1. The latest user instruction and canonical docs/25–28 define **public search → actual evidence → sourced mini-report → verified signup → secure one-time report claim → private workspace/leads**, with Shopify optional afterward. Earlier signup-first/Shopify-first prose is historical sequencing, not the current product.
2. Founding access is the first **500 distinct customer user accounts**, all released and future features free, without automatic expiry/billing. Historical `business_id` free-grant suggestions in docs/14, “verified businesses” in docs/15, “business seats/research credits” in docs/20, and “500 business constraints” in docs/23 must not become runtime entitlement policy. Docs/09 and /24–28 plus the current user request override those lines.
3. The latest design request restores Syne headings, DM Sans UI and DM Mono metrics, superseding the immediately preceding all-Syne change. Palette and editorial identity remain unchanged.
4. JSON registries and specimen endpoints are **design contracts**, not evidence that providers/tools/routes are operational. `mini_report_schema.json` describes a target object; it is not a complete executable JSON Schema validator.
5. Older statements that GitHub was unavailable are historical. The designated repo now exists; its exact current visibility, default head and committed tree require a fresh API check before recording a remote milestone. The current user explicitly asks for verified milestone commits. Do not claim a push from local commit IDs or silently change repository visibility.
6. Current instruction prohibits deployment, provider spending, private-service access and outreach without permission. Earlier preview-link work does not authorize a production release or paid API usage in this build.

## Implemented baseline versus target platform

| Boundary | Observed baseline behavior | Missing target behavior at audit start |
| --- | --- | --- |
| Public acquisition | Bounded name/link/NG/GH/city/no-website intake; CSRF and escaped templates; honest unavailable search/fetch states | Actual business candidates, research jobs, source receipts and saved reports |
| Evidence extraction | Pure local HTML title/meta/headings/links/product-schema extraction; no network call | Verified fetch provenance, immutable storage, per-claim citations and report coverage |
| Identity | Scrypt passwords, normalized email, signup/login/logout, signed browser-cookie identity | Server-side revocation, verification/reset, persistent throttling, disabled-user lifecycle and full membership model |
| Database | `User`, one-user/one-`Shop`, one-user/one-`Snapshot`; SQLite default, `create_all()` during import | Versioned migrations, PostgreSQL acceptance, Business/Membership and auditable service schema |
| Shopify | Strict myshopify domain shape, state/HMAC/timestamp callback, encrypted expiring token pair, refresh and GraphQL reads; mocked tests | Authorized live install, supported SDK assessment, refresh locking, durable sync, privacy/event ledger and full webhook identity binding |
| Merchant answers | Deterministic keyword-based answers from current matching store/snapshot; cannot honestly be called an LLM | Unified evidence-grounded Gemini/Claude orchestration and persisted private recommendations |
| Leads/work/payments | Design manifests only; no executed sender/payment/write capability | Real organization discovery, source/fit/state persistence, provider-specific payment verification and governed execution |
| Entitlements | Static founding-500 promise/spec checks | Atomic persistent user-grant allocation and all-feature resolver |
| UI/quality | Search-first responsive intake plus original empty/real-source Shopify dashboard; locked dependencies and local CI tools | Full merchant report/leads/settings/security application and integrated live acceptance |

## Security and correctness findings

| Priority | Finding in baseline | Required engineering response |
| --- | --- | --- |
| P0 addressed locally | Original browser-held identity and OAuth pending state allowed replay without database revocation | Now uses opaque database sessions, expiring bearer digests, server consumption and password-reset revocation; live review pending |
| P0 | Schema creation on import is not a migration strategy; one-user store model does not represent shared businesses | Explicit migrations, stable Business/Membership boundaries and PostgreSQL checks |
| P0 | No permitted live research provider or safe crawl egress exists; syntax-only URL checks do not prevent DNS/redirect SSRF | Fail closed until an explicitly configured bounded provider-managed retrieval boundary or controlled pinned-IP egress is verified |
| P0 | Webhook body HMAC does not authenticate unsigned shop-domain/topic headers used by deletion routing | Bind routing to signed payload shop identity, verify expected topic/event, dedupe and audit before removing connection data |
| P0 | OAuth nonce in a signed cookie is not server-consumed; callback replay and duplicate query key/canonicalization need review | Server-consumed authorization transaction, current official provider verification and replay tests |
| P1 | Login bounds do not replace rate limiting; verification/reset/delivery absent | Persisted attempt limits, safe recovery lifecycle and actual mail-provider readiness state |
| P1 | `/ask` answers are stored in a signed but browser-readable cookie | Keep private answers/session state server-side and bound response sizes |
| P1 | Financial totals assume two decimal digits and current order totals; imported counts are capped at 750; UTC processed periods differ from query ordering | ISO-aware decimal/currency policy, explicit coverage/period definitions, refund/payment semantics and live reconciliation |
| P1 | Refresh and sync run in request workers without distributed locking/queue/checkpoints | Transaction-safe token rotation, durable jobs, retries/throttling and uninstall race tests |
| P1 | Privacy topics are acknowledged without an auditable processing/retention workflow | Provider event/privacy ledger, deletion retention rules and operational evidence |
| P1 | Type-hinted dataclasses and an `has_actual_provider_evidence` boolean are not a trusted external-evidence validator | Runtime schemas, source-ID membership checks and server-owned provenance assertions |

Foundation commits already tightened nonempty/Unicode-safe CSRF checks, login size bounds, no-store headers, stale/orphan snapshot denial and malformed/nonfinite/negative/mixed-currency order rejection. Those changes do not close the larger identity/provider/production gates above.

## Preserved working behavior and test truth

Original-source import kept the full archive; no blind framework migration or seeded merchant data was introduced. Existing tests cover mocked Shopify OAuth/read/uninstall, token ciphertext, auth/CSRF, wrong-store denial, deterministic questions, hostile URL parsing, bounded extraction and design consistency. Later foundation tests cover public no-network/no-persistence intake and selected security regressions. `BASELINE_TEST_RESULTS.md` records the 37→79 local baseline; preview-route scaffolding subsequently reached 87 local tests.

Test HTML/business fixtures are not production facts. No application-generated live source-backed report, discovered lead, model answer, merchant installation, paid transaction, sent message, reply or verified sale is evidenced at audit start. Passing SQLite/mocked tests does not prove PostgreSQL concurrency, network egress enforcement or live provider compatibility.

## Active implementation and blockers

The build proceeds through identity/database, research/evidence/claim, protected dashboard/leads, compatible AI gateways and end-to-end integration. Those areas are **in progress**, not accepted merely because an agent owns them or a file is created.

External blockers: server-side public-research API credentials and licensed policy/budget; Gemini/Claude API configuration; transactional email sender/credentials; production PostgreSQL and stable secrets; consenting Shopify developer installation and payment sandbox permissions; privacy/legal release review; original Emergent source; deployment/spend authorization. Continue independent implementation and adversarial tests, but keep live feature states unavailable until matching evidence exists.

The current delivery is **PARTIALLY COMPLETE**. Root plan/progress/status files govern the next acceptance checks; this audit is preserved as the starting-state record.
