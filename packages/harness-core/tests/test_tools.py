"""Tool registry: typed registration, freeze, and parameter validation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from harness_core.errors import ToolRegistrationError, ToolValidationError
from harness_core.tools import ToolRegistry, ToolResult, ToolSpec

from tests.fakes import DraftParams, build_registry


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _handler(params: BaseModel) -> ToolResult:
    return ToolResult(ok=True)


def _spec(name: str = "x.tool", level: str = "L1") -> ToolSpec:
    return ToolSpec(
        name=name,
        version="1.0.0",
        level=level,  # type: ignore[arg-type]
        agent_allowlist=frozenset({"content"}),
        params_model=_P,
        handler=_handler,
    )


def test_duplicate_registration_rejected() -> None:
    registry = ToolRegistry()
    registry.register(_spec())
    with pytest.raises(ToolRegistrationError):
        registry.register(_spec())


def test_registration_after_freeze_rejected() -> None:
    """Prompt injection cannot widen the tool set at runtime."""
    registry = ToolRegistry()
    registry.freeze()
    with pytest.raises(ToolRegistrationError, match="frozen"):
        registry.register(_spec())


def test_unknown_level_rejected() -> None:
    registry = ToolRegistry()
    with pytest.raises(ToolRegistrationError):
        registry.register(_spec(level="L9"))


def test_empty_allowlist_rejected() -> None:
    registry = ToolRegistry()
    spec = ToolSpec(
        name="x.tool",
        version="1.0.0",
        level="L1",
        agent_allowlist=frozenset(),
        params_model=_P,
        handler=_handler,
    )
    with pytest.raises(ToolRegistrationError, match="allowlist"):
        registry.register(spec)


def test_unregistered_tool_params_rejected() -> None:
    registry = build_registry()
    with pytest.raises(ToolValidationError, match="not registered"):
        registry.validate_params("shell.exec", {})


def test_malicious_params_rejected() -> None:
    registry = build_registry()
    with pytest.raises(ToolValidationError, match="invalid parameters"):
        registry.validate_params(
            "content.draft", {"topic": "x", "__proto__": "rm -rf /", "shell": "sh"}
        )
    with pytest.raises(ToolValidationError):
        registry.validate_params("content.draft", {"topic": 42})


def test_valid_params_return_typed_model() -> None:
    registry = build_registry()
    params = registry.validate_params("content.draft", {"topic": "launch"})
    assert isinstance(params, DraftParams)
    assert params.topic == "launch"


def test_snapshot_contains_no_handlers() -> None:
    registry = build_registry()
    snapshot = registry.snapshot()
    assert [entry["name"] for entry in snapshot] == sorted(entry["name"] for entry in snapshot)
    for entry in snapshot:
        assert set(entry) == {"name", "version", "level", "agent_allowlist", "params_schema"}
