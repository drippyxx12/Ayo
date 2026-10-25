# ADR 0002: separate discovery, fetch, models and execution

Date: 2026-10-25. Status: adapter direction accepted; provider selection and live evaluation pending.

Follow docs/26: Gemini is the provisional discovery/synthesis recommendation; Claude is an optional evaluated planning adapter. Neither is configured. A personal model subscription is not an application API credential or authorized budget.

Keep search, controlled content fetch, evidence validation, model inference and action policy as separate boundaries. The public intake module makes no HTTP requests and returns explicit unavailable states. It must not manufacture domains, evidence, lead contacts, or reports to compensate for missing providers. Owner-provided descriptions remain unverified statements.

A future provider adapter must include credential readiness, budget, country/location disambiguation, actual provenance receipts and output validation. A future fetcher must enforce pinned-public-IP egress, redirect checks, robots/terms, time/byte/page limits and isolated workers. URL syntax validation is not SSRF protection. A model cannot bypass these gates or authorize writes.

No vendor API or SDK is selected or billed by this change. Version-specific official documentation and live NG/GH evaluation are required before implementing an adapter. There is no provider execution hidden behind the intake screen.
