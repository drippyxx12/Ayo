# Merchant platform: M3/M4 and M5 foundations

Date: 2026-10-27. **PARTIALLY COMPLETE; local implementation, not live-provider acceptance.** The full [C01–C18 product vision](../PRODUCT_VISION.md) and [M0–M10 roadmap](../ROADMAP.md) remain the destination. This slice keeps the existing FastAPI/SQLAlchemy/Jinja application and PostgreSQL architecture.

## Working merchant journeys

1. Register and verify using the existing account service. The automatic regression journey uses an explicitly offline encrypted-outbox verification link, not delivered mail. Search-first public onboarding remains available before signup.
2. Open Business; save the offer, products, audience, location and goals without requiring a website or Shopify account. These records are `OWNER_PROVIDED_UNVERIFIED`. Changes to the NG/GH market keep currency and timezone valid without converting historical money records or proving ownership.
3. Open the research library; search/filter saved records, inspect retained products, explicit categories, linked channels, citation support and source dates, compare versions of the same target or two distinct researched targets, and download a contact-redacted selected-report export. Saving or comparing reports grants no website control. Source changes and price disagreements describe retained listings, not verified stock, transactions or a complete competitor study.
4. Create internal Work from a saved report or prospect. Set a due date, review/update a task and record progress. Optimistic versions reject stale edits. Completing a task is merchant-recorded work, not a provider receipt or commercial outcome.
5. Search/filter saved prospects; organize them into lists; inspect original discovery evidence and qualification events; add notes and follow-up tasks. Prepare and edit a sourced introduction draft using the merchant's offer and an exact retained excerpt. This is a deterministic template or merchant edit, never represented as generated AI. No sending route exists. Drafts do not advance the contact pipeline.
6. Open Ayo; create a private conversation, ask about saved business context, reports, opportunities, prospects or tasks, and reopen the recorded question, read plan and source snapshots. The current foundation selects bounded deterministic read tools and uses the existing Gemini orchestration only under its existing authorization/data/budget gates. Missing/blocked/invalid/interrupted analysis is persisted honestly. No successful AI response is fabricated.
7. Log out/in and reopen persisted work. Switch between authorized workspaces; prior workspace records remain inaccessible in the new selected workspace. Conversations additionally belong to their individual account. Review activity, change a password and revoke other sessions using current-password confirmation.

## Services, storage and controls

| Area | Implementation | Persistence / boundary |
| --- | --- | --- |
| Business / Work | `ayo/merchant_work.py`, `ayo/merchant_routes.py` | BusinessProfile and Task; verified role checks, same-tenant source references, bounded inputs, caller-owned transactions and optimistic versions. |
| Grow / prospects | `ayo/lead_management.py`, `ayo/lead_routes.py` | LeadList/Item, LeadNote, OutreachDraft; composite tenant foreign keys, exact retained source/quote, audit and concurrent draft conflicts. Existing discovery/qualification retained. |
| Research | `ayo/research_workspace.py`, `ayo/research_workspace_routes.py` | Existing immutable reports; current-workspace published-only access, pagination, bounded returned pages, explicit 14-day source freshness, comparisons and redacted exports. Canonical/freshness filters stream tenant rows for accurate counts. |
| Ayo | `ayo/assistant.py`, `ayo/assistant_routes.py` | Private conversations/messages/tool runs; exact read-only versioned registry, per-user request limits, replay/single-flight fences, committed snapshots before inference and citation revalidation. |
| Account | `ayo/account_management.py`, `ayo/account_deletion.py` | Fresh password confirmation under a user-row lock, revocation of previous sessions/reset tokens, personal conversation removal and deletion of exclusive workspace records/linked encrypted research jobs. Shared business work remains with anonymized account attribution. |
| Overview | `ayo/merchant_overview.py`, existing platform routes | Real report/lead/task counts and workspace activity. Reconciled business-scoped sales/revenue/customer metrics remain unavailable. No imported alpha snapshot is guessed to belong to a business. |

Migration chain: `0004_budgets → 0005_merchant → 0006_lead_crm → 0007_assistant`. Existing users, founding grants, source reports, provider budgets and alpha commerce records remain intact. All model modules share one declarative registry. Migration 0006 uses a unique parent index rather than rebuilding populated SQLite lead tables, preserving events and task references. Downgrading removes the new domain data; follow [migration backup/rollback guidance](../migrations/README.md), never downgrade a live database without review.

The assistant registry contains only `business.profile`, `research.saved`, `opportunities.list`, `leads.saved` and `work.tasks`, version 1. User text, retrieved content and model output cannot supply a tenant, executable tool, provider or permission. At most three recent records per tool are retrieved; all limitations/truncation remain visible. Conversation history is retained for users but is **not transmitted to the model in this foundation**. Contextual follow-up reasoning, broader dynamic plans, durable approvals and external execution remain future milestones.

The premium palette, self-hosted Syne headings, DM Sans UI and DM Mono metrics are preserved. Home/Ayo/Work/Grow/Business, Research, Activity, Connections, Settings and Help link to functional routes. Native forms retain server validation, CSRF and accessible pending states. Full accessibility certification is not claimed.

## Evidence and limits

**888 automated tests passed, zero failed/skipped**; one upstream Starlette/httpx deprecation warning. Final merchant browser verification passed 132 HTTP and 132 screen checks at 390/768/1440px, and the existing NG/GH public research regression passed at each width. Automated tests use actual local PostgreSQL and SQLite with synthetic account data and clearly labeled source/model/mail fixtures. Browser evidence: [merchant platform receipt](evidence/merchant-platform-browser.json), reproduced with optional Playwright/Chromium:

```sh
AYO_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/ayo_test \
  .venv/bin/python scripts/verify-merchant-browser.py
```

This script refuses remote databases, migrates an isolated schema, generates synthetic runtime secrets, blocks browser egress outside its loopback origin, disables provider/mail spend and removes the schema/server afterward. Browser source snapshots and organization prospects are explicitly synthetic. Offline Gemini REST fixtures test actual adapter contracts separately. [PROGRESS](../PROGRESS.md) records exact test counts, corrections and GitHub receipts.

Neither a local test nor an inherited key proves a successful live API call, stable secret binding, hosted application, delivered mail or actual merchant outcome. The existing protected preview has not been updated by this stage and continues to disable private/account/provider routes.

## Live blockers retained without stopping development

- Managed secret bindings and recreation/rotation proof remain unverified. The current Cloud Environment observation has no application secret/runtime-variable bindings. Existing supplied credentials remain outside Git; no replacement credentials are requested for this stage.
- Gemini/Firecrawl account access, billing/data/source reviews, exact permitted domains and explicit bounded live-call authorization remain open. Current authorized paid calls: zero. Konga/Nigeria and Skin Gourmet/Ghana are proposed test cases, not researched businesses in this evidence.
- Hosted persistent API/worker/PostgreSQL, transactional sender/delivered verification, independent real NG/GH report/lead checks and release approval remain outstanding.
- Commerce/payment connections, business ownership proof, approved sending, verified replies/sales, governed provider actions, monitoring, backups and broader production/pilot review remain incomplete in the full roadmap.

Next independent development: extend ownership/correction and multi-source research workflows, then improve contextual follow-up planning and the business-scoped connector model while external operations remain disabled. Ayo remains **PARTIALLY COMPLETE**.
