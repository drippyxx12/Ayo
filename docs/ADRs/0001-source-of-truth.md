# ADR 0001: preserve the imported FastAPI alpha

Date: 2026-10-25. Status: accepted for this development slice; original Emergent source remains unavailable.

The accessible source is the founder-supplied ZIP in `drippyxx12/Ayo`, uploaded at commit `9622fa6`. `architecture/source_artifact_manifest.json` records the archive hash and original file hashes. The first local source commit imports its contents unchanged; subsequent commits contain development changes. The ZIP is preserved.

Keep FastAPI, SQLAlchemy, Jinja and the existing test contracts. A framework migration would increase risk without solving the immediate auth, data integrity and public acquisition gaps. Keep routes in the existing module for this increment and put public intake validation in its own pure module. This does not replace or consolidate uninspected historical projects.

The canonical 25 October search-first instructions and docs/25–28 supersede older signup-first and Shopify-first sequencing. The first slice implements public intake and honest unconfigured states; it does not enable fetching, generate a sourced report, or grant ownership. Shopify remains an optional, independently authorized integration.

GitHub currently reports the repository as **public**. The bundled instructions require a private canonical repository. Development can proceed locally, but no new source is published by this slice. Repository visibility is a founder-controlled setting and has not been changed.

Next gates: server-revocable sessions and verified identity, PostgreSQL migrations and memberships, configured search adapter, controlled crawl egress, durable evidence, source-backed mini-report and secure claim. Model routing is provisional under ADR 0002.
