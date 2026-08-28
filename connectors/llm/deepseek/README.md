# deepseek-connector

Phase 02 / Subphase 04 — DeepSeek LLM connector with a unified interface,
deterministic mock, normalized errors, local rate limiting and cost gates.

## Boundaries

- **Repo / normal CI**: `mode: mock` only. The package ships no real HTTP
  client; every test runs against deterministic fixtures — zero external
  HTTP, zero secrets.
- **DEV**: real `sandbox`/`live` calls only run in the protected pipeline
  (self-hosted runner, proxy + FQDN allowlist, Secret Resolver) after
  enterprise LLM approval is recorded. `scripts/dev_smoke.py` refuses to
  run without `DEEPSEEK_DEV_APPROVAL_EVIDENCE`.
- The API key is only ever a `secretref://` reference
  (`infra_core.secrets`); raw keys in config or env fail validation.

## Unified interface

`DeepSeekConnector`: `validate_config` / `dry_run` / `execute` /
`get_status` / `reconcile` / `cancel` (both return `NOT_SUPPORTED` —
chat is synchronous) / `normalize_error` (maps every failure onto the
frozen `connector-error.v1` contract).

Governance: connect/request/total timeouts, local RPM + max-concurrency
queue, per-run/daily budgets (alert at 80%, hard stop at 100%), bounded
exponential backoff + jitter for 408/429/5xx/timeout honoring
`Retry-After`; schema/auth 4xx are never blindly retried. The journal
records request hash, model/prompt/config versions, tokens and cost —
never bodies or secrets.

## Content Workflow bridge

`DeepSeekContentModel` implements the `ContentModel` protocol of
`packages/content-workflow`, so `GenerateCopy` can switch between the
fake model and the DeepSeek connector without graph changes.
Model-returned citations are untrusted: claims may only reference RAG
facts by `chunk_hash`; unknown references become uncited claims, which
compliance blocks.

## Commands

```bash
pip install -e packages/product-rag -e packages/harness-core \
  -e packages/infra-core -e packages/content-workflow \
  -e "connectors/llm/deepseek[dev]"
cd connectors/llm/deepseek
python3 -m pytest        # 36 tests, all deterministic mock
python3 -m mypy          # strict
python3 -m mypy tests
```

Configuration lives in `config/deepseek.yaml` (non-sensitive template;
`enabled: false`, `mode: mock` by default).
