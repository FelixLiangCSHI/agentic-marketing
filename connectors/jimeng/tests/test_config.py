"""Config schema, tenant isolation, forbidden auth and secret absence."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from jimeng_connector import (
    ConnectorConfigError,
    ForbiddenAuthError,
    load_config,
    resolve_runtime,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "jimeng.yaml"

REAL_ENV = {
    "JIMENG_TENANT_VARIANT": "volcengine_cn",
    "JIMENG_REGION": "cn-north-1",
    "JIMENG_PROJECT_ID": "proj-dev",
    "JIMENG_API_ENDPOINT": "https://visual.volcengine.example",
    "JIMENG_CREATE_PATH": "/v1/images/jobs",
    "JIMENG_STATUS_PATH": "/v1/images/jobs/{job_id}",
    "JIMENG_RESULT_PATH": "/v1/images/jobs/{job_id}/result",
    "JIMENG_AUTH_METHOD": "vendor_signed_request",
    "JIMENG_ACCESS_KEY_ID_SECRET_REF": "secretref://vault/dev/jimeng-ak",
    "JIMENG_SECRET_ACCESS_KEY_SECRET_REF": "secretref://vault/dev/jimeng-sk",
    "JIMENG_BEARER_TOKEN_SECRET_REF": "",
    "JIMENG_MODEL_ID": "jimeng-image-x",
    "JIMENG_MAX_IMAGES_PER_REQUEST": "4",
    "JIMENG_RPM": "30",
    "JIMENG_JOBS_PER_DAY": "100",
    "JIMENG_MAX_CONCURRENCY": "2",
    "JIMENG_PER_RUN_BUDGET": "2.0",
    "JIMENG_DAILY_BUDGET": "20.0",
    "JIMENG_MAX_ASSETS_PER_RUN": "8",
    "DMT_HTTPS_PROXY": "http://proxy.internal:3128",
    "JIMENG_ALLOWED_FQDNS": "visual.volcengine.example",
    "DMT_GENERATED_ASSET_BUCKET_REF": "secretref://vault/dev/generated-bucket",
}


def _write(tmp_path: Path, mutate: dict[str, object]) -> Path:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw.update(mutate)
    path = tmp_path / "jimeng.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


class TestConfigSchema:
    def test_repo_template_loads_with_safe_defaults(self) -> None:
        config = load_config(CONFIG_PATH)
        assert config.enabled is False
        assert config.mode == "mock"
        assert config.model.capability == "image_generation"
        assert config.async_job.callback_webhook_enabled is False
        assert config.auth_method.browser_cookie_auth_forbidden is True
        assert config.retry_strategy.reconcile_job_before_retry_create is True
        assert config.retry_strategy.idempotency_key == "run_id_node_id_input_hash"
        assert config.config_hash().startswith("sha256:")

    def test_unknown_field_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"surprise_field": True})
        with pytest.raises(ConnectorConfigError, match="config invalid"):
            load_config(path)

    def test_webhook_cannot_be_enabled(self, tmp_path: Path) -> None:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        raw["async_job"]["callback_webhook_enabled"] = True
        path = tmp_path / "jimeng.yaml"
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        with pytest.raises(ConnectorConfigError, match="config invalid"):
            load_config(path)

    def test_secret_looking_value_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"endpoint": "AKLTsomethingsecret"})
        with pytest.raises(ConnectorConfigError, match="raw secret"):
            load_config(path)

    def test_repo_config_contains_no_secret_material(self) -> None:
        text = CONFIG_PATH.read_text(encoding="utf-8")
        for marker in ("AKLT", "sk-", "Bearer ", "cookie:", "secret_value"):
            assert marker not in text


class TestRuntimeResolution:
    def test_mock_mode_needs_no_env_or_credentials(self) -> None:
        runtime = resolve_runtime(load_config(CONFIG_PATH), {})
        assert runtime.mode == "mock"
        assert runtime.auth is None
        assert runtime.endpoint is None

    def test_live_mode_blocked_when_disabled(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "live"})
        with pytest.raises(ConnectorConfigError, match="enabled=true"):
            resolve_runtime(load_config(path), REAL_ENV)

    def test_live_mode_requires_every_env_value(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "live", "enabled": True})
        config = load_config(path)
        required = [k for k in REAL_ENV if REAL_ENV[k]]
        for missing in required:
            env = {k: v for k, v in REAL_ENV.items() if k != missing}
            with pytest.raises((ConnectorConfigError, ForbiddenAuthError)):
                resolve_runtime(config, env)

    def test_sandbox_resolves_with_full_env(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        runtime = resolve_runtime(load_config(path), REAL_ENV)
        assert runtime.tenant_variant == "volcengine_cn"
        assert runtime.auth is not None
        assert runtime.auth.auth_type == "vendor_signed_request"
        assert runtime.auth.access_key_id_ref == "secretref://vault/dev/jimeng-ak"

    def test_cn_and_global_tenant_must_not_mix(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {**REAL_ENV, "JIMENG_TENANT_VARIANT": "byteplus_global"}  # cn-north-1 region
        with pytest.raises(ConnectorConfigError, match="must not mix"):
            resolve_runtime(load_config(path), env)

    def test_cookie_auth_is_immediate_fail(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {**REAL_ENV, "JIMENG_AUTH_METHOD": "cookie"}
        with pytest.raises(ForbiddenAuthError, match="FAIL"):
            resolve_runtime(load_config(path), env)

    def test_unofficial_auth_method_is_fail(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {**REAL_ENV, "JIMENG_AUTH_METHOD": "reverse_proxy_token"}
        with pytest.raises(ForbiddenAuthError):
            resolve_runtime(load_config(path), env)

    def test_raw_credentials_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {**REAL_ENV, "JIMENG_ACCESS_KEY_ID_SECRET_REF": "AKLTrawaccesskey"}
        with pytest.raises(ConnectorConfigError, match="secretref"):
            resolve_runtime(load_config(path), env)

    def test_bearer_auth_resolves_with_token_ref(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {
            **REAL_ENV,
            "JIMENG_AUTH_METHOD": "bearer",
            "JIMENG_BEARER_TOKEN_SECRET_REF": "secretref://vault/dev/jimeng-bearer",
        }
        runtime = resolve_runtime(load_config(path), env)
        assert runtime.auth is not None
        assert runtime.auth.auth_type == "bearer"
        assert runtime.auth.bearer_token_ref == "secretref://vault/dev/jimeng-bearer"
        assert runtime.auth.access_key_id_ref is None


class TestEndpointGuard:
    def test_http_endpoint_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {**REAL_ENV, "JIMENG_API_ENDPOINT": "http://visual.volcengine.example"}
        with pytest.raises(ConnectorConfigError, match="https"):
            resolve_runtime(load_config(path), env)

    def test_endpoint_host_not_in_allowlist_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {**REAL_ENV, "JIMENG_API_ENDPOINT": "https://attacker.example"}
        with pytest.raises(ConnectorConfigError, match="allowlist"):
            resolve_runtime(load_config(path), env)
