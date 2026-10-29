## Highest-priority founder update — 25 October 2026: SEARCH-FIRST, not signup-first
**Binding UX sequence:** public visitor `SEARCH (name/site/social) → source-backed website/business research → useful mini-report + optional actual organization-level lead preview → CTA create free account → secure report claim and private workspace → Ayo sourced lead discovery & operations → OPTIONAL Shopify or other integrations`. E-commerce only; Africa-first for Nigeria, Ghana and later countries. Ayo must also work for businesses with NO website, via permitted public listings or owner-supplied labeled facts. **Never require Shopify or signup to see the initial public mini-report.** Public research never grants site ownership, OAuth permissions or marketing consent. Model recommendation: Gemini for cited web discovery and URL analysis; Claude optional behind an evaluated adapter for complex planning; actual execution through Ayo's typed approval/policy engine. DO NOT confuse AI model chat subscriptions with API credentials or provider spend. Detailed contracts: `docs/25–28`, `architecture/search_first_journey.json`, `architecture/ai_provider_routing.json`, `architecture/mini_report_schema.json`. These are target specs; providers NOT YET CONFIGURED.

**CANONICAL 25 OCT 2026 OVERRIDE: PUBLIC SEARCH → VERIFIED SITE RESEARCH → SOURCED MINI-REPORT → CREATE ACCOUNT → SAVE/CLAIM REPORT → OPTIONAL PROVIDERS (SHOPIFY) → SOURCED LEADS & GOVERNED ACTIONS. Shopify is NOT required to use Ayo, and public assessment precedes signup. Read `docs/25_SEARCH_FIRST_DISCOVERY_TO_SIGNUP_CANONICAL.md`. Every available feature remains FREE to the first 500 USER accounts. Gemini is a provisional primary engine; Claude is an optional adapter pending evaluations. None of this newly specified workflow is live in the current alpha.**

**Founding access rule (founder-confirmed 25 Oct 2026): ALL AVAILABLE FEATURES ARE FREE FOR THE FIRST 500 DISTINCT CUSTOMER USERS (ACCOUNTS), not 500 businesses. There are NO feature paywalls, operator tiers or paid add-ons for their Ayo capabilities, including features shipped later. Preserve founding-user entitlement across their authorized workspaces. Safety/anti-abuse safeguards and independently disclosed external provider fees are not permission to silently add an Ayo feature paywall. No automatic expiration or billing is authorized; lifetime contractual wording remains a founder/legal decision. See `docs/09_LAUNCH_AND_FREE_500_POLICY.md`.**

# Ayo Africa-first Codex package — manifest

Date: 25 October 2026. **Private GitHub push not yet performed**; account `drippyxx12` has no accessible installed GitHub repository in the connected tool. This package is deliberately unpacked-at-root friendly.

## Build truth
- Existing FastAPI/Jinja/SQLite-local/SQLAlchemy standalone Shopify alpha is included (`ayo/app.py`).
- Existing unit tests for mocked Shopify flows are included; no authorized merchant Shopify installation has occurred.
- `ayo/website_research.py` has pure, non-network URL classification/normalization and local HTML observation extraction. It does **not** fetch remote websites or perform live lead search.
- `tests/test_architecture_contracts.py` checks design contract coherence, **not** successful external integrations.
- None of the discovered leads, outreach sending, payment adapters, public search, web crawling or sales tracking is currently live.

## Codex architecture sequence
- `START_CODEX_HERE.md` => founder intent / first PRs.
- `FOUNDER_BRIEF.md` and `AGENTS.md` => founder constraints and hard safety rules.
- `docs/00–10` => existing app product/security, Shopify connection scope and accepted-release gates.
- `docs/11–17` => public web intelligence, layered reference architecture, data models, preliminary Codex phase playbook and repo handoff.
- `docs/18–24` => country-aware NG/GH priorities, full site search/research, cited real lead pipeline, payment localization, implementation gates, and binding FREE FIRST 500 USERS rule.
- `architecture/country_capabilities.json` => proposed merchant-country profiles. `architecture/skill_registry.json` => scoped planned tool capabilities. `architecture/specimen_api_contracts.json` => non-live API shapes.

## Required external setup
Private repo under the correct GitHub account with installed connector; historical Emergent code review; Shopify developer app credentials and approved store install; search API provider and lawful use terms; secured public-network crawler egress; provider messaging and verified consent/authorization; staging HTTPS and managed DB; legal/compliance checks before contact data or marketing execution.

**Do not confuse architecture presence with shipped features or verified outcomes.**
