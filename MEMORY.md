# Ayo project memory and stopping point

Updated: 2026-10-25 23:38 UTC. Overall platform: **PARTIALLY COMPLETE**.

## Persistent working preference

The founder wants a direct browser link, not screenshot links, and a clear account of where work stopped. Always give the actual app URL first, state which features can be used, and label any screenshot walkthrough as separate evidence. Read this file at the start of every session. Before pausing or ending a session, update the current step, last verified evidence, code/PR reference, preview scope, blockers and exact next action. Append historical evidence to PROGRESS.md; keep this file as the current handoff. End work-session summaries with a brief **Stopped at / Next / Blocked by** statement. This is repository-backed project memory, not a claim about account-wide ChatGPT memory.

## Current step and stopping point

- **M2: early public Gemini research pipeline is implemented and verified locally with explicit offline fixtures.** Real-source/Gemini acceptance has not passed.
- The worker commits hidden evidence before inference, uses a public-only Gemini context, revalidates citations on publication, and retains model/policy/usage metadata. Pending evidence is unreadable and unclaimable. Missing/rejected/timed-out AI remains explicitly partial.
- This handoff: refreshed the protected browser preview and saved persistent project memory. The new deployment is READY and hosted checks passed; no merchant backend/provider was enabled.
- The full C01–C18 end-state remains in PRODUCT_VISION.md and ROADMAP.md. MVP and customer V1 are intermediate milestones.

## Last verified evidence

- **256 tests passed**, zero skipped, with actual local PostgreSQL and offline source/model fixtures; one upstream deprecation warning.
- SQLite/PostgreSQL HTTP tests exercise the actual Gemini REST adapter through a mock transport, then report → signup → fixture verification → claim → logout/login/reopen → lead discovery/qualification.
- Chromium passed 390/768/1440px fixture workflows, font checks, overflow checks and page-error checks. Evidence: `docs/evidence/public-gemini-browser-workflow.json`.
- Code CI passed: [40244375756](https://github.com/drippyxx12/Ayo/actions/runs/40244375756) and [40244371760](https://github.com/drippyxx12/Ayo/actions/runs/40244371760). Ruff, whitespace and secret scans passed.
- No real research/model/mail/store/payment/outreach/sale outcome was verified. Local browser servers were stopped and temporary session settings removed.

## Source and review references

- Repository: [drippyxx12/Ayo](https://github.com/drippyxx12/Ayo). Review: [draft PR #1](https://github.com/drippyxx12/Ayo/pull/1); not merged.
- Remote review branch: `codex/africa-platform`. Latest verified code: `a5a2fd78ddeebdc83bba2cfb7f0080111701d6b1`.
- Latest published evidence receipt before this task: `7ffb2ae71d200e8d07f5ad22f2f7b52c9349b869`.
- Local branch `codex/search-first-foundation` has different commit ancestry/SHAs. Remote receipts above identify published code; do not infer a push from a local commit.
- The original ZIP and source hashes are preserved. Historical Emergent/builder sources remain unavailable and unmerged.

## Preview scope

- Direct browser link: [Open Ayo development preview](https://ayo-development-preview-5icko1nq4-ayodejiiolatunbosun-7460.vercel.app/). Vercel Authentication may require the founder to sign in with the authorized account.
- Deployment: `dpl_FHxr7kjKUjVhvUAcyccB6JmptXBC`, target preview, READY; all-deployment Vercel Authentication remains enabled.
- Interactive scope: public business intake with honest unavailable states. Registration, private workspace, provider calls and persistence are disabled in this preview. It is not the full hosted merchant application.
- Separate optional evidence: `/static/tour.html` shows current labeled offline Gemini screenshots plus a Where we stopped panel; never substitute it for a requested interactive app link.
- Latest preview checks: hosted intake/tour 200, signup correctly disabled 503; local gallery at 390/768/1440px loads all current image hashes, no overflow/page errors, no credential/data collection forms. Existing preview restrictions: 11 tests passed. No backend-code change or broad suite rerun in this refresh.
- Current screenshots: `/workspace/ayo-evidence/gemini-*.png`. Preview builder: `scripts/build-preview.py --screenshot-prefix gemini`; source: `preview/`. Receipt: `docs/evidence/current-preview-hosted.json`.

## Next concrete actions

1. On resuming, read this memory and preserve the direct preview URL/scope; do not restart completed source/vision work.
2. Clear M2 live setup through secure runtime settings: permitted source provider, available Gemini model, reviewed source/egress/data policies and explicitly authorized usage limit. Never paste keys in chat or copy connector secrets into app runtime.
3. Run an authorized real NG business and GH business through evidence → Gemini → cited report, with independent source checks and redacted receipts.
4. Configure authorized transactional mail and persistent hosted identity before accepting M3 signup/save/reopen/leads live. Continue full roadmap requirements after these gates; never call the MVP finished Ayo.

## Blockers and invariants

- The observed runtime has no configured application secrets/provider variables. Actual research/Gemini calls and email delivery remain blocked. Production DB/worker/secrets, source acceptance, budget approval and independent operational/privacy reviews remain outstanding.
- Keep one unified Africa-first Ayo; Nigeria/Ghana, NGN/GHS, public research before signup and optional Shopify. Preserve Syne headings, DM Sans UI, DM Mono metrics and the editorial palette.
- First 500 distinct legitimate user accounts receive all released/future Ayo features free; no repeated slot per business or automatic expiry/billing. Provider fees and permissions are separate.
- No fabricated facts, leads, customers, sends or sales; no unauthorized outreach, merchant writes, public production deployment or spending. Existing protected-preview authorization covers the requested scoped preview only.
- Enriched report JSON needs compatible web/worker readers. Previous strict readers reject new fields; follow RUNBOOK before an approved rollout/rollback.

## Do not restart completed work

Use existing code, migrations, tests and receipts. Do not re-import/overwrite the ZIP, rewrite the framework, recreate the preview project or duplicate PR #1. Do not rerun broad tests without changes or a new concern. Consult PRODUCT_VISION.md, ROADMAP.md, FEATURE_STATUS.md, PROGRESS.md and RUNBOOK.md for scope, evidence and operational detail.
