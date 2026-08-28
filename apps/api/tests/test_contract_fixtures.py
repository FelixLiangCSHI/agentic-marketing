"""Validate the shared golden/invalid fixtures with the Pydantic models.

TypeScript runs the exact same fixtures against the JSON Schemas
(``src/tests/domain-contracts.test.ts``); both sides must agree 100%.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dmt_api.contracts import CONTRACT_MODELS, validate_contract

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_ROOT = REPO_ROOT / "packages" / "domain-contracts" / "fixtures"


def _load(kind: str, contract: str) -> list[dict[str, Any]]:
    path = FIXTURES_ROOT / kind / f"{contract}.json"
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    assert entries, f"fixture file {path} must not be empty"
    return entries


def test_every_contract_has_golden_and_invalid_fixtures() -> None:
    for contract in CONTRACT_MODELS:
        assert (FIXTURES_ROOT / "golden" / f"{contract}.json").is_file()
        assert (FIXTURES_ROOT / "invalid" / f"{contract}.json").is_file()


@pytest.mark.parametrize("contract", sorted(CONTRACT_MODELS))
def test_golden_fixtures_are_valid(contract: str) -> None:
    for entry in _load("golden", contract):
        valid, errors = validate_contract(contract, entry["document"])
        assert valid, f"golden fixture {entry['name']!r} should be valid: {errors}"


@pytest.mark.parametrize("contract", sorted(CONTRACT_MODELS))
def test_invalid_fixtures_are_rejected(contract: str) -> None:
    for entry in _load("invalid", contract):
        valid, _ = validate_contract(contract, entry["document"])
        assert not valid, f"invalid fixture {entry['name']!r} must be rejected"


@pytest.mark.parametrize("contract", sorted(CONTRACT_MODELS))
def test_unknown_fields_are_rejected(contract: str) -> None:
    entry = _load("golden", contract)[0]
    mutated = dict(entry["document"])
    mutated["unexpected_extra_field"] = "x"
    valid, _ = validate_contract(contract, mutated)
    assert not valid, f"{contract} must reject unknown fields per contract rules"
