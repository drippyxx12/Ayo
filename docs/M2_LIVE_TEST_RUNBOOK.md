# M2 controlled live-test runbook

Status: **PARTIALLY COMPLETE. No live provider workflow is certified by this runbook.** The automated regression suite uses labeled offline fixtures. The existing protected preview has provider calls, merchant accounts and persistence disabled; it cannot perform this acceptance journey. No deployment, spending or outreach is authorized by these instructions.

Current secure setup target, model, draft limits and founder-review policies: [M2_SECURE_SETUP.md](M2_SECURE_SETUP.md). Use preparation mode with both switches 0; no key value belongs in chat. The existing test plan remains unexecuted.

## Configuration and authorization gates

Prefer runtime secret-manager bindings shared by the web and worker. The founder has explicitly authorized the supplied credentials; they are now in an owner-only workspace configuration outside Git, loaded with `scripts/with-private-runtime.py`. Values must never enter source, screenshots, URLs or command history. This fallback does not create managed vault/deployment bindings. A connected personal app or chat subscription does not supply Ayo API authorization.

Required provider secrets and server settings:

| Setting | Required configuration and evidence |
| --- | --- |
| `GEMINI_API_KEY` | A Gemini Developer API project key with separately approved API access. Presence/basic syntax can be checked offline; validity cannot. |
| `GEMINI_MODEL` | An explicit evaluated model identifier available to that project, supporting the selected `generateContent` JSON response configuration. Do not assume a model named in old examples is available. No default model is silently selected. |
| `FIRECRAWL_API_KEY` | A separately authorized Firecrawl API key supporting the v2 search/crawl operations used by Ayo. |
| `AYO_AI_DATA_POLICY=public_only_reviewed` | Operator attestation after reviewing the chosen Gemini account/tier's retention, training, processing locations and permitted public-source data. This mode blocks private workspace inference; broader private-data use requires a separate review. The flag itself is not proof of review or compliance. |
| `AYO_RESEARCH_EGRESS_POLICY=provider_managed_verified` | Operator acceptance of the provider's network, redirect, robots/terms and source-access controls. Ayo does not locally fetch arbitrary submitted URLs. This attestation does not independently prove the provider's controls. |
| `AYO_RESEARCH_APPROVED_HOSTS` | Comma-separated exact public hosts approved for this test. Include separately approved redirect/www hosts only when needed; no wildcard or access-wall bypass. Search discovery does not grant permission to crawl a candidate. |
| `AYO_PROVIDER_SPEND_AUTHORIZED` | Keep `0` while preparing. Only set `1` after the founder separately authorizes the test providers, target sources, maximum calls and maximum conservative budget. Credentials alone are not spend approval. |

The production budget validator requires **all** of these settings. Values must be selected from reviewed current model/provider pricing and actual operation limits, not copied from a fabricated example:

- `AYO_REQUEST_BUDGET_MICROUSD`, `AYO_REQUEST_CALL_LIMIT`.
- `AYO_FIRECRAWL_DAILY_BUDGET_MICROUSD`, `AYO_FIRECRAWL_DAILY_CALL_LIMIT`, `AYO_FIRECRAWL_SCOPE_DAILY_BUDGET_MICROUSD`, `AYO_FIRECRAWL_SCOPE_DAILY_CALL_LIMIT`.
- `AYO_FIRECRAWL_BUDGET_POLICY_VERSION`, `AYO_FIRECRAWL_BUDGET_POLICY_VALID_UNTIL`.
- `AYO_FIRECRAWL_SEARCH_RESERVATION_MICROUSD`, `AYO_FIRECRAWL_FETCH_RESERVATION_MICROUSD`.
- `AYO_GEMINI_DAILY_BUDGET_MICROUSD`, `AYO_GEMINI_DAILY_CALL_LIMIT`, `AYO_GEMINI_SCOPE_DAILY_BUDGET_MICROUSD`, `AYO_GEMINI_SCOPE_DAILY_CALL_LIMIT`.
- `AYO_GEMINI_BUDGET_POLICY_VERSION`, `AYO_GEMINI_BUDGET_POLICY_VALID_UNTIL`, `AYO_GEMINI_ANALYZE_RESERVATION_MICROUSD`.
- Exact model binding: `AYO_GEMINI_BUDGET_MODEL`, `AYO_GEMINI_BUDGET_MAX_INPUT_BYTES=32768`, `AYO_GEMINI_BUDGET_MAX_OUTPUT_TOKENS` and `AYO_GEMINI_BUDGET_THINKING_LEVEL`, matching `GEMINI_MODEL`, `GEMINI_MAX_OUTPUT_TOKENS` and `GEMINI_THINKING_LEVEL` (or `provider_default`). Configuration changes invalidate the review before dispatch.

Amounts are positive integer USD micro-units: one micro-unit is USD 0.000001. Policy expiry is a future Unix UTC timestamp. Policy versions identify a retained operator review of pricing, model, token/byte/page limits and a conservative upper bound for each operation. Include thinking/output charges, the actual provider plan and any minimum credit cost. The application reserves before dispatch, records usage where available and retains the configured conservative debit after failure or ambiguous timeout. These amounts are **budget accounting**, not a claim to have measured provider invoice costs. Check the provider's own project billing limits too; those limits and quota resets can differ from Ayo's daily window. Active request/provider-day/scope-day bucket caps are immutable. A mid-window cap change fails closed; retain counters and wait for the next UTC window or perform an explicitly reviewed migration. Never delete ledger/buckets to regain authorization. Do not lower or reuse a reviewed policy to disguise prior spend.

Optional private Claude analysis needs its own `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` and matching `AYO_CLAUDE_*` policy. It is not required for M2 public reports, which use Gemini without silent vendor fallback. No outreach or commerce permission follows from either API key.

For the complete account journey also configure:

- Durable PostgreSQL `DATABASE_URL`, consistent `SESSION_SECRET` of at least 32 characters, a valid durable Fernet `TOKEN_ENCRYPTION_KEY`, and explicit `APP_ORIGIN`. Use HTTPS for any remotely reachable account test; plain HTTP is restricted to loopback development.
- An approved environment with additive migration `0004_budgets` applied and a web process plus `python -m ayo.worker` using the same configuration and encryption key. Run approved cleanup separately. Do not run a fixture server as a public merchant environment.
- A verified transactional email sender/domain, `RESEND_API_KEY`, `MAIL_FROM`, and separate `AYO_MAIL_SEND_AUTHORIZED=1` authorization. Run `python -m ayo.worker --mail` only after authorizing account email delivery. This is not marketing/outreach consent.
- Required database backup/TLS/restore, privacy and hosting decisions before storing real merchant information. No production database or hosted account application is provisioned by this document.

## Safe offline preflight

From the repository root, after installing the pinned dependencies:

```sh
python scripts/check-provider-readiness.py --mode prepare --scope provider
```

This script does not load `.env` files, connect to a database, call a model-list endpoint, validate a key remotely or make any network request. It prints fixed check IDs/statuses, never configuration values, hashes or key fragments. Preparation requires provider and mail switches explicitly `0`. Exit `0` means the selected provider configuration scope passes; use `--scope account` to include account/mail configuration. Exit `2` means settings are missing, inconsistent, expired, unreviewed or switches are not disabled. Legacy/default `--mode armed --scope account` checks an already authorized configuration without enabling it. Both outcomes report `live_verified: false`.

A pass does not prove that a key works, a model is available, a source permits retrieval, email is delivered or the database is reachable. Verify those only in the separately authorized controlled test. A missing credential is a blocker to live calls, not a reason to substitute a fixture as live success.

## Reproducible offline browser regression

The optional browser check needs Playwright's Python package and `/usr/bin/chromium` in addition to the pinned application dependencies. Run it against a **disposable local PostgreSQL test database** using `AYO_TEST_POSTGRES_URL=<test-url> python scripts/verify-m2-browser.py`. It creates/drops an isolated schema, binds only `127.0.0.1:8018`, generates ephemeral local signing/encryption settings, disables spending/mail and injects explicit source/model/mail fixtures. It does not deploy or contact a provider. The receipt is `docs/evidence/m2-hardening-browser.json`.

The current receipt covers NG/GH at 390/768/1440px, persisted queue/retry events, source/Gemini fixture report, private save/relogin/reopen and leads. Five cases create/verify a new fixture account. The sixth correctly reaches the existing five-per-hour signup limit, then reuses an already verified fixture account; the control is preserved and this distinction is recorded. No overflow/page errors were found and font roles loaded. Database migration behavior is separately tested in the main suite; this script's schema is disposable and is not a deployment procedure.

## Current API contract review

Official public documentation was retrieved and reviewed on **26 October 2026**, without credentials or calls to inference/search/crawl/model-list APIs:

| Official source | Applicable contract and limitation |
| --- | --- |
| [Gemini generateContent reference](https://ai.google.dev/api/generate-content) | REST `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`; key in `x-goog-api-key`, with `systemInstruction`, text `contents` and `generationConfig`. JSON MIME and output-token limits remain documented. Ayo does not enable tools, provider search or URL fetching. |
| [Gemini API versions](https://ai.google.dev/gemini-api/docs/api-versions) | v1beta schemas may change. New guides may default to the Interactions API; that is not a reason to silently migrate Ayo's existing adapter. Validate this exact endpoint/configuration for the selected project/model. |
| [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) and generateContent reference | JSON formatting is not factual validation. Current reference marks older schema fields deprecated in favor of newer response-format configuration; Ayo retains the documented JSON MIME path and validates structured claims/citations locally. Do not add a deprecated schema field based on an old example. |
| [Thinking](https://ai.google.dev/gemini-api/docs/thinking) and generateContent usage metadata | Model-dependent thinking can affect latency/cost. `thoughtsTokenCount` is separate; total usage includes prompt, tool-use prompt, thoughts and candidates. Visible final text alone does not measure all billed output. Do not enable thought summaries or store model reasoning as business evidence. |
| [Safety settings](https://ai.google.dev/gemini-api/docs/safety-settings) | A blocked prompt/candidate can produce no usable report. Do not relax safety, resubmit modified prohibited input or represent a block as success. |
| [Troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting) | Authentication/client errors, rate limits, service failure, transport uncertainty and malformed/safety output require distinct safe states. Ayo deliberately avoids automatic inference retries after ambiguous dispatch because charges may already have occurred. |
| [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) and [pricing](https://ai.google.dev/gemini-api/docs/pricing) | Limits are project/model/tier dependent, with request and token dimensions; provider daily reset may differ from Ayo's accounting. Pricing must be reviewed for the chosen configuration. No model quota or invoice price was inferred from documentation alone. |
| [API key guidance](https://ai.google.dev/gemini-api/docs/api-key) | Keep keys server-side and restrict/rotate them through provider controls. A string's shape is not proof of valid credentials. |
| [Firecrawl search](https://docs.firecrawl.dev/api-reference/endpoint/search), [crawl start](https://docs.firecrawl.dev/api-reference/endpoint/crawl-post), [status](https://docs.firecrawl.dev/api-reference/endpoint/crawl-get), [cancel](https://docs.firecrawl.dev/api-reference/endpoint/crawl-delete) | Search/create require success envelopes; crawl status has no required success field and cancellation returns a status object. Ayo now parses these separately, sends explicit NG/GH search country and bounds creation/polling with one deadline plus at most two seconds of cleanup. Poll failures after acceptance never trigger a fresh crawl. Review source/profile identity, access-wall and encoded-path restrictions; no bypass mode is enabled. Requested robots/source controls do not certify the vendor's network guarantees. No live Firecrawl result was obtained. |

Public documentation retrieval is live documentation evidence only. It is not live business research, credential validation or model acceptance.

## Separately authorized real acceptance journey

Before starting, record approval for the exact provider/project/model, allowed hosts, bounded calls, policy versions, maximum budget, test account and transactional recipient. Keep secrets and personal account identifiers out of the repository evidence. Confirm the local offline suite is green, migrations are current and the public preview remains disabled for provider/account operations.

1. Enter a real Nigerian business name with market **NG**. A planned query may be “Konga”; this runbook has not researched or verified a current candidate. Record the exact query, timestamp and provider receipt. Do not silently accept a same-name organization.
2. Inspect actual candidate URLs and source snippets. Resolve ambiguity explicitly. Confirm source permission/robots and approve the exact candidate host before retrieval. Search absence, blocked social access, weak evidence or an unavailable source is a valid partial outcome.
3. Retrieve permitted evidence. Inspect the persisted redacted snapshot, public URL, retrieval time, content hash, provider receipt and coverage. Confirm no login, private data, access challenge or secret entered model context. Verify the database evidence checkpoint exists before inference and is inaccessible without the public report capability.
4. Generate the Gemini report using the configured model. Record actual success/block/timeout/failure, retained token usage and budget reservation. Independently compare **every** factual claim/quotation to the retained source and current accessible page; inspect inference labels, limitations, country uncertainty and recommendations. Reject fabricated financial figures, people, contacts or execution claims. A partial single-page report is not a verified full-site audit.
5. Register a new legitimate merchant account. Receive the actual transactional verification email; use that link. A fixture-extracted token does not pass this live gate. Confirm the correct first-500-user entitlement without consuming another slot for another workspace.
6. Save/claim the exact report once into the verified account's authorized workspace. Check a foreign account cannot view or claim it. Saving a report must not mark the researched domain as owned or grant commerce/outreach permissions.
7. Log out, verify the old session is revoked, log in again and reopen the saved report. Check the same source hashes, analysis, market/coverage and timestamps survive a web/worker restart using PostgreSQL.
8. Define an organization audience and discover genuine relevant prospects through approved sources. Independently inspect identity, deduplication and fit evidence. Record source URLs/receipts/times; distinguish discovered and merchant-qualified from contacted/replied/converted. No messages or sales may be invented or sent during this test.
9. Repeat **steps 1–4 for Ghana (GH)** with a separately selected real business; “Skin Gourmet” is a planned query, not an already verified result. Confirm the selected Ghana context does not itself prove domicile, ownership or GHS payment acceptance. Check country/currency labels and cite actual evidence.
10. Exercise an approved negative case without provoking provider abuse: disabled configuration and exhausted local budget must block dispatch; a fixture can verify forced rate-limit/timeout/malformed cases. Never intentionally spend to exhaust a real provider quota. Reconcile local conservative debits/usage with available provider records and clearly retain unknown actual costs.

Write a redacted receipt identifying source-code commit, provider/model, operator policy review, actual calls and timestamps, source evidence hashes, independent reviewer, account/mail outcomes, tenant-isolation result and remaining failures. Do not commit raw keys, session/claim/email tokens, private account data or unredacted provider payloads. Clearly separate actual provider output from offline regression fixtures and from ordinary documentation retrieval.

If any required live step remains blocked or fails, keep M2 acceptance open and Ayo **PARTIALLY COMPLETE**. Continue independent engineering; never replace the missing outcome with a fabricated report or a screenshot of fixture data.
