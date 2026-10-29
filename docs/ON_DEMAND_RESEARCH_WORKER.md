# Bounded research worker commands

29 October 2026. The existing standalone worker remains supported. Protected PostgreSQL staging can additionally host an explicit worker POST command, so a visitor need not wait for an always-on daemon before seeing public source research. This reuses the same encrypted queue, row leases, source checkpointing, analysis policy, immutable report publication and recovery logic. No migration or new provider.

## Command boundary

Intake/review POST still queues only. Status GET and opaque revision GET remain read-only. A separate CSRF-protected `/research/jobs/{id}/dispatch` command first checks the exact anonymous browser capability. Private `/research/library/{report}/refresh/{job}/dispatch` checks the requester, selected workspace, original report and current verified writer permission. The worker selector is restricted to that authorized job; it cannot fall back to another tenant's queued work.

The host requires `AYO_ON_DEMAND_RESEARCH=1`, PostgreSQL row-lock semantics, direct public acquisition and **paid-provider switch0**. SQLite, paid mode and Firecrawl modes fail closed. Only a queued, never-attempted job is eligible through this host. Repeats/concurrent commands return without another source attempt; active/failed/completed/retry jobs are not silently re-dispatched. The existing standalone worker retains its reviewed retry/checkpoint recovery behavior. Requests are throttled to10/hour per anonymous capability, alongside existing intake/private-refresh limits.

An explicit command awaits the real worker within100 seconds, inside a120-second staging function limit. It is not an unreliable after-response task. Source retrieval still has its45-second total bound, public-IP-pinned per-hop validation, robots/access checks, at most three selected pages and byte limits. All evidence commits before synthesis. A disconnected/deadline response does not prove failure or authorize another source/model call: current leases and committed/uncertain-dispatch fences remain authoritative.

The browser submits the optional worker form once after the already-authorized intake/review, polls actual saved progress without navigating away mid-command, consumes the command JSON body and opens the server-authorized report. It never automatically resubmits an interrupted command. Native manual POST works with JavaScript disabled. No completion percentages or fabricated results.

## Source-only default and cost

`AYO_ON_DEMAND_GEMINI_AUTHORIZED` defaults0. This host then creates an explicitly PARTIAL source report with `model_not_authorized_for_on_demand`, without initializing a model provider or reserving a model call. The UI states that no Gemini request was made. Existing earlier real Gemini receipts remain preserved; this is not new Gemini acceptance. Setting this extra switch1 still requires the existing data policy, exact model/current finite free-only budget and dispatch ledger; it never replaces those controls or permits paid calls. No new Gemini allowance is granted by this implementation.

Read-only staging inspection discovered an existing preview paid-provider flag1. It was lowered to0 in project configuration per the founder's no-spending instruction; production was already0. Existing immutable deployments retain old environment snapshots, so the new protected staging build must be checked before any live worker test. No monetary cap/consumed ledger was raised or reset, no model/mail authorization enabled, and no billing/protection upgrade performed.

## Preview origin

Each Vercel preview receives a new hostname. `application_origin` derives HTTPS origin only from trusted `VERCEL_ENV=preview`/validated `VERCEL_URL`, rather than the stale fixed APP_ORIGIN or any HTTP Host/forwarded header. Production/non-Vercel origin behavior stays unchanged. Foreign browser origins still fail CSRF checks.

## Verification and remaining scope

**1137 full tests pass,0 failures/skips**, actual isolated PostgreSQL17+SQLite,130.17s, one upstream warning.111 affected worker/refresh/inference/origin checks also pass. Cases include exact-job selection, foreign/CSRF/role denial, concurrent replay, source refusal/no fake report, source-only no-provider initialization, paid/unsupported host gates and trusted preview-origin checks.

Chromium390/768/1440 verifies public URL→exactly one worker POST→status poll during a deliberately slow fixture fetch→automatic visible source report, with attempt1 and no horizontal overflow. A JavaScript-disabled native keyboard form journey also passes.4 synthetic source calls,0 model calls, no real provider requests. [Browser receipt](evidence/on-demand-worker-browser.json). The harness was corrected to avoid reading discarded response bodies after navigation and to use native keyboard activation in the JS-disabled case. Interrupted harness processes and their isolated schema were explicitly cleaned; public records were untouched.

**Hosted acceptance succeeded:** core b6839e1 on protected staging processed exactly one reviewed Books to Scrape public-demo job.3 actual pages, URL/time/hash/robots-checked direct provenance, worker command1.349s, reportGET200 and unchanged-hash reopen in a new HTTP client. Gemini0/Firecrawl0/mail0/provider chargeUSD0. No account was created/claimed or logout/login/mail delivery asserted. [Actual receipt](evidence/hosted-source-only-worker.json), [readable evidence](evidence/hosted-demo-source-report.md). Backend CI40902795220 passed1137 tests/audit/secrets. The temporary15-minute test access was revoked and its private config deleted. This is a public scraping demonstration, not a real African merchant or complete business audit.

A subsequent focused browser probe fixes busy202 handling: wait for saved progress without reloading into another automatic POST.1 command/1 status poll, no provider call. [Protocol receipt](evidence/worker-busy-browser.json). This frontend follow-up leaves the live-tested backend unchanged, avoiding another source test.

Universal website compatibility, JavaScript rendering, complete audits, delivered account email, fresh Gemini/owner-input acceptance, domain proof, scheduling, commerce and external action/outreach capabilities remain unfinished. Source denials remain explicit; merchant-authorized information/documents remain an alternative.
