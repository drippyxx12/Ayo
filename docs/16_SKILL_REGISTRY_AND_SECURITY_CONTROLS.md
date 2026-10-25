# 16 — Ayo unified intelligence contract / security and evaluation

## One intelligence, controlled skills
User interacts with one Ayo agent. Internally it reasons over intent and a server-maintained registry of **real, versioned, permission-aware** capabilities. LLM outputs are requests to typed tools, not permission grants. Rules and user limits live in deterministic code and DB policy, not the prompt.

## Skill catalog (candidate)
| Skill | Mode | Prerequisite | Evidence | External side effect |
|---|---|---|---|---|
| `website.discover_candidates` | read | search provider configured | search source/URL/time | provider search cost only |
| `website.scan_public_site` | async read | validated domain + budgets + robots | actual fetched pages | outbound crawl only |
| `website.describe_business` | read | complete/partial report with evidence | source URLs | none |
| `website.compare_sites` | read | 2+ access-allowed reports | individual domain/page/date | none |
| `commerce.get_sales` | read | authorized Shopify connection and complete sync | source run + metric definition | none |
| `commerce.get_inventory` | read | permitted scope and synced catalog | provider item refs | none |
| `grow.find_listing_gaps` | read/prepare | verified store listing + public page observations | before/after facts | creates work draft |
| `work.propose_product_copy` | prepare | authorized tenant context | data refs + diff | creates proposal only |
| `work.approve` | command | authenticated merchant role + policy | approval record | authorization only |
| `shopify.update_product_copy` | write | granted write scope + unexpired approval + valid current state | Shopify mutation response and readback | writes merchant Shopify |

Each tool declares: `name`, `version`, JSON Schema input/output, tenant scope, access classification, minimum evidence, allowed actor roles, provider scope, monetary cost estimate, timeout, retry/idempotency strategy, risk level, audit requirements and required data freshness.

## Intelligence response schema
```json
{
  "message": "Summary grounded in visible evidence, or an honest data gap",
  "facts": [{"statement":"...", "kind":"observed | derived", "evidence_ids": ["..."]}],
  "hypotheses": [{"statement":"...", "confidence":"low | medium | high", "reason":"..."}],
  "limitations": ["Website inspection cannot establish sales figures"],
  "recommended_work": [{"draft_id":"...", "approval_required":true}],
  "source_window": {"earliest":"ISO-8601", "latest":"ISO-8601"},
  "data_freshness": "current | stale | partial | unknown",
  "provider_side_effects": []
}
```
Schema example is not a real output. Model-generated confidence labels are heuristics, not statistical probabilities unless calibrated.

## Permissions and actions
- `read` tools never receive private write credentials. `prepare` may persist a draft and its data citation but cannot dispatch a provider mutation. `approve` is a narrowly scoped recorded human act with preview hash, expiration and intended target. `execute` checks policy again and uses merchant-granted specific provider adapter and idempotency, then verifies result before status `completed`.
- The model does not hold Shopify refresh secrets, app secrets, raw access tokens, SMTP/API keys, merchant credentials or permission registry write access. Tool execution uses server-controlled identity/session and business context, never model-supplied business ID as authority.
- Public website instructions (HTML, JSON-LD, user reviews, alt text, code blocks, invisible CSS text) have **no privileged authority**, regardless of whether they impersonate system/assistant instructions.
- Anonymous site research cannot create public customer communications or modify external websites. Research of a competitor is not consent to contact them or their customers.
- For website research from merchant-owned URL, optional domain ownership verification is separate and cannot replace Shopify OAuth.

## Model/AI policy
- Prefer deterministic non-LLM extraction for product fields, prices, HTTP metadata, robots and schema.org when possible. LLM synthesizes evidence-limited explanations and hypotheses with source refs.
- Prompt assemble via explicit roles: system policy immutable; developer tool schema/version; merchant question; retrieved page content as a clearly labeled low-trust data structure; factual tools return typed fields. Output validator ensures every numeric merchant metric maps to deterministic tool result.
- No cross-merchant embeddings, memory or fine-tuning by default; opt-in/legal basis and strict tenant segregation required. Retain only necessary redacted traces. Inference provider usage metered; hard per-tenant budgets.

## Red-team and quality gates
- Prompt injection adversaries in all website formats; false business ownership; malformed JSON-LD; obsolete evidence; data contamination across tenants; runaway recursion/tool loops; response claiming an action that did not happen; Ayo leaking user's own merchant info in competitor reports; page that advertises fictional revenue; fake receipt.
- Measure citation precision, unsupported-claim rate, route-to-tool correctness, refusal/error accuracy, per-scan cost, time-to-useful-report, latency, cross-tenant zero-leak evidence, retries and crawl policy obedience.
- Ayo response must explain its own evidence and uncertainty, not simply produce persuasive sales copy with no source.

## First action walk-through
Public research of merchant-controlled shop identifies unclear shipping information on product page → authenticated Shopify source confirms actual current product description → Ayo drafts proposed description with citations and explicit inferred upside → merchant approves exact diff → policy validates fresh write scope and merchant identity → Shopify mutation attempted once → actual success/readback recorded → subsequent changes tracked; no claim of sales lift without suitable analytics.
