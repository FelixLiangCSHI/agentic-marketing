"""Fixture parity for the local ``ConnectorErrorV1`` mirror.

The mirror in ``deepseek_connector.errors`` is a hand-written copy of the
``connector-error.v1`` contract; run it against the shared golden/invalid
fixtures so it cannot drift silently from the schema-owning package.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from deepseek_connector.errors import ConnectorErrorV1

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_ROOT = REPO_ROOT / "packages" / "domain-contracts" / "fixtures"


def _load(kind: str) -> list[dict[str, Any]]:
    path = FIXTURES_ROOT / kind / "connector-error.v1.json"
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    assert entries, f"fixture file {path} must not be empty"
    return entries


def test_golden_connector_error_fixtures_are_accepted() -> None:
    for entry in _load("golden"):
        ConnectorErrorV1.model_validate(entry["document"])


def test_invalid_connector_error_fixtures_are_rejected() -> None:
    for entry in _load("invalid"):
        try:
            ConnectorErrorV1.model_validate(entry["document"])
        except ValidationError:
            continue
        raise AssertionError(
            f"invalid fixture {entry['name']!r} accepted by the local mirror"
        )
