"""Schema-parity gate: the raw JSON Schemas are the single source of truth.

The Pydantic models in ``dmt_api.contracts`` are hand-written mirrors.  This
test validates every shared golden/invalid fixture directly against the JSON
Schemas with ``jsonschema`` and asserts that both validators agree 100%, so a
mirror that drifts from the schemas fails CI even where fixture coverage is
thin on one side.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from dmt_api.contracts import CONTRACT_MODELS, validate_contract

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_ROOT = REPO_ROOT / "packages" / "domain-contracts"
SCHEMAS_ROOT = CONTRACTS_ROOT / "schemas"
FIXTURES_ROOT = CONTRACTS_ROOT / "fixtures"


def _validator(contract: str) -> Draft7Validator:
    schema = json.loads(
        (SCHEMAS_ROOT / f"{contract}.schema.json").read_text(encoding="utf-8")
    )
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def _load(kind: str, contract: str) -> list[dict[str, Any]]:
    path = FIXTURES_ROOT / kind / f"{contract}.json"
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    assert entries, f"fixture file {path} must not be empty"
    return entries


def test_every_pydantic_mirror_has_a_schema() -> None:
    for contract in CONTRACT_MODELS:
        assert (SCHEMAS_ROOT / f"{contract}.schema.json").is_file()


@pytest.mark.parametrize("contract", sorted(CONTRACT_MODELS))
def test_schema_and_pydantic_agree_on_golden_fixtures(contract: str) -> None:
    validator = _validator(contract)
    for entry in _load("golden", contract):
        schema_errors = list(validator.iter_errors(entry["document"]))
        assert not schema_errors, (
            f"golden fixture {entry['name']!r} rejected by JSON Schema: "
            f"{[e.message for e in schema_errors]}"
        )
        pyd_valid, pyd_errors = validate_contract(contract, entry["document"])
        assert pyd_valid, (
            f"golden fixture {entry['name']!r} rejected by Pydantic mirror "
            f"(schema accepted it — mirror drifted): {pyd_errors}"
        )


@pytest.mark.parametrize("contract", sorted(CONTRACT_MODELS))
def test_schema_and_pydantic_agree_on_invalid_fixtures(contract: str) -> None:
    validator = _validator(contract)
    for entry in _load("invalid", contract):
        schema_valid = not list(validator.iter_errors(entry["document"]))
        pyd_valid, _ = validate_contract(contract, entry["document"])
        assert not schema_valid, (
            f"invalid fixture {entry['name']!r} accepted by JSON Schema"
        )
        assert not pyd_valid, (
            f"invalid fixture {entry['name']!r} accepted by Pydantic mirror "
            "(schema rejected it — mirror drifted)"
        )
