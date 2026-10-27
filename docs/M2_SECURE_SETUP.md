# M2 secure preparation and founder review

**27 October recovery override:** source recovered at `/workspace/Ayo`. After the founder restored the existing credentials to owner-only private runtime storage, exactly one authorized Free-tier synthetic Gemini request returned HTTP200 / `AYO_GEMINI_OK` (19 tokens). [Actual receipt and recovery](GEMINI_CONNECTION_RECOVERY.md). Do not repeat this connectivity test. General provider/mail switches stay0; the paid-budget proposal below remains unapproved. Full public research, private inference and hosted acceptance retain their separate gates. Historical environment/presence/zero-call statements below describe earlier checkpoints.

Updated 26 October 2026. **DRAFT FOR REVIEW; no provider call, charge, deployment or merge authorized. Ayo is PARTIALLY COMPLETE.** The generated AI Studio key is not configured in Ayo merely because it exists.

## 1. Exact configuration target

Use the **managed Cloud Environment attached to this conversation**, with the existing checkout `/workspace/ayo`, branch `codex/africa-platform`. Current observation: environment spec124, running/connected, current observations, enforced HTTP policy, **no secret bindings or runtime variables**. The environment is identified by `ccarenv_b64_Y2NhcmVudl8zYTg4OTE4ZmUwY2M4MTkxYmRjZjBlYWEzMWIwM2NhNQ`. Recheck the selected environment after configuration; this identifier is a receipt, not permission to reuse a detached instance.

Open that environment's configuration controls and add **secret environment-variable bindings** `GEMINI_API_KEY` and `FIRECRAWL_API_KEY`. These managed secret controls are preferred. The connected tool can inspect readiness but cannot write vault values. The founder has now explicitly authorized reuse of the supplied keys; a private workspace fallback is configured below. Keys must stay out of Git, CI, browser output, shell history and public artifacts.

Add the nonsecret settings below as runtime variables. Apply the same bindings to the private web process and research worker; they must use the same database and encryption key. Applying settings is preparation, not permission to run provider calls. Confirm the environment's observed bindings are ready before using them; never print their values or dump the environment.

The Vercel project `ayo-development-preview` / deployment `dpl_FHxr7kjKUjVhvUAcyccB6JmptXBC` is **not this test backend**. Its wrapper disables providers, accounts and persistent storage. Do not put the keys there or in GitHub Actions: CI uses offline fixtures. No complete live merchant deployment has been provisioned. Keep the existing preview unchanged.

Provider-only offline preparation does not need transactional email. Actual evidence persistence/worker operation additionally needs an approved PostgreSQL `DATABASE_URL`, durable `SESSION_SECRET` and Fernet `TOKEN_ENCRYPTION_KEY`, and an `APP_ORIGIN` suitable for the private test. The existing disposable PostgreSQL service proves offline tests only. No managed DB, public API/worker hosting, SMTP/Resend service or paid resource is created by this guide. Delivered-account/M3 acceptance separately requires approved hosting/HTTPS and `RESEND_API_KEY`, verified `MAIL_FROM` and transactional-mail permission.

### Authorized private workspace fallback

The founder explicitly authorized using the supplied credentials. Both are now stored in `/workspace/.ayo-private/runtime.env`, outside the Git checkout, in an owner-only directory 0700/file 0600. This is a local workspace file, **not** a managed vault binding or a deployment secret. It is available only while this workspace/private file persists. No actual value or key fingerprint is recorded in project documentation, source or evidence.

Use the loader to supply that file to the existing offline preparation check:

```sh
.venv/bin/python scripts/with-private-runtime.py
.venv/bin/python scripts/with-private-runtime.py -- .venv/bin/python scripts/check-provider-readiness.py --mode prepare --scope account
```

The helper checks ownership/permissions, rejects ancestor/file symlinks, anchors directory/file lookups, rejects malformed/duplicate/system-variable bindings and does not interpolate values. It does not display loaded values or modify the parent process environment. Explicit child commands receive the configuration; choose commands intentionally and never run environment-dumping commands. All supplied configuration currently keeps provider/mail switches 0. The managed runtime observation still has no vault bindings; readiness through this loader reports both credential-presence/shape checks as configured, not live-valid. Data/source/host/budget-review and actual database/mail checks remain blocked.

## 2. Gemini model and owner-side checks

Proposed exact model: **`gemini-3.5-flash-lite`**. Current official catalogue/detail/deprecation documents list it as stable, support structured output, and announce no shutdown date. These documents were fetched normally on 26 October; they do not prove your project's access or model quality. Recheck before execution. Avoid a `latest` alias or a preview model.

In your AI Studio/Google Cloud project UI, privately confirm:

1. The key is associated with the intended dedicated Ayo test project, enabled and restricted to the Generative Language/Gemini API. Current keys can be authorization keys bound to a service account; do not rely on an old key prefix. Use least privilege; no broad project Editor or unrestricted key is required by Ayo.
2. The API is enabled, the project/key is not blocked, and the chosen model/region is eligible. Nigeria and Ghana are listed in published availability, but this runtime's outbound location and your account/project eligibility are not yet verified. No region/VPN workaround is authorized.
3. Whether the project uses unpaid quota or billing. Possessing an AI Studio key proves neither free quota nor zero charges. If you want a free-only test, verify that account/plan and automatic purchases cannot bill you. A budget alert alone is not a hard cap. Do not enable billing or buy a plan to satisfy this checklist without your separate decision.

Proposed nonsecret model configuration:

```dotenv
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_MAX_OUTPUT_TOKENS=1500
GEMINI_THINKING_LEVEL=MINIMAL
AYO_PROVIDER_SPEND_AUTHORIZED=0
AYO_MAIL_SEND_AUTHORIZED=0
```

The adapter uses `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`, `x-goog-api-key` header, system/text messages, JSON MIME, one candidate, temperature 0 and explicit MINIMAL thinking with `includeThoughts:false`. Tools, provider search/grounding, URL context, files, batch/flex/priority and thought summaries stay off. MINIMAL does **not** mean zero thinking tokens. We did not send a model-list, key-validation or inference request.

The adapter now caps **combined system and serialized context at 32768 UTF8 bytes**, avoids ASCII-escape amplification and caps output at 1500 for this proposal. Budget policy is fingerprinted to the actual provider/model/input/output/thinking configuration. Changing the model or limits without matching review fails before reservation/network. This adds no SQL migration; the existing ledger hash stores the binding. Historical data and held debits remain intact.

Official references: [model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [deprecations](https://ai.google.dev/gemini-api/docs/deprecations), [API](https://ai.google.dev/api/generate-content), [thinking](https://ai.google.dev/gemini-api/docs/thinking), [keys](https://ai.google.dev/gemini-api/docs/api-key), [regions](https://ai.google.dev/gemini-api/docs/available-regions).

## 3. Budget proposal, not approval

Current authorized calls/spend: **0 / USD 0**. Machine-readable draft: [m2-live-test-review.json](../config/m2-live-test-review.json). Copyable **nonsecret** draft values: [.env.m2-prepare.example](../.env.m2-prepare.example); that file is not auto-loaded. Keep real values in the environment's secure configuration.

| Limit | Proposed conservative reservation/call cap |
| --- | --- |
| Gemini | USD 1.00 per call; maximum 2 calls and USD 2.00 global/scope total |
| Firecrawl | USD 0.25 per search or one-page fetch; maximum 4 operations and USD 1.00 global/scope total |
| One business journey | USD 1.50, maximum 3 operations: search + fetch + Gemini |
| Entire planned run | Maximum6 chargeable operations, USD 3.00 conservative reservation ceiling |
| Validity | One explicitly reviewed UTC day; both policy expiries no later than its next UTC midnight |

These are intentionally large **local authorization debits**, not expected invoices, verified vendor prices or permission to charge USD 3. Draft thresholds remain inactive until policy review and separate call approval. Current Gemini standard published rates are USD 0.30/M input and USD 2.50/M output including thinking. Ayo's small request should be much smaller than the reservation, but token interpretation, thinking, actual tier, tax/fees and current pricing need review; no token-to-invoice guarantee is made.

Firecrawl currently publishes 1000 free monthly credits with no card required, search 2 credits per 1–10 results, and basic crawl 1/page. Our two 5-result index searches plus two 1-page basic crawls have an estimated **6 base credits**, not six dollars. Markdown/HTML are requested; search result scraping, JSON/LLM extraction, paid prompt scanning, PDF parsing and proxy escalation are disabled. PII redaction is requested, but neither its completeness nor actual billing was tested. Check your actual plan, available credits, add-ons and automatic purchases privately; do not assume website pricing establishes your account's charges. USD/credit reconciliation remains pending.

Both `AYO_*_BUDGET_POLICY_VALID_UNTIL` values must be a reviewed future Unix UTC timestamp **at or before the next UTC midnight**. This prevents daily counters resetting inside the approved run. No expiry extension, next-day renewal or extra retry allocation is authorized. Active bucket limits are immutable: never delete ledger/counters to regain authorization. A definitive rejection consumes its conservative reservation and may exhaust the small trial budget; stop and review rather than increase it.

Source pricing: [Gemini](https://ai.google.dev/gemini-api/docs/pricing), [Firecrawl](https://www.firecrawl.dev/pricing), [search credit rules](https://docs.firecrawl.dev/features/search#cost-implications). These public documentation reads incurred no model/search/crawl API calls.

## 4. Data and source-access policy for review

Recommended limited approval: `AYO_AI_DATA_POLICY=public_only_reviewed`, **only after you accept this policy**. Ayo enforces this by rejecting private workspace inference before any model dispatch. The broader legacy `reviewed` value must not be used to turn a public-only free-tier review into private analysis permission.

Unpaid Gemini terms allow product improvement/training and human review, and prohibit personal, sensitive or confidential submissions. Only sanitized, reviewed, permitted organization/product text belongs in this trial. Exclude account identity, contact PII, customer/orders, owner private facts, credentials, session/claim links, raw unreviewed HTML and thought summaries. Public availability alone does not establish permissible personal-data or copyright use. If the chosen evidence cannot meet unpaid-service terms, stop; a paid-data-policy alternative requires separate review/approval. [Official terms](https://ai.google.dev/gemini-api/terms).

Before accepting `AYO_RESEARCH_EGRESS_POLICY=provider_managed_verified`, review Firecrawl's actual egress/redirect/robots controls, processing/retention and access terms. Add only exact independently reviewed hosts to `AYO_RESEARCH_APPROVED_HOSTS`. No wildcard, private service, login, access challenge or anti-bot bypass; no source write, personal-contact enrichment or outreach. The source adapter stays basic proxy, one page, depth 0, external/subdomain traversal off, robots enforcement requested and cache storage off. Flags are operator attestations, not independent proof.

The proposed businesses/hosts below are **unverified test selections**, not successful research or approved crawl targets. Resolve same-name ambiguity from actual permitted discovery, review source terms/robots and public evidence eligibility, then freeze the exact selected host/URL before retrieval. Redirect/profile identity restrictions still apply.

## 5. Preparation checks, safely disabled

After setting secure bindings and reviewed nonsecret configuration, from `/workspace/ayo` run:

```sh
python scripts/check-provider-readiness.py --mode prepare --scope provider
python scripts/check-provider-readiness.py --mode prepare --scope account
```

Both are offline: no API/model-list/DNS/database connection, no `.env` loading, no values printed, no setting changed. Preparation requires **both** spending/mail switches explicitly 0. Exit 0 means only the selected configuration scope passes; exit 2 lists missing/invalid/expired/unreviewed settings. A provider-only pass does not mean account/DB/mail/worker readiness. Model/key access and actual invoice cost remain unverified even on exit 0. The legacy default/`--mode armed` merely inspects an already-authorized configuration; it never arms it and is not the preparation command.

For public evidence persistence, separately verify the approved private PostgreSQL connection and `alembic current`/upgrade to the current head (`0007_assistant` after the merchant-stage migrations) under normal database change controls, with a backup for non-disposable data. Readiness deliberately does not infer connectivity/migration/worker health from a URL's shape. The offline regression suite already tests current schema parity/legacy preservation with real local PostgreSQL.

### Local fallback versus persistent bindings

The preparation loader now selects a complete credential source. `--source auto` prefers injected provider settings before reading any local file; `--source injected` never reads the workspace fallback. A partial or blank injected pair fails closed instead of reviving local keys. Injected nonsecret settings retain precedence too. Provider spending and mail must both be explicitly disabled; the helper refuses armed/ambiguous preparation rather than masking it.

```sh
python scripts/with-private-runtime.py --source injected
python scripts/check-secret-migration.py
```

These commands do not provision a secret or call a provider. The second emits readiness metadata only. An explicitly selected `--compare-local` can compare a complete valid injected pair with the owner-only fallback without printing values, hashes or partial matches; it does not read that file while injected preparation is incomplete. A result of `matched` still does not prove managed-vault provisioning, real environment recreation, key revocation, API validity, billing status or authorization. All those proof fields remain false until separately evidenced. Fresh child processes test configuration selection, not environment recreation; already-running API/worker processes require restart to pick up a new selected version.

Current managed observations still contain no application bindings; migration/rotation/recreation remain recorded blockers. Preserve signing/encryption/database compatibility before removing any fallback: migrating only two provider keys must not discard the key needed to decrypt existing jobs/tokens. No additional credential request or paid validation is part of the merchant-development stage.

## 6. Controlled two-business test, after configuration AND separate approval

| Planned query | Market | Proposed host for identity/access review |
| --- | --- | --- |
| Konga | Nigeria / NG | www.konga.com |
| Skin Gourmet | Ghana / GH | skingourmet.com |

These names/hosts have not been verified by an Ayo live provider call. Exact provider/model, sources, UTC window, policy versions, calls, maximum approved charge and reviewers must be recorded before execution. Source approval and public-data review are required independently of the numeric budget. All switches remain 0 during preparation.

1. Recheck secure runtime observations and offline provider preparation. Confirm no concurrent test/worker can consume the dedicated project/budget unexpectedly. No new deployment is necessary for an operator-led private provider test; public merchant hosting is a separate gate.
2. After explicit test approval, an operator can arm only the approved provider operations for that window. Keep transactional mail off. Discovery is at most one5-result index search per business. Inspect actual matching source/identity; if ambiguous or restricted, stop.
3. Collect at most one approved public page per business using the bounded source adapter. Persist and re-read a hidden evidence checkpoint before inference. For an unpaid-tier trial, **inspect the actual redacted organization/product excerpts before sending them**. Use an operator-controlled source-first service session (`ResearchService`, `ReportStore.stage_preview`) and review the retained snapshot; do not run the automatic research worker before that data review. The ordinary worker has no human review pause.
4. After evidence eligibility is confirmed, synthesize from that exact committed checkpoint using the existing public Gemini orchestration and publication validators. No private tenant facts or arbitrary URLs enter context. At most one Gemini request per business; no automatic ambiguous-call retry. If Gemini or any local limit fails, retain an explicit partial outcome.
5. Independently compare every observed quotation/citation with retained sources; assess inferred recommendations as hypotheses. Record real provider/model/usage, source/time/hash, ledger debit/outcome and reviewer verdict without raw secrets/PII. A single-page partial report cannot be called a full-site audit.
6. Stop after the two cases, disarm provider calls, retain all debits and compare actual provider records where permitted. Any unresolved source/model/privacy/cost outcome keeps M2 open. Registration/delivered-email/save/reopen/genuine leads remain the next separately configured live acceptance path; no contacts, sends or sales are invented.

The run is **prepared, not executed or approved**. Existing [M2 full-journey runbook](M2_LIVE_TEST_RUNBOOK.md) and [ROADMAP](../ROADMAP.md) remain binding. Full platform completion requires the broader end-state and independent live evidence.
