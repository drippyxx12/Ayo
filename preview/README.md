# Restricted development preview

Build a new standalone bundle from whitelisted runtime source and existing labeled offline screenshot evidence:

```sh
python scripts/build-preview.py --evidence-dir /workspace/ayo-evidence --output /workspace/ayo-preview-new
```

This command does not deploy. The output has an in-memory database, forced preview route restrictions, disabled provider spending and email delivery, an ephemeral encryption key, and no copied environment files, tests or private data. Configure a durable session secret securely in the hosting environment. The read-only screen walkthrough clearly identifies all example businesses, sources and leads as offline test fixtures. It is not live research or platform completion evidence.

Vercel requirements are flattened from the hash-pinned lock into `requirements.txt`; no requirements include or project metadata autodetection is used. The deployed entrypoint is root `app.py`. Hosting deployment protection remains a separate required setting; this bundle does not change protection or authorize deployment/spend.
