# Founder-confirmed decisions since this document was drafted

- **Confirmed:** e-commerce only at first launch; **Shopify first** but other platforms/custom installs later; **one unified Ayo assistant** dynamically coordinating implemented and authorized capabilities; ALL features free for the first **500 distinct legitimate customer users** (not businesses); no paid feature tiers for them; lifetime wording and later pricing remain separate founder decisions; full product ambition and Ayo's own unique positioning.
- **Not confirmed:** exact first three operator tasks, autonomy (recommend Ask-before-acting), specific first real action (catalog listing improvement recommended), Nigerian store-builder timing, detailed pricing and grandfathering.
- The older “pricing discovery”, “narrow read-only V1” language below applies to technical staging and economic validation. **It does not override the founder's free early-access direction or the requirement for a truly functional customer release.** See `../FOUNDER_BRIEF.md`.

# Ayo — product decisions and open questions
The following defaults unblock first implementation. They are proposals unless labeled accepted; confirm with actual merchant evidence and technical constraints.

1. **First niche (proposed):** Nigerian Shopify small/mid-sized retail merchants with sufficient order activity. Target merchants willing to connect development stores and share their own outcomes. We should not assume this is the only segment Ayo will serve.
2. **Initial value (proposed):** Understand sales, product performance and emerging stock risks; trustworthy answers before automated action. This is a reliable first ship even when customer PII/advertising integrations are unavailable.
3. **First dashboard (accepted as build direction):** completely empty until data is authorized and synced. Actual store identity/last sync, exact paid-order amount with clear metric definition, product count, stock and reliable freshness; zero-day/zero-transaction states handled.
4. **Shopify app type (requires validation):** merchant-installable standalone Ayo service, non-embedded initially. Confirm current Shopify distribution review and required approvals for intended audiences.
5. **Architecture (requires source audit):** use existing canonical Emergent app where sound; separate FastAPI alpha for reference. PostgreSQL + worker queue when progressing to external staging; avoid inventing compatibility with React/Next without inspection.
6. **LLM provider (defer):** implement tool contracts for business facts first. Provider choice requires latency, cost, data handling, quality and safety evaluations with realistic test prompts.
7. **Customer follow-up (defer):** do not assume Shopify's customer fields imply marketing permission. The first WhatsApp or email messaging feature needs explicit consent, validated adapter and approved actions.
8. **Revenue model (discovery):** start with invitation-only trials; pricing and tiers should follow merchant willingness-to-pay interviews, operational/API costs and proof of value.
9. **Commercial readiness (hard gate):** no outside merchant personal data in unreviewed staging, no public production release before auth/privacy/correctness checks.
10. **Meaning of a successful prototype:** **genuine working onboarding and authorized store sync**, not fake sample data, clickable-only UI or an AI conversation with invented sales figures.
