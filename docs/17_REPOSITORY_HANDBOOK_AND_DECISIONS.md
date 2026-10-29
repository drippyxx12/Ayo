## Additional stage gates as of 2026-10-25
Source repository remains uncreated/unverified under the requested second GitHub account (connector has no create-repository action). **Never claim uploaded or private until GitHub confirms it.** This package's root now contains Codex-readable source plus `AGENTS.md`, `START_CODEX_HERE.md`, docs/11–23 and machine-readable architecture manifests. Website input normalization and local HTML extraction have tests; no real site fetch has been verified. New ADRs: `ADR-011 market country capability verification`, `ADR-012 lead sources/legal and retention`, `ADR-013 provider-backed communications and recorded consents`, `ADR-014 country-aware payment state machine`, `ADR-015 AI lead-scoring evidence threshold and calibration`.

---

# 17 — GitHub / Codex execution handbook and ADRs

## Canonical repository rules
Founder-designated second GitHub account: `drippyxx12`. **As of the 25 Oct 2026 connector check this account has zero visible repositories and zero installed GitHub App installations. A private repository was NOT created, and the code has NOT been pushed.** GitHub connector currently has file/commit tools for existing repos but no create-repository tool. Do not claim upload until a real private repository exists, access is granted, and contents/privacy verified.

Suggested repo name: `ayo` or `ayo-commerce-os` (private). Keep only one canonical repo, preferably with `main` protected and `codex/*` PR branches. The *existing* FastAPI alpha in this package is the only local source currently accessible; the original Emergent project source has not been recovered. Floot/Base44/Lovable/Replit staging projects are independent experiments, not merged into this Git history.

## Git hygiene / secrets
- `.env`, token encryption key files, DB files, cookies, screenshots with tokens, raw Shopify orders/customer exports, crawl contents with personal data, browser sessions and vendor private credentials never committed.
- Include `.env.example` with placeholders only. Use GitHub secret scanning, protected CI environments, dependabot, security advisories, least privilege GitHub permissions.
- A ZIP is not a GitHub push. Extract into local working tree, `git init` if no repo, review `git status` and `.gitignore`, then commit to newly created private GitHub remote. Do NOT upload the ZIP itself as the only repo file; Codex needs unpacked source and AGENTS instructions.

## Codex first action prompt
> Inspect AGENTS.md and FOUNDER_BRIEF.md; read docs/11–17 completely before modifying code. Ayo is a unified e-commerce intelligence platform with two distinct inputs: public website research by search or URL, and separate verified Shopify merchant authorization. Preserve current FastAPI alpha and tests, audit the canonical source, then complete Phase 0 and begin Phase 1 of docs/15_CODEX_PHASE_PLAYBOOK.md. Never seed fictitious merchant revenue or claim any website data were fetched when none were. Write PR-sized changes on codex/* branches, tests and evidence in each PR. Do not deploy or install on external stores without approval. Escalate missing Shopify credentials, egress proxy, search provider or permission rather than simulating success.

## Definition of done per layer
- UX: correct zero-data state, keyboard/mouse/mobile semantics, accessibility and truthful provenance.
- Auth: session boundaries, recovered accounts, MFA plan, secure data deletion and tenant access.
- Research: fetched public page source/robots metadata/evidence, SSRF-resistant network, explicit source count and scan errors, stable API.
- Commerce: real Shopify installation and reconciliation, token vault, exact metric definition and retries.
- AI: approved tool contracts only, citations/confidence and no unauthorized actions.
- Work: explicit approvals, idempotent real provider writes and provider receipts.
- Ops: CI/CD, observability, backups, secure environment, privacy/legal release readiness.

## ADR backlog (must resolve with evidence)
ADR-001 Canonical source (FastAPI starter vs Emergent historical code) — pending original source access.
ADR-002 Website discovery API vendor and licensing — pending search provider, quota/cost evaluation.
ADR-003 Website fetcher controlled egress, DNS pinning and headless rendering — required before URL crawler release.
ADR-004 Research storage and TTL; opt-out robots/terms and deletion rules — pending legal/privacy assessment.
ADR-005 Auth multi-business roles and organization claims — modular implementation required.
ADR-006 Shopify official SDK and token refresh semantics — validate against installed Shopify developer app.
ADR-007 Unified LLM provider + model budget — evaluate cost/country availability and tool security.
ADR-008 Work approvals and first product edit action — confirm founder priorities and live scope.
ADR-009 First 500 USER accounts get ALL released features free — founder-confirmed. Lifetime contractual wording and later-user pricing still require founder/legal decision.
ADR-010 Public company name search vs merchant-verified website distinction — architectural non-negotiable.

## Operational evidence checklist
1. GitHub: exact private repo URL, privacy field, owner login, commit SHA and tree including `AGENTS.md` and `docs/`.
2. Baseline: tests and dependency scan output.
3. Shopify: authorized app/dev-store install and GraphQL read, screen/data reconciliation, webhook receipts.
4. Website: run ID, real public test domain, URLs actually fetched, robot decisions, bounded evidence, no internal/metadata DNS access.
5. Actions: authenticated merchant approval, before/after, provider receipt and duplicate prevention.
6. Costs & privacy: usage billing controls for free cohort, deletion tests, data minimization, retention runbooks.
