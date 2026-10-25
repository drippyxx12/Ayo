# Local implementation evidence — 25 October 2026

## Scope

Imported the original ZIP, established a reproducible baseline, corrected selected security/data-integrity gaps, added CI checks and implemented docs/28 Iteration 1 public acquisition intake. No public deployment, source push, provider grant or external merchant write occurred.

The original archive ran **37 tests**, all passing. After this slice, **79 tests pass**: 21 public-intake tests and 21 security regressions were added. Tests use isolated SQLite and mocked Shopify, not a live development store or PostgreSQL. One existing Starlette/httpx deprecation warning remains.

## Commands and observed results

| Check | Result |
| --- | --- |
| Python 3.12 clean venv, `pip install --require-hashes -r requirements.lock` | Passed; pins and hashes verified |
| `python -m pip check` | No broken requirements found |
| `python -m pytest -q` | 79 passed, 1 upstream deprecation warning |
| `python -m ruff check .` | All checks passed; correctness rule subset defined in pyproject.toml |
| `python -m pip_audit --require-hashes -r requirements.lock` | No known vulnerabilities found at check time |
| `sh scripts/check-secrets.sh` | Gitleaks 8.30.0 working-tree and history scans: no leaks found |
| `git diff --check` | Passed |

Original dependency resolution selected cryptography 48.0.1, for which the audit reported PYSEC-2026-3552, PYSEC-2026-3553 and PYSEC-2026-3554. The new lock pins 50.0.2; Fernet and app regressions pass after upgrading. Audit results are time-bound and do not guarantee absence of vulnerabilities.

CI definitions use read-only repository permissions and verified pinned upstream action commits. They have not been run on GitHub. Runtime lock and secret-download helper were tested on Linux x64/Python 3.12; other platforms require validation.

## Browser → route → service → response

The story is an anonymous visitor entering a name/public URL or a no-website description, receiving a truthful availability/profile page, and optionally proceeding to account creation. The pure intake service performs no network requests or persistence; the no-fetch and no-save boundaries are tested. Signup and ownership/report claim are separate, unfinished milestones.

Local Chromium/Playwright exercised actual forms against Uvicorn at `127.0.0.1:8000`, using temporary SQLite and ephemeral development secrets. No external providers were configured.

| Viewport | Homepage | Name search | Owner-provided profile | Layout / page errors |
| --- | --- | --- | --- | --- |
| 390 × 844 | 200 | 503 search_not_configured | 200 owner_provided_unverified | No horizontal overflow; no page errors |
| 768 × 1024 | 200 | 503 search_not_configured | 200 owner_provided_unverified | No horizontal overflow; no page errors |
| 1440 × 1000 | 200 | 503 search_not_configured | 200 owner_provided_unverified | No horizontal overflow; no page errors |

The 503 response is deliberate: no live search provider exists. URL integration tests likewise return `secure_fetch_not_configured`. No completed research/report is advertised. Profile text is escaped, marked unverified, and not stored in a cookie or workspace. Returning to the homepage clears the visible form. Dynamic responses carry private/no-store headers.

Browser screenshots and machine-readable results are saved locally under `/workspace/ayo-evidence/`; they contain only explicit test inputs. The mobile screenshot was visually inspected. These are development artifacts, not live research receipts.

## Boundaries and remaining work

- Empty/mismatched CSRF values fail closed; login input size is bounded before hashing. This does not implement brute-force protection.
- `/ask` requires a matching current store and snapshot. Dynamic page caching is disabled. Existing insights still use browser-readable signed cookies and must move server-side.
- Invalid/nonfinite/negative/mixed-currency eligible order values fail without replacing the prior snapshot. Currency exponent/refund/settlement reconciliation remains outstanding.
- Public intake does not grant website ownership, save/claim a sourced report, connect Shopify or send messages. Country selection is explicit and optional, limited to NG/GH for this slice.
- No database migration was introduced. `create_all()` and the one-user/one-store model remain; Phase 1 identity/membership requirements are incomplete.
- No credentials were added and no provider calls were made. Search, secure crawling, evidence reports, Gemini/Claude, live Shopify and outreach are **NOT TESTED LIVE**.
- See `RISK_REGISTER.md` for unresolved high-priority session, webhook, OAuth and production gates.

Rollback: revert the development commit to the preceding original-source import. No production data or schema migration needs reversal. Preserve the original ZIP and its source manifest.
