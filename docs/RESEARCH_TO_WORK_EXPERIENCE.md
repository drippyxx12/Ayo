# Research that leads to reviewed work

29 October 2026. Continues the existing branch, PostgreSQL workspace and research pipeline. No framework rewrite, migration, new provider, paid call or public deployment.

## Research and plans

Public/private research pages now check saved job progress automatically and follow the existing authorized report route when it changes. The capability-scoped JSON response exposes only an opaque revision and terminal flag. Polling is GET-only, same-origin, uncached, bounded to40 checks/six minutes, suspended in hidden/offline tabs and stopped on lost access/repeated network failures. It cannot enqueue, dispatch or retry a provider. Ordinary links work with JavaScript disabled. Failed jobs offer another public page or the existing authorized merchant-input/document workflow.

Product URLs use the existing2048-character URL bound; business names remain limited to250 characters. The sampler additionally recognizes actual `catalogue`, singular `category` and WooCommerce `product-category` paths. Initial+two-page/45-second sampling and all robots/DNS/pinned-egress controls remain. JavaScript-only pages, access walls and denied sources remain unsupported; universal domain compatibility is not claimed.

Saved public and merchant-input reports now offer an **action plan** review. Up to eight existing supported recommendations/opportunities can become selected internal Work tasks. The review binds exact saved JSON, supporting input IDs/times/hashes and input origin. Owner statements remain OWNER_PROVIDED_UNVERIFIED. Proposals are not certified improvements, priority scores or measured impact. No recommendations means an empty plan, never invented work.

Verified writer roles, CSRF, explicit review, unchanged evidence and listed suggestion keys are required. User/membership/business locks serialize team reviews and account changes. Stable workspace/report/hash/suggestion task identities prevent duplicates across repeat forms and concurrent team members, including after task edits/completion. New report versions are distinct evidence and may have separate plans. Tasks link the immutable original report; no message, website edit or provider execution follows. Completion remains merchant-recorded.

## Interface

The shared experience layer preserves black/beige/warm white, self-hosted Syne/DM typography and first500 all-feature access. Original line SVG icons, plus/minus disclosures, clearer hierarchy and button/navigation/link hover feedback replace inconsistent markers. Entrance movement never hides content. Reduced-motion preferences disable animation/transitions/smooth scrolling. Native disclosure keyboard behavior, visible focus and server forms remain. The restricted preview builder now ships its referenced shared CSS and JavaScript without weakening account/storage/provider restrictions.

## Separate loopback workspace preview

`scripts/run-workspace-preview.py` starts actual FastAPI web and research worker processes together. Both inherit identical PostgreSQL, durable signing/encryption and provider settings. Either process exiting stops its companion; shutdown cleans both process groups. The runner never provisions hosting, migrates data, seeds accounts, clears usage or enables providers/mail. It does not modify the existing Vercel deployment.

Use a dedicated loopback PostgreSQL database/schema already migrated to the repository head, durable `SESSION_SECRET`/`TOKEN_ENCRYPTION_KEY`, `ENVIRONMENT=development`, `AYO_PREVIEW_MODE=0`, `APP_ORIGIN=http://127.0.0.1:8000`, direct public research and explicit paid-provider/mail switches0. Keep configuration outside Git. Then:

```sh
python scripts/run-workspace-preview.py --check
python scripts/run-workspace-preview.py --port 8000
```

The check verifies configuration and actual PostgreSQL migration head without dispatching work. Starting the runner permits real direct retrieval only after a research submission. Gemini retains its current data/budget gates; unavailable inference produces explicitly partial source research. Disarmed mail does not deliver account verification. Tests use clearly synthetic verified reviewer accounts, not delivered mail or a verification shortcut for real users.

## Evidence and hosted dependencies

Full suite: **1112 passed,0 failed/skipped**, actual isolated PostgreSQL17+SQLite,132.53s, one upstream warning. The subsequent deployment-manifest regression plus16 preview checks also passed. New regressions cover polling isolation, URL bounds, source-linked task persistence/no-provider behavior, hash/role/CSRF/tenant checks, concurrent team deduplication and preview configuration/asset packaging.

Chromium390/768/1440 verifies icons, keyboard disclosures, reduced motion, visible search, reviewed refresh→worker fixture→automatic report opening→plan review→source-linked Work→logout/login/reopen. Actual web+worker children pass PostgreSQL preflight; ending the worker stops its web companion with no orphans. Temporary servers/schema are cleaned. Source/model/account data is synthetic:3 source and3 model fixtures, real provider calls0. [Browser receipt](evidence/research-experience-browser.json).

Read-only inspection found two projects protected on all deployments on the existing Hobby team. `ayo-development-preview` remains intake-only with just a preview signing secret. The separate Git-linked `ayo-merchant-staging` already has database, encryption, provider and policy bindings; presence alone does not prove connectivity/authorization. Its751cb09 deployment returns500: runtime logs show missing `httpx`, and build logs show pyproject-based dependency installation with no dependencies declared. The new PEP621 manifest pins the entire existing requirements.lock graph, with a parity regression test; no package versions changed. Existing Git integration may rebuild this protected preview on branch publication; no production target or protection setting is changed.

Hosted acceptance still requires actual DB/schema checks, a worker sharing its database/key, a finite current zero-cost model policy and authorized transactional mail. No replacement API key is requested or worker/paid resource provisioned. Final staging/CI evidence follows in MEMORY/PROGRESS. Local engineering remains unblocked.

Prior actual Gemini/company-record and direct-page receipts remain preserved. No successful new live refresh, owner synthesis, universal website support or complete platform is claimed. Domain ownership, isolated rendering, monitoring, commerce/action/outreach integrations and full acceptance remain in ROADMAP.
