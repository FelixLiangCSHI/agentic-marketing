"""Layered, typed configuration.

Merge order: base -> environment -> agent -> workflow -> tenant/market.
Later layers override earlier scalars; nested sections merge key-by-key.
Unknown fields anywhere are rejected. ``mode`` defaults to ``mock``; any
non-mock capability must declare endpoint, quota, proxy, and a
``secretref://`` credential reference or startup fails. PRD configuration
refuses to run with a ``.env`` file containing secret-looking entries.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from infra_core.secrets import SecretRef, SecretRefFormatError


class ConfigError(Exception):
    """Configuration is invalid; startup must fail."""


Mode = Literal["mock", "sandbox", "live"]
Environment = Literal["local", "dev", "sit", "uat", "prd"]


class QueueConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "dmt-tasks"
    max_attempts: int = Field(default=3, ge=1, le=20)
    lease_seconds: int = Field(default=60, ge=5, le=3600)


class ObjectStoreConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str = "dmt-artifacts"
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1)


class CapabilityConfig(BaseModel):
    """A capability that can run mock, sandbox, or live."""

    model_config = ConfigDict(extra="forbid")

    mode: Mode = "mock"
    endpoint: str | None = None
    quota_per_minute: int | None = Field(default=None, ge=1)
    proxy: str | None = None
    api_key_ref: str | None = None

    @model_validator(mode="after")
    def _require_full_declaration_for_real_modes(self) -> "CapabilityConfig":
        if self.mode == "mock":
            return self
        missing = [
            name
            for name, value in (
                ("endpoint", self.endpoint),
                ("quota_per_minute", self.quota_per_minute),
                ("proxy", self.proxy),
                ("api_key_ref", self.api_key_ref),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                f"mode={self.mode!r} requires: {', '.join(missing)}"
            )
        assert self.api_key_ref is not None
        try:
            SecretRef.parse(self.api_key_ref)
        except SecretRefFormatError as exc:
            raise ValueError(str(exc)) from None
        return self


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Mode = "mock"
    environment: Environment = "local"
    queue: QueueConfig = QueueConfig()
    object_store: ObjectStoreConfig = ObjectStoreConfig()
    llm: CapabilityConfig = CapabilityConfig()
    media: CapabilityConfig = CapabilityConfig()
    linkedin: CapabilityConfig = CapabilityConfig()
    google_ads: CapabilityConfig = CapabilityConfig()

    def config_hash(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_files(cls, paths: Sequence[Path]) -> "AppConfig":
        layers: list[Mapping[str, Any]] = []
        for path in paths:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(loaded, dict):
                raise ConfigError(f"{path} must contain a mapping")
            layers.append(loaded)
        return load_config(layers)


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, Mapping)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


_SECRETY_KEYS = ("key", "token", "secret", "password", "credential")


def _dotenv_has_secrets(dotenv_path: Path) -> bool:
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip().lower()
        if any(fragment in name for fragment in _SECRETY_KEYS):
            return True
    return False


def load_config(
    layers: Sequence[Mapping[str, Any]],
    *,
    dotenv_path: Path | None = None,
) -> AppConfig:
    """Merge layers in order and validate the result; fail closed."""
    merged: dict[str, Any] = {}
    for layer in layers:
        merged = _deep_merge(merged, layer)
    try:
        config = AppConfig.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(
            "configuration is invalid: "
            + "; ".join(
                f"{'/'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
        ) from None
    if (
        config.environment == "prd"
        and dotenv_path is not None
        and dotenv_path.exists()
        and _dotenv_has_secrets(dotenv_path)
    ):
        raise ConfigError(
            "PRD configuration must not carry secrets in a .env file; "
            "use secret references resolved by the enterprise secret manager"
        )
    return config
