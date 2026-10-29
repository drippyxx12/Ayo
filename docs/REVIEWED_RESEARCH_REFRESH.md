# Reviewed research refresh

29 October 2026. A verified owner/admin/editor can now review a refresh from a saved public report and queue a new private evidence version. The original report, citations, JSON and exports remain unchanged. This uses the existing encrypted job queue, research tables, provider budgets and target history; no schema migration or new provider was added.

## User flow

Open a saved public report, choose **Review a new source refresh**, inspect the target/scope and check the required review checkbox. Ayo queues one private refresh job. For direct websites the current three-page/45-second sampler applies; other adapters retain their existing bounds. Fresh robots, source-access, provider-data and cost controls still apply. Entering a refresh never grants ownership or merchant-write permission.

The worker saves a hidden private evidence checkpoint before the existing Gemini step. A published new version appears in the private library/history. If Gemini is unavailable under the current policy or allowance, the new source-only version explicitly remains partial. A denied or failed source does not create a fabricated version. The original stays available throughout. Users can compare versions using the existing history/comparison view.

Owner-provided descriptions/uploads cannot be converted into crawl targets through this feature; they must be revised in the merchant-input workflow.

## Scope and replay controls

Each encrypted request binds actor, workspace, original report ID and SHA256 of the exact reviewed JSON. The target, market and business label come from that stored report, never editable request fields. An original record changed out of band invalidates the earlier review. User/membership locks keep request, checkpoint and publication checks current; private worker locking follows the same User→Job order as account removal.

A nonce produces a deterministic private job ID. Replayed or simultaneous submissions return the existing job and cannot dispatch another source/model request. Persistent audit tombstones reject an old nonce even after its job receipt expires. Three new refreshes per business/hour are allowed; replay does not consume an extra slot. Existing durable provider call/money policies, expiry and uncertain-dispatch fences are unchanged.

The private job uses an internal random anonymous capability that is never handed to a browser. Its sources attach to the selected workspace, have no anonymous expiry/capability, and issue no public claim token. Private status is bound to the original requester/workspace/report; completed reports use normal current-workspace access. Pending evidence remains unreadable through report/library/public endpoints. Permission is rechecked before retrieval, after retrieval, before model context and at publication. Revocation fails closed and discards only this job's unpublished checkpoint.

## Data lifecycle

Successful refreshes preserve both original and new immutable versions. New evidence keeps actual final source URLs; the report's target/history key remains the reviewed target, so ordinary same-site redirects do not detach its history. Audit events separately link requested/published versions and keep ownership explicitly unverified.

Removing an account removes its queued/running refresh jobs and encrypted payloads, including jobs with no report checkpoint yet. Shared published business history retains the existing account-removal semantics. Retention removes expired job receipts and unpublished checkpoints; it preserves saved report versions and the replay-denial tombstone. No consumed usage ledger is reset or deleted.

## Verification and limits

**36 refresh tests passed** on SQLite and actual isolated PostgreSQL, covering version creation, exact original/export preservation, private checkpointing, requester/tenant/role/CSRF/consent checks, unchanged reviewed inputs, revoked permissions at each async boundary, concurrent replay, expired-nonce replay, bounded requests, source denial, account removal, crash resume without refetch, owner-input exclusion and retention. The full application suite passed1066 tests,0 failures/skips,116.89s, one upstream warning.

Focused Chromium verification passed at390/768/1440px using actual loopback HTTP/PostgreSQL: native review validation, checkbox bounds/no overflow, private queue, source/model fixtures, new-version rendering, logout/login/reopen and original immutability. [Browser receipt](evidence/research-refresh-browser.json). The maintained [verifier](../scripts/verify-refresh-browser.py) needs the same optional Playwright/Chromium tooling as the existing browser scripts. It accepts only loopback PostgreSQL, blocks browser egress, uses synthetic ephemeral credentials, disables real providers and cleans its temporary server/schema.

Source/model/account/email inputs are explicitly synthetic fixtures. No new live website/Gemini/Firecrawl/mail call, credit purchase, paid spending, public deployment, outreach or merge was performed. Prior real provider receipts remain valid. JavaScript rendering, recurring/scheduled refresh, independently checked live refresh quality and actual domain ownership proof remain unfinished.
