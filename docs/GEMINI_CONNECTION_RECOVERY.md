# Gemini connection recovery — 27 October 2026

**Gemini connectivity VERIFIED LIVE at 2026-10-27 14:47:48 UTC.** After the initial recovery checks below, the founder supplied the existing credentials; they were stored outside Git in the owner-only private runtime. Exactly one synthetic Standard request returned HTTP200, `AYO_GEMINI_OK`, model `gemini-3.5-flash-lite`, response ID `lLngarKdJ4HAqtsPgonv0AM`, and 12 input / 7 output / 19 total tokens. [Actual redacted response receipt](evidence/gemini-connectivity-attempt.json). No retry or Firecrawl request occurred; general provider/mail switches remain disabled. Cost basis: founder-reported Free-tier Ayo project plus current official Free-tier pricing; no independent billing statement was accessed. Full M2 research acceptance remains open.

The sections below preserve the initial recovery evidence and the executed one-request plan. Their missing-credential blocker was resolved by the founder during this session. Do not repeat the successful connectivity test.

Recovered branch `codex/africa-platform` at `711f7aedf3798568b00931091c3544dc66f1b91c`; PR #1 is open/draft/unmerged. Latest PR CI [40469700236](https://github.com/drippyxx12/Ayo/actions/runs/40469700236) succeeded. Application code remains `09c6abc965030cf47cc0d292fe0833f0c0e00e5c`. The fresh checkout was clean. Previous uncommitted files/private logs are unavailable here.

[Previous verification](evidence/merchant-stage-verification.json) explicitly records `provider_live_workflows_verified:false` and offline readiness `network_requests_made:0`, `live_verified:false`. Its 888 passing tests use offline provider fixtures. There is no actual Gemini HTTP/model/usage receipt to show. An unrecorded request in the inaccessible prior workspace cannot be ruled out.

## Initial blocker and founder action — resolved this session

This attached environment is new (current spec 1, running, enforced networking), with zero secret/runtime bindings. `GEMINI_API_KEY` and `GOOGLE_API_KEY` are absent. The previously recorded `/workspace/.ayo-private/runtime.env` does not exist here. The GitHub clone recovered source, not private workspace storage.

1. Reattach the previous private Codex workspace, or securely bind its **existing Ayo-project `GEMINI_API_KEY`** to this attached environment. Keep the value out of chat and Git. Regenerating the key is unnecessary for this blocker.
2. For the project associated with that same key, retain the **Free** tier already reported by the founder. Check [AI Studio rate limits](https://aistudio.google.com/rate-limit) for `gemini-3.5-flash-lite`: nonzero request/token quota and capacity for one tiny request. A Free label alone does not reveal remaining quota. Do not upgrade billing to unblock this test.

Firecrawl, transactional email, a database and source-crawl approvals are not prerequisites for this isolated synthetic connectivity check. Their existing gates still apply to the full research journey.

## Current zero-cost and policy evidence

Ordinary official documentation GETs succeeded on 27 October; URL/status/content hashes are in the [recovery receipt](evidence/gemini-connection-recovery.json). No paid lookup or provider API operation was used.

- [Model catalogue](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite): stable exact model, structured output supported. [Deprecations](https://ai.google.dev/gemini-api/docs/deprecations): no shutdown date announced. This is public availability, not proof of access for the absent key.
- [Pricing](https://ai.google.dev/gemini-api/docs/pricing): this model's **Standard Free Tier input and output, including thinking, are “Free of charge.”** Paid-tier prices remain $0.30/M input and $2.50/M output. No paid-tier fallback is authorized.
- [Billing](https://ai.google.dev/gemini-api/docs/billing): paid access requires billing setup. The founder reports the Ayo project is Free; the absent credential cannot yet be tied to that project here.
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): project-scoped, actual limits in AI Studio, capacity not guaranteed; provider daily quotas reset at midnight Pacific. Do not confuse that with Ayo's local UTC budget window.
- [Terms](https://ai.google.dev/gemini-api/terms): unpaid content may be used for product improvement and human review; personal, sensitive and confidential submissions are prohibited. Use only the synthetic sentence below. Operator age/region/use eligibility still applies; [Nigeria and Ghana are listed](https://ai.google.dev/gemini-api/docs/available-regions). No geographic restriction bypass is authorized. Private merchant AI remains blocked by its separate policy.

## Executed one-request plan — do not rerun

The latest user instruction **already conditionally authorizes one real connectivity request at verified USD 0**. Do not request paid-call approval or repeat a successful test. It does not authorize the earlier two-business paid-budget proposal in [M2 secure setup](M2_SECURE_SETUP.md).

Use a single Standard `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`, key in `x-goog-api-key` only. Exact input: `Reply with exactly AYO_GEMINI_OK.` One candidate, temperature 0, maximum 64 output tokens, `thinkingLevel:MINIMAL`, `includeThoughts:false`; bounded 30-second timeout. No search/grounding, URL context, tools, files, caching, batch, flex or priority. No model-list/key-validation request, redirects, retries, fallback model or concurrent worker.

Only execute after the selected credential's project/tier/quota and applicable terms are established. Keep Ayo's general provider/mail switches disabled; this diagnostic grants no background-worker or private-data permission. Do not alter application budget ledgers or increase allowances. On a rejection or uncertain timeout, retain that result and stop after the one attempt.

Record actual UTC time, HTTP status, returned text, model version/response ID where returned, numeric usage and the exact request settings, excluding authentication headers. Only an actual successful response proves connectivity; it still does not pass M2's real NG/GH source-to-report acceptance. Once verified, resume the existing roadmap at M4 ownership/correction and multi-source evidence, followed by M5 contextual planning and business-scoped connectors. Preserve all completed milestones.
