**Founding access rule (founder-confirmed 25 Oct 2026): ALL AVAILABLE FEATURES ARE FREE FOR THE FIRST 500 DISTINCT CUSTOMER USERS (ACCOUNTS), not 500 businesses. There are NO feature paywalls, operator tiers or paid add-ons for their Ayo capabilities, including features shipped later. Preserve founding-user entitlement across their authorized workspaces. Safety/anti-abuse safeguards and independently disclosed external provider fees are not permission to silently add an Ayo feature paywall. No automatic expiration or billing is authorized; lifetime contractual wording remains a founder/legal decision. See `docs/09_LAUNCH_AND_FREE_500_POLICY.md`.**

# Engineering enforcement

See `docs/09_LAUNCH_AND_FREE_500_POLICY.md` and `architecture/founding_500_entitlements.json`. Implement user-based, transactional founding-cohort grants, a server-side entitlement resolver and regression tests for feature access, newly launched capabilities, multiple authorized workspaces and 499/500/501 concurrency. Founding users must not see paid upgrade prompts. Do not use a merchant/business count. Provider authorization, platform availability, abuse and safety checks still apply.

**NOT IMPLEMENTED:** This file is requirements only.
