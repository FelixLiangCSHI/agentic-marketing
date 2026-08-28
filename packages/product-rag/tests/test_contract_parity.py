"""Anti-drift gate: product_rag models must agree with the shared fixtures.

The authoritative golden/invalid fixtures live in
``packages/domain-contracts/fixtures``. dmt_api and TypeScript validate them
in their own suites; this test keeps the product_rag mirrors in lockstep.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from product_rag.models import ProductChangeV1, ProductClaimV1, ProductDocumentV1

FIXTURES_ROOT = (
    Path(__file__).resolve().parents[2] / "domain-contracts" / "fixtures"
)

CONTRACTS: dict[str, type[BaseModel]] = {
    "product-document.v1": ProductDocumentV1,
    "product-claim.v1": ProductClaimV1,
    "product-change.v1": ProductChangeV1,
}


def _load(kind: str, contract: str) -> list[dict[str, Any]]:
    path = FIXTURES_ROOT / kind / f"{contract}.json"
    entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    assert entries, f"fixture file {path} must not be empty"
    return entries


@pytest.mark.parametrize("contract", sorted(CONTRACTS))
def test_golden_fixtures_are_valid(contract: str) -> None:
    model = CONTRACTS[contract]
    for entry in _load("golden", contract):
        model.model_validate(entry["document"])


@pytest.mark.parametrize("contract", sorted(CONTRACTS))
def test_invalid_fixtures_are_rejected(contract: str) -> None:
    model = CONTRACTS[contract]
    for entry in _load("invalid", contract):
        with pytest.raises(ValidationError):
            model.model_validate(entry["document"])
