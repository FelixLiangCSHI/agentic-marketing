"""Jimeng connector configuration: non-sensitive YAML + env indirection.

Mirrors the parent-plan ``config/jimeng.yaml`` template. Rules:
- ``enabled: false`` / ``mode: mock`` defaults; unknown fields rejected.
- Credentials are only ever ``secretref://`` references resolved through
  :class:`infra_core.secrets.SecretResolver`; raw values fail validation.
- CN and global tenants must not mix: the tenant variant fixes which
  region prefix is acceptable, checked at resolution time.
- Cookie/browser auth is forbidden by schema (``Literal[True]``) and any
  non-official auth method value is an immediate typed FAIL.
- sandbox/live must resolve tenant, endpoint, operations, auth, model,
  quotas, budgets, proxy and FQDN allowlist — anything missing is a typed
  startup failure, never a silent fallback to mock.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, ValidationError

from infra_core.secrets import SecretRef, SecretRefFormatError
from jimeng_connector.errors import ConnectorConfigError, ForbiddenAuthError

Mode = Literal["mock", "sandbox", "live"]
TenantVariant = Literal["volcengine_cn", "byteplus_global", "approved_enterprise_gateway"]
AuthType = Literal["vendor_signed_request", "bearer"]

_SECRET_LOOKING_PREFIXES = ("sk-", "Bearer ", "AKIA", "ghp_", "xoxb-", "AKLT")

#: Tenant variant -> allowed region prefixes.区域与租户绑定，禁止混用。
_TENANT_REGION_PREFIXES: Mapping[str, tuple[str, ...]] = {
    "volcengine_cn": ("cn-",),
    "byteplus_global": ("ap-", "eu-", "us-"),
    "approved_enterprise_gateway": ("gw-",),
}


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TenantConfig(_Section):
    variant_env: StrictStr
    region_env: StrictStr
    project_env: StrictStr


class OperationsConfig(_Section):
    create_path_env: StrictStr
    status_path_env: StrictStr
    result_path_env: StrictStr


class AuthMethodConfig(_Section):
    type_env: StrictStr
    access_key_id_secret_ref_env: StrictStr
    secret_access_key_secret_ref_env: StrictStr
    bearer_token_secret_ref_env: StrictStr
    session_token_secret_ref_env: StrictStr
    send_from_server_only: Literal[True]
    browser_cookie_auth_forbidden: Literal[True]


class ModelConfig(_Section):
    model_id_env: StrictStr
    capability: Literal["image_generation"]
    output_formats: tuple[Literal["png", "jpeg", "webp"], ...]
    max_images_per_request_env: StrictStr


class AsyncJobConfig(_Section):
    enabled: Literal[True]
    poll_interval_ms: Annotated[StrictInt, Field(ge=1)]
    max_poll_interval_ms: Annotated[StrictInt, Field(ge=1)]
    max_duration_ms: Annotated[StrictInt, Field(ge=1)]
    persist_job_id: Literal[True]
    resume_after_worker_restart: Literal[True]
    callback_webhook_enabled: Literal[False]


class TimeoutsConfig(_Section):
    connect_ms: Annotated[StrictInt, Field(ge=1)]
    create_request_ms: Annotated[StrictInt, Field(ge=1)]
    status_request_ms: Annotated[StrictInt, Field(ge=1)]
    download_ms: Annotated[StrictInt, Field(ge=1)]


class RateLimitConfig(_Section):
    requests_per_minute_env: StrictStr
    jobs_per_day_env: StrictStr
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
    reconcile_job_before_retry_create: Literal[True]
    idempotency_key: Literal["run_id_node_id_input_hash"]


class NetworkConfig(_Section):
    proxy_url_env: StrictStr
    allowed_fqdns_env: StrictStr
    direct_internet_egress_allowed: Literal[False]
    tls_verify: Literal[True]
    webhook_required: Literal[False]


class StorageConfig(_Section):
    import_result_to_object_store: Literal[True]
    result_bucket_ref_env: StrictStr
    verify_mime: Literal[True]
    malware_scan: Literal[True]
    preserve_provider_response_hash: Literal[True]
    provider_url_max_ttl_seconds: Annotated[StrictInt, Field(ge=1)]


class CostControlConfig(_Section):
    per_run_budget_env: StrictStr
    daily_budget_env: StrictStr
    max_assets_per_run_env: StrictStr
    alert_at_percent: Annotated[StrictInt, Field(ge=1, le=99)]
    stop_at_percent: Literal[100]


class DataHandlingConfig(_Section):
    allowed_classifications: tuple[StrictStr, ...]
    redact_pii: Literal[True]
    log_prompt: Literal[False]
    log_result_url: Literal[False]
    provider_training_opt_out_required: Literal[True]
    retention_policy_must_be_approved: Literal[True]


class FaultInjectionConfig(_Section):
    enabled_env: StrictStr
    timeout_rate_env: StrictStr
    rate_limit_rate_env: StrictStr
    failed_job_rate_env: StrictStr
    malformed_result_rate_env: StrictStr


class MockConfig(_Section):
    fixture_dir: StrictStr
    deterministic_seed: StrictInt
    create_latency_ms: Annotated[StrictInt, Field(ge=0)]
    complete_after_polls: Annotated[StrictInt, Field(ge=1)]
    validate_request_schema: Literal[True]
    generated_asset_fixture: StrictStr
    fault_injection: FaultInjectionConfig


class JimengConfig(_Section):
    """Root of ``config/jimeng.yaml``; non-sensitive by construction."""

    schema_version: Literal["1.0"]
    provider: Literal["jimeng"]
    enabled: StrictBool
    mode: Mode
    tenant: TenantConfig
    endpoint: StrictStr
    operations: OperationsConfig
    auth_method: AuthMethodConfig
    model: ModelConfig
    async_job: AsyncJobConfig
    timeouts: TimeoutsConfig
    rate_limit: RateLimitConfig
    retry_strategy: RetryStrategyConfig
    network: NetworkConfig
    storage: StorageConfig
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


def _check_endpoint(endpoint: str, allowed_fqdns: tuple[str, ...], mode: str) -> None:
    """SSRF guard: real-mode endpoints must be HTTPS on an allowlisted FQDN."""
    parsed = urlparse(endpoint)
    if parsed.scheme != "https":
        raise ConnectorConfigError(
            f"mode={mode} requires an https:// endpoint; got scheme "
            f"{parsed.scheme or 'none'!r}"
        )
    host = parsed.hostname or ""
    if host not in allowed_fqdns:
        raise ConnectorConfigError(
            f"mode={mode} endpoint host {host!r} is not in the FQDN allowlist"
        )


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


def load_config(path: Path) -> JimengConfig:
    """Load and validate the non-sensitive YAML config."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConnectorConfigError(f"config is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConnectorConfigError("config root must be a mapping")
    try:
        config = JimengConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConnectorConfigError(f"config invalid: {exc}") from exc
    for text in _iter_strings(raw):
        _reject_secret_looking(text, "config value")
    return config


class ResolvedAuth(BaseModel):
    """Vendor-specific auth adapter output: references only, no values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    auth_type: AuthType
    access_key_id_ref: StrictStr | None
    secret_access_key_ref: StrictStr | None
    bearer_token_ref: StrictStr | None
    session_token_ref: StrictStr | None


class RuntimeSettings(BaseModel):
    """Env-resolved runtime values for one mode; secret references only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Mode
    tenant_variant: TenantVariant
    region: StrictStr
    project: StrictStr
    endpoint: StrictStr | None
    create_path: StrictStr
    status_path: StrictStr
    result_path: StrictStr
    auth: ResolvedAuth | None
    model_id: StrictStr
    max_images_per_request: Annotated[StrictInt, Field(ge=1)]
    requests_per_minute: Annotated[StrictInt, Field(ge=1)]
    jobs_per_day: Annotated[StrictInt, Field(ge=1)]
    max_concurrency: Annotated[StrictInt, Field(ge=1)]
    per_run_budget: Annotated[float, Field(gt=0.0)]
    daily_budget: Annotated[float, Field(gt=0.0)]
    max_assets_per_run: Annotated[StrictInt, Field(ge=1)]
    proxy_url: StrictStr | None
    allowed_fqdns: tuple[StrictStr, ...]
    result_bucket_ref: StrictStr | None


_MOCK_DEFAULTS: Mapping[str, str] = {
    "JIMENG_TENANT_VARIANT": "volcengine_cn",
    "JIMENG_REGION": "cn-mock-1",
    "JIMENG_PROJECT_ID": "proj-mock",
    "JIMENG_MODEL_ID": "jimeng-image-mock",
    "JIMENG_MAX_IMAGES_PER_REQUEST": "4",
    "JIMENG_RPM": "30",
    "JIMENG_JOBS_PER_DAY": "200",
    "JIMENG_MAX_CONCURRENCY": "2",
    "JIMENG_PER_RUN_BUDGET": "2.00",
    "JIMENG_DAILY_BUDGET": "20.00",
    "JIMENG_MAX_ASSETS_PER_RUN": "8",
    "JIMENG_CREATE_PATH": "/v1/images/jobs",
    "JIMENG_STATUS_PATH": "/v1/images/jobs/{job_id}",
    "JIMENG_RESULT_PATH": "/v1/images/jobs/{job_id}/result",
}


def _require(env: Mapping[str, str], name: str, mode: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConnectorConfigError(
            f"mode={mode} requires environment variable {name}; refusing to start"
        )
    return value


def _resolve_auth(config: JimengConfig, env: Mapping[str, str], mode: str) -> ResolvedAuth:
    auth_type_raw = _require(env, config.auth_method.type_env, mode)
    if auth_type_raw in ("cookie", "browser_cookie", "session_cookie"):
        raise ForbiddenAuthError(
            "browser cookie auth is forbidden; only the official enterprise "
            "API auth (vendor_signed_request | bearer) is allowed — FAIL"
        )
    if auth_type_raw not in ("vendor_signed_request", "bearer"):
        raise ForbiddenAuthError(
            f"auth method {auth_type_raw!r} is not an approved official method — FAIL"
        )
    auth_type: AuthType = auth_type_raw  # type: ignore[assignment]

    def _ref(env_name: str) -> str:
        value = _require(env, env_name, mode)
        try:
            SecretRef.parse(value)
        except SecretRefFormatError as exc:
            raise ConnectorConfigError(
                f"{env_name} must be a secretref:// reference; raw credentials rejected"
            ) from exc
        return value

    if auth_type == "vendor_signed_request":
        session_raw = env.get(config.auth_method.session_token_secret_ref_env, "").strip()
        return ResolvedAuth(
            auth_type=auth_type,
            access_key_id_ref=_ref(config.auth_method.access_key_id_secret_ref_env),
            secret_access_key_ref=_ref(config.auth_method.secret_access_key_secret_ref_env),
            bearer_token_ref=None,
            session_token_ref=(
                _ref(config.auth_method.session_token_secret_ref_env) if session_raw else None
            ),
        )
    return ResolvedAuth(
        auth_type=auth_type,
        access_key_id_ref=None,
        secret_access_key_ref=None,
        bearer_token_ref=_ref(config.auth_method.bearer_token_secret_ref_env),
        session_token_ref=None,
    )


def _check_tenant_region(variant: str, region: str) -> TenantVariant:
    prefixes = _TENANT_REGION_PREFIXES.get(variant)
    if prefixes is None:
        raise ConnectorConfigError(f"unknown tenant variant {variant!r}")
    if not region.startswith(prefixes):
        raise ConnectorConfigError(
            f"region {region!r} does not belong to tenant variant {variant!r}; "
            "CN and global tenants must not mix endpoints, credentials or quotas"
        )
    checked: TenantVariant = variant  # type: ignore[assignment]
    return checked


def resolve_runtime(config: JimengConfig, env: Mapping[str, str]) -> RuntimeSettings:
    """Resolve env indirection for the configured mode.

    ``mock`` uses deterministic synthetic defaults and never needs
    credentials. ``sandbox``/``live`` require every value or a typed
    startup failure — no silent fallback.
    """
    mode = config.mode
    if mode == "mock":
        merged = {**_MOCK_DEFAULTS, **{k: v for k, v in env.items() if v.strip()}}
        variant = _check_tenant_region(
            merged["JIMENG_TENANT_VARIANT"], merged["JIMENG_REGION"]
        )
        return RuntimeSettings(
            mode=mode,
            tenant_variant=variant,
            region=merged["JIMENG_REGION"],
            project=merged["JIMENG_PROJECT_ID"],
            endpoint=None,
            create_path=merged["JIMENG_CREATE_PATH"],
            status_path=merged["JIMENG_STATUS_PATH"],
            result_path=merged["JIMENG_RESULT_PATH"],
            auth=None,
            model_id=merged["JIMENG_MODEL_ID"],
            max_images_per_request=int(merged["JIMENG_MAX_IMAGES_PER_REQUEST"]),
            requests_per_minute=int(merged["JIMENG_RPM"]),
            jobs_per_day=int(merged["JIMENG_JOBS_PER_DAY"]),
            max_concurrency=int(merged["JIMENG_MAX_CONCURRENCY"]),
            per_run_budget=float(merged["JIMENG_PER_RUN_BUDGET"]),
            daily_budget=float(merged["JIMENG_DAILY_BUDGET"]),
            max_assets_per_run=int(merged["JIMENG_MAX_ASSETS_PER_RUN"]),
            proxy_url=None,
            allowed_fqdns=(),
            result_bucket_ref=None,
        )

    if not config.enabled:
        raise ConnectorConfigError(
            f"mode={mode} requires enabled=true after human approval; refusing to start"
        )
    variant = _check_tenant_region(
        _require(env, config.tenant.variant_env, mode),
        _require(env, config.tenant.region_env, mode),
    )
    endpoint = _require(env, "JIMENG_API_ENDPOINT", mode)
    _reject_secret_looking(endpoint, "JIMENG_API_ENDPOINT")
    allowed = tuple(
        fqdn.strip()
        for fqdn in _require(env, config.network.allowed_fqdns_env, mode).split(",")
        if fqdn.strip()
    )
    if not allowed:
        raise ConnectorConfigError(f"mode={mode} requires a non-empty FQDN allowlist")
    _check_endpoint(endpoint, allowed, mode)
    bucket_ref = _require(env, config.storage.result_bucket_ref_env, mode)
    try:
        SecretRef.parse(bucket_ref)
    except SecretRefFormatError as exc:
        raise ConnectorConfigError(
            f"{config.storage.result_bucket_ref_env} must be a secretref:// reference"
        ) from exc
    return RuntimeSettings(
        mode=mode,
        tenant_variant=variant,
        region=_require(env, config.tenant.region_env, mode),
        project=_require(env, config.tenant.project_env, mode),
        endpoint=endpoint,
        create_path=_require(env, config.operations.create_path_env, mode),
        status_path=_require(env, config.operations.status_path_env, mode),
        result_path=_require(env, config.operations.result_path_env, mode),
        auth=_resolve_auth(config, env, mode),
        model_id=_require(env, config.model.model_id_env, mode),
        max_images_per_request=int(_require(env, config.model.max_images_per_request_env, mode)),
        requests_per_minute=int(_require(env, config.rate_limit.requests_per_minute_env, mode)),
        jobs_per_day=int(_require(env, config.rate_limit.jobs_per_day_env, mode)),
        max_concurrency=int(_require(env, config.rate_limit.max_concurrency_env, mode)),
        per_run_budget=float(_require(env, config.cost_control.per_run_budget_env, mode)),
        daily_budget=float(_require(env, config.cost_control.daily_budget_env, mode)),
        max_assets_per_run=int(_require(env, config.cost_control.max_assets_per_run_env, mode)),
        proxy_url=_require(env, config.network.proxy_url_env, mode),
        allowed_fqdns=allowed,
        result_bucket_ref=bucket_ref,
    )
