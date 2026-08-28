"""DeepSeek connector configuration: non-sensitive YAML + env indirection.

Mirrors the parent-plan ``config/deepseek.yaml`` template. The YAML holds
only structure and env-variable *names*; endpoint, model, quota, proxy and
the secret *reference* are resolved from the environment at startup.

Rules enforced here:
- ``enabled: false`` and ``mode: mock`` are the defaults.
- Unknown fields anywhere are rejected.
- The API key is never present: only a ``secretref://`` reference resolved
  through :class:`infra_core.secrets.SecretResolver`; raw secret-looking
  values in config or env fail validation.
- ``sandbox``/``live`` must resolve endpoint, model, quota, proxy,
  FQDN allowlist and the secret reference; anything missing is a typed
  startup failure (never a silent fallback to mock).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, ValidationError

from deepseek_connector.errors import ConnectorConfigError
from infra_core.secrets import SecretRef, SecretRefFormatError

Mode = Literal["mock", "sandbox", "live"]

_SECRET_LOOKING_PREFIXES = ("sk-", "Bearer ", "AKIA", "ghp_", "xoxb-")


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthMethodConfig(_Section):
    type: Literal["bearer"]
    api_key_secret_ref_env: StrictStr
    send_from_server_only: Literal[True]


class ModelsConfig(_Section):
    chat_model_env: StrictStr
    temperature: Annotated[float, Field(ge=0.0, le=2.0)]
    max_output_tokens_env: StrictStr


class TimeoutsConfig(_Section):
    connect_ms: Annotated[StrictInt, Field(ge=1)]
    request_ms: Annotated[StrictInt, Field(ge=1)]
    total_workflow_ms: Annotated[StrictInt, Field(ge=1)]


class RateLimitConfig(_Section):
    requests_per_minute_env: StrictStr
    tokens_per_minute_env: StrictStr
    max_concurrency_env: StrictStr
    local_queue: StrictBool
    fail_when_quota_unknown_in_live: Literal[True]


class RetryStrategyConfig(_Section):
    policy: Literal["exponential_backoff_with_jitter"]
    max_attempts: Annotated[StrictInt, Field(ge=1, le=10)]
    initial_delay_ms: Annotated[StrictInt, Field(ge=1)]
    max_delay_ms: Annotated[StrictInt, Field(ge=1)]
    multiplier: Annotated[float, Field(ge=1.0)]
    honor_retry_after: Literal[True]
    retry_http_statuses: tuple[StrictInt, ...]
    do_not_retry_http_statuses: tuple[StrictInt, ...]
    retry_requires_same_request_hash: Literal[True]


class NetworkConfig(_Section):
    proxy_url_env: StrictStr
    allowed_fqdns_env: StrictStr
    direct_internet_egress_allowed: Literal[False]
    tls_verify: Literal[True]


class CostControlConfig(_Section):
    per_run_budget_env: StrictStr
    daily_budget_env: StrictStr
    stop_at_percent: Literal[100]
    alert_at_percent: Annotated[StrictInt, Field(ge=1, le=99)]


class DataHandlingConfig(_Section):
    allowed_classifications: tuple[StrictStr, ...]
    redact_pii: Literal[True]
    log_request_body: Literal[False]
    log_response_body: Literal[False]
    record_prompt_version: Literal[True]
    record_model_version: Literal[True]


class FaultInjectionConfig(_Section):
    enabled_env: StrictStr
    timeout_rate_env: StrictStr
    rate_limit_rate_env: StrictStr
    server_error_rate_env: StrictStr


class MockConfig(_Section):
    fixture_dir: StrictStr
    deterministic_seed: StrictInt
    latency_ms: Annotated[StrictInt, Field(ge=0)]
    validate_request_schema: Literal[True]
    fault_injection: FaultInjectionConfig


class DeepSeekConfig(_Section):
    """Root of ``config/deepseek.yaml``; non-sensitive by construction."""

    schema_version: Literal["1.0"]
    provider: Literal["deepseek"]
    enabled: StrictBool
    mode: Mode
    endpoint: StrictStr
    api_path: StrictStr
    auth_method: AuthMethodConfig
    models: ModelsConfig
    timeouts: TimeoutsConfig
    rate_limit: RateLimitConfig
    retry_strategy: RetryStrategyConfig
    network: NetworkConfig
    cost_control: CostControlConfig
    data_handling: DataHandlingConfig
    mock: MockConfig

    def config_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reject_secret_looking(value: str, where: str) -> None:
    if any(value.startswith(prefix) for prefix in _SECRET_LOOKING_PREFIXES):
        raise ConnectorConfigError(
            f"{where} looks like a raw secret; only secretref:// references are allowed"
        )


def load_config(path: Path) -> DeepSeekConfig:
    """Load and validate the non-sensitive YAML config."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConnectorConfigError(f"config is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConnectorConfigError("config root must be a mapping")
    try:
        config = DeepSeekConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConnectorConfigError(f"config invalid: {exc}") from exc
    for text in _iter_strings(raw):
        _reject_secret_looking(text, "config value")
    return config


def _iter_strings(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, str):
        found.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            found.extend(_iter_strings(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_iter_strings(value))
    return found


class RuntimeSettings(BaseModel):
    """Env-resolved runtime values for one mode. Holds the secret
    *reference* only; the value stays inside the resolver."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Mode
    endpoint: StrictStr | None
    api_path: StrictStr
    chat_model: StrictStr
    max_output_tokens: Annotated[StrictInt, Field(ge=1)]
    temperature: float
    requests_per_minute: Annotated[StrictInt, Field(ge=1)]
    tokens_per_minute: Annotated[StrictInt, Field(ge=1)]
    max_concurrency: Annotated[StrictInt, Field(ge=1)]
    per_run_budget: Annotated[float, Field(gt=0.0)]
    daily_budget: Annotated[float, Field(gt=0.0)]
    proxy_url: StrictStr | None
    allowed_fqdns: tuple[StrictStr, ...]
    api_key_ref: StrictStr | None


_MOCK_DEFAULTS: Mapping[str, str] = {
    "DEEPSEEK_CHAT_MODEL": "deepseek-chat-mock",
    "DEEPSEEK_MAX_OUTPUT_TOKENS": "2048",
    "DEEPSEEK_RPM": "60",
    "DEEPSEEK_TPM": "100000",
    "DEEPSEEK_MAX_CONCURRENCY": "2",
    "DEEPSEEK_PER_RUN_BUDGET": "1.00",
    "DEEPSEEK_DAILY_BUDGET": "10.00",
}


def _require(env: Mapping[str, str], name: str, mode: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConnectorConfigError(
            f"mode={mode} requires environment variable {name}; refusing to start"
        )
    return value


def resolve_runtime(config: DeepSeekConfig, env: Mapping[str, str]) -> RuntimeSettings:
    """Resolve env indirection for the configured mode.

    ``mock`` uses deterministic synthetic defaults (overridable via env)
    and never needs credentials. ``sandbox``/``live`` require every value
    and a valid ``secretref://`` API-key reference or startup fails.
    """
    mode = config.mode
    if mode == "mock":
        merged = {**_MOCK_DEFAULTS, **{k: v for k, v in env.items() if v.strip()}}
        return RuntimeSettings(
            mode=mode,
            endpoint=None,
            api_path=config.api_path,
            chat_model=merged["DEEPSEEK_CHAT_MODEL"],
            max_output_tokens=int(merged["DEEPSEEK_MAX_OUTPUT_TOKENS"]),
            temperature=config.models.temperature,
            requests_per_minute=int(merged["DEEPSEEK_RPM"]),
            tokens_per_minute=int(merged["DEEPSEEK_TPM"]),
            max_concurrency=int(merged["DEEPSEEK_MAX_CONCURRENCY"]),
            per_run_budget=float(merged["DEEPSEEK_PER_RUN_BUDGET"]),
            daily_budget=float(merged["DEEPSEEK_DAILY_BUDGET"]),
            proxy_url=None,
            allowed_fqdns=(),
            api_key_ref=None,
        )

    if not config.enabled:
        raise ConnectorConfigError(
            f"mode={mode} requires enabled=true after human approval; refusing to start"
        )
    endpoint = _require(env, "DEEPSEEK_API_ENDPOINT", mode)
    _reject_secret_looking(endpoint, "DEEPSEEK_API_ENDPOINT")
    api_key_ref = _require(env, config.auth_method.api_key_secret_ref_env, mode)
    try:
        SecretRef.parse(api_key_ref)
    except SecretRefFormatError as exc:
        raise ConnectorConfigError(
            f"{config.auth_method.api_key_secret_ref_env} must be a secretref:// "
            "reference; raw API keys are rejected"
        ) from exc
    proxy_url = _require(env, config.network.proxy_url_env, mode)
    allowed = tuple(
        fqdn.strip()
        for fqdn in _require(env, config.network.allowed_fqdns_env, mode).split(",")
        if fqdn.strip()
    )
    if not allowed:
        raise ConnectorConfigError(f"mode={mode} requires a non-empty FQDN allowlist")
    return RuntimeSettings(
        mode=mode,
        endpoint=endpoint,
        api_path=config.api_path,
        chat_model=_require(env, config.models.chat_model_env, mode),
        max_output_tokens=int(_require(env, config.models.max_output_tokens_env, mode)),
        temperature=config.models.temperature,
        requests_per_minute=int(_require(env, config.rate_limit.requests_per_minute_env, mode)),
        tokens_per_minute=int(_require(env, config.rate_limit.tokens_per_minute_env, mode)),
        max_concurrency=int(_require(env, config.rate_limit.max_concurrency_env, mode)),
        per_run_budget=float(_require(env, config.cost_control.per_run_budget_env, mode)),
        daily_budget=float(_require(env, config.cost_control.daily_budget_env, mode)),
        proxy_url=proxy_url,
        allowed_fqdns=allowed,
        api_key_ref=api_key_ref,
    )
