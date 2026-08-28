"""Layered configuration tests.

Order: base -> environment -> agent -> workflow -> tenant/market.
Unknown fields are rejected; mode defaults to mock; non-mock modes require
endpoint/quota/proxy/secret references; PRD forbids .env secrets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from infra_core.config import (
    AppConfig,
    ConfigError,
    load_config,
)

BASE: dict[str, Any] = {
    "mode": "mock",
    "environment": "local",
    "queue": {"name": "dmt-tasks", "max_attempts": 3},
    "object_store": {"bucket": "dmt-artifacts", "max_bytes": 1048576},
    "llm": {"mode": "mock"},
}


def test_defaults_to_mock_mode() -> None:
    config = load_config([{"environment": "local", "queue": {"name": "q"}}])
    assert config.mode == "mock"
    assert config.llm.mode == "mock"


def test_layers_merge_in_order() -> None:
    config = load_config(
        [
            BASE,
            {"environment": "dev"},
            {"queue": {"max_attempts": 5}},
            {"object_store": {"max_bytes": 2048}},
            {"queue": {"name": "tenant-queue"}},
        ]
    )
    assert config.environment == "dev"
    assert config.queue.max_attempts == 5
    assert config.queue.name == "tenant-queue"
    assert config.object_store.max_bytes == 2048


def test_unknown_top_level_field_is_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config([BASE, {"unknown_field": 1}])


def test_unknown_nested_field_is_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config([BASE, {"queue": {"nope": True}}])


def test_live_mode_without_endpoint_or_secret_ref_fails_at_startup() -> None:
    with pytest.raises(ConfigError):
        load_config([BASE, {"llm": {"mode": "live"}}])


def test_live_mode_with_full_declaration_is_accepted() -> None:
    config = load_config(
        [
            BASE,
            {"environment": "dev"},
            {
                "llm": {
                    "mode": "live",
                    "endpoint": "https://llm.corp.example/v1",
                    "quota_per_minute": 10,
                    "proxy": "http://proxy.corp.example:3128",
                    "api_key_ref": "secretref://corp-vault/dmt/dev/llm-api-key",
                }
            },
        ]
    )
    assert config.llm.mode == "live"


def test_live_mode_with_raw_secret_instead_of_reference_is_rejected() -> None:
    with pytest.raises(ConfigError):
        load_config(
            [
                BASE,
                {
                    "llm": {
                        "mode": "live",
                        "endpoint": "https://llm.corp.example/v1",
                        "quota_per_minute": 10,
                        "proxy": "http://proxy.corp.example:3128",
                        "api_key_ref": "sk-raw-key-value",
                    }
                },
            ]
        )


def test_prd_environment_forbids_dotenv_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_API_KEY=raw\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config([BASE, {"environment": "prd"}], dotenv_path=env_file)


def test_non_prd_environment_tolerates_dotenv_presence(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DMT_ENVIRONMENT=local\n", encoding="utf-8")
    config = load_config([BASE], dotenv_path=env_file)
    assert config.environment == "local"


def test_config_hash_is_stable_for_identical_layers() -> None:
    one = load_config([BASE])
    two = load_config([dict(BASE)])
    assert one.config_hash() == two.config_hash()
    assert one.config_hash() != load_config(
        [BASE, {"queue": {"max_attempts": 9}}]
    ).config_hash()


def test_yaml_files_load_in_layer_order(tmp_path: Path) -> None:
    (tmp_path / "base.yaml").write_text(
        "mode: mock\nenvironment: local\nqueue:\n  name: q\n  max_attempts: 3\n",
        encoding="utf-8",
    )
    (tmp_path / "dev.yaml").write_text("environment: dev\n", encoding="utf-8")
    config = AppConfig.from_files([tmp_path / "base.yaml", tmp_path / "dev.yaml"])
    assert config.environment == "dev"
    assert config.queue.name == "q"
