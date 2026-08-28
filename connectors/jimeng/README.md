# jimeng-connector

Phase 02 / Subphase 05 — official enterprise Jimeng media (image)
connector: async jobs, durable-queue polling, object-store import and a
deterministic mock. **Only the official enterprise API** (Volcengine CN /
BytePlus global / approved enterprise gateway) — cookies, reverse-
engineered endpoints or third-party proxy resellers are forbidden and any
such auth value is an immediate typed `ForbiddenAuthError` (FAIL).

## Boundaries

- **Repo / normal CI**: `mode: mock` only. No real HTTP client exists in
  this package; the deterministic `JimengMockTransport` simulates the
  full async lifecycle (create → poll → result URL → download) plus fault
  scenarios. Zero external HTTP, zero secrets.
- **DEV**: real `sandbox`/`live` calls only via the protected pipeline
  after vendor/procurement, region/tenant, auth and data
  retention/training policies are confirmed. `scripts/dev_smoke.py`
  refuses without `JIMENG_DEV_APPROVAL_EVIDENCE`; the connector
  constructor refuses non-mock modes without an approval reference.
- Credentials are only ever `secretref://` references (AK/SK for
  vendor-signed requests, or a bearer token); raw values fail validation.
- CN (`volcengine_cn`, `cn-*`) and global (`byteplus_global`,
  `ap-/eu-/us-*`) tenants must not mix endpoints, credentials or quotas —
  enforced at runtime resolution.

## Async job model

`execute` creates the provider job (idempotency key =
`run_id_node_id_input_hash`) and enqueues a poll task on the durable
queue (`infra_core.queue`); any worker instance sharing the same job
store + queue continues after a restart. Guarantees:

- duplicate submits (100×) never create a second provider job;
- create timeout reconciles via `find_job` before any retry-create;
- expired temporary result URLs re-fetch the result reference — the job
  is never recreated;
- unknown provider jobs stop the pipeline: `NEEDS_RECONCILE` + DLQ for
  human reconciliation, never a fresh create;
- no public webhook (`callback_webhook_enabled: false`) — polling only.

Downloaded assets are validated (TLS, MIME allowlist, size, provider
hash match, synthetic malware scan) before import into the *generated*
object-store area; promotion copies into the separate *approved* area.
Object versions are immutable — modifications always create new versions.

Governance: local RPM/concurrency/jobs-per-day limits and per-run/daily
budgets with a per-run asset cap (alert at 80%, stop at 100%) are checked
before any create call. Logs and errors never contain prompts, result
URLs or secret material.

## Content Workflow bridge

`JimengMediaGenerator` implements the `MediaGenerator` protocol of
`packages/content-workflow`, so `GenerateMedia` can switch between the
fake generator and the Jimeng connector without graph changes. Only the
approved image capability is claimed; other media types raise a typed
`NotSupportedError` — capabilities are never faked.

## Commands

```bash
pip install -e "packages/infra-core" -e "packages/product-rag" \
  -e "packages/harness-core" -e "packages/content-workflow" \
  -e "connectors/jimeng[dev]"
npm run jimeng:test        # pytest (44 tests, all mock)
npm run jimeng:typecheck   # mypy --strict
```

Config template: `config/jimeng.yaml` (non-sensitive, `enabled: false`,
`mode: mock`; real values only via env + secret references in DEV).
