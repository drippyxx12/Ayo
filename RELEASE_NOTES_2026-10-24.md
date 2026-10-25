# Release notes — Founder-aligned Ayo Codex handoff (24 Oct 2026)

**What this archive IS:** original FastAPI/SQLAlchemy/Jinja alpha source plus historical audits and new founder-aligned product/engineering requirements. ZIP is not a deployed service. No external merchant Shopify OAuth install has been verified by Ayo. Original automated tests use mocked Shopify responses.

**What changed from the previous Shopify-verified ZIP:**

- Added `FOUNDER_BRIEF.md` (founder confirmed versus proposal distinction; Ayo brand independence).
- Added `docs/07_AYO_V1_PRODUCT_REQUIREMENTS.md` (actual merchant journeys, capabilities and explicit acceptance tests).
- Added `docs/08_UNIFIED_INTELLIGENCE_AND_ACTION_CONTRACTS.md` (single Ayo orchestration, skills and real write policy).
- Added `docs/09_LAUNCH_AND_FREE_500_POLICY.md` (first-500 early-access strategy with transparent caps; terms not final).
- Added `docs/10_CODEX_DELIVERY_GATES.md` (updated build order and Codex prompt; no fake completion).
- Added product alignment notices at the top of the old README, AGENTS.md, CODEX_BUILD_TASK.md and docs 00, 02, 03, 05 to resolve contradictions without erasing older audit history.
- **No application code changed** from the prior archive. Engineering requirements have been upgraded; production features described here are not yet implemented.

**Next action:** Place on private GitHub, restore/cross-check canonical Emergent implementation, run Codex per docs/10, then create and test the Ayo Shopify developer app in an authorized test store. Do not copy the ChatGPT Shopify connector token into Ayo or imply it authorizes Ayo OAuth.
