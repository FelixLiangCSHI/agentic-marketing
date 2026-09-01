"""Config schema, unknown-field rejection, secret absence and env resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deepseek_connector import (
    ConnectorConfigError,
    load_config,
    resolve_runtime,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = REPO_ROOT / "config" / "deepseek.yaml"

REAL_ENV = {
    "DEEPSEEK_API_ENDPOINT": "https://api.deepseek.example",
    "DEEPSEEK_API_KEY_SECRET_REF": "secretref://vault/dev/deepseek-api-key",
    "DEEPSEEK_CHAT_MODEL": "deepseek-chat",
    "DEEPSEEK_MAX_OUTPUT_TOKENS": "2048",
    "DEEPSEEK_RPM": "30",
    "DEEPSEEK_TPM": "60000",
    "DEEPSEEK_MAX_CONCURRENCY": "2",
    "DEEPSEEK_PER_RUN_BUDGET": "1.0",
    "DEEPSEEK_DAILY_BUDGET": "5.0",
    "DMT_HTTPS_PROXY": "http://proxy.internal:3128",
    "DEEPSEEK_ALLOWED_FQDNS": "api.deepseek.example",
}


def _write(tmp_path: Path, mutate: dict[str, object]) -> Path:
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    raw.update(mutate)
    path = tmp_path / "deepseek.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


class TestConfigSchema:
    def test_repo_template_loads_with_safe_defaults(self) -> None:
        config = load_config(CONFIG_PATH)
        assert config.enabled is False
        assert config.mode == "mock"
        assert config.provider == "deepseek"
        assert config.retry_strategy.retry_http_statuses == (408, 429, 500, 502, 503, 504)
        assert config.data_handling.log_request_body is False
        assert config.data_handling.log_response_body is False
        assert config.config_hash().startswith("sha256:")

    def test_unknown_field_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"surprise_field": True})
        with pytest.raises(ConnectorConfigError, match="config invalid"):
            load_config(path)

    def test_nested_unknown_field_rejected(self, tmp_path: Path) -> None:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        raw["retry_strategy"]["shadow_retries"] = 99
        path = tmp_path / "deepseek.yaml"
        path.write_text(yaml.safe_dump(raw), encoding="utf-8")
        with pytest.raises(ConnectorConfigError, match="config invalid"):
            load_config(path)

    def test_secret_looking_value_in_config_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"endpoint": "sk-verysecretapikey"})
        with pytest.raises(ConnectorConfigError, match="raw secret"):
            load_config(path)

    def test_repo_config_contains_no_secret_material(self) -> None:
        text = CONFIG_PATH.read_text(encoding="utf-8")
        for marker in ("sk-", "Bearer ", "api_key:", "secret_value"):
            assert marker not in text


class TestRuntimeResolution:
    def test_mock_mode_needs_no_env_or_credentials(self) -> None:
        runtime = resolve_runtime(load_config(CONFIG_PATH), {})
        assert runtime.mode == "mock"
        assert runtime.api_key_ref is None
        assert runtime.endpoint is None

    def test_live_mode_blocked_when_disabled(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "live"})
        with pytest.raises(ConnectorConfigError, match="enabled=true"):
            resolve_runtime(load_config(path), REAL_ENV)

    def test_live_mode_requires_every_env_value(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "live", "enabled": True})
        config = load_config(path)
        for missing in REAL_ENV:
            env = {k: v for k, v in REAL_ENV.items() if k != missing}
            with pytest.raises(ConnectorConfigError):
                resolve_runtime(config, env)

    def test_live_mode_resolves_with_full_env(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        runtime = resolve_runtime(load_config(path), REAL_ENV)
        assert runtime.mode == "sandbox"
        assert runtime.api_key_ref == "secretref://vault/dev/deepseek-api-key"
        assert runtime.allowed_fqdns == ("api.deepseek.example",)
        assert runtime.proxy_url == "http://proxy.internal:3128"

    def test_raw_api_key_in_env_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "live", "enabled": True})
        env = {**REAL_ENV, "DEEPSEEK_API_KEY_SECRET_REF": "sk-rawkey123"}
        with pytest.raises(ConnectorConfigError, match="secretref"):
            resolve_runtime(load_config(path), env)


class TestEndpointGuard:
    def test_http_endpoint_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {**REAL_ENV, "DEEPSEEK_API_ENDPOINT": "http://api.deepseek.example"}
        with pytest.raises(ConnectorConfigError, match="https"):
            resolve_runtime(load_config(path), env)

    def test_endpoint_host_not_in_allowlist_rejected(self, tmp_path: Path) -> None:
        path = _write(tmp_path, {"mode": "sandbox", "enabled": True})
        env = {**REAL_ENV, "DEEPSEEK_API_ENDPOINT": "https://attacker.example"}
        with pytest.raises(ConnectorConfigError, match="allowlist"):
            resolve_runtime(load_config(path), env)
