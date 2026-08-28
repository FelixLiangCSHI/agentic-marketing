"""Versioned content policy: the only source of banned/comparison terms.

The policy is a frozen fixture committed to the repository; its version is
recorded in every compliance result. Models never modify the policy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

from dmt_compliance.contracts import Severity


class PolicyError(Exception):
    """Policy fixture missing or structurally invalid (typed, never faked)."""


class BannedExpression(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    phrase: StrictStr = Field(min_length=1)
    severity: Severity


class ContentPolicyV1(BaseModel):
    """Frozen, versioned content policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    policy_id: StrictStr
    policy_version: StrictStr = Field(pattern=r"^\d+\.\d+\.\d+$")
    markets: tuple[StrictStr, ...]
    banned_expressions: tuple[BannedExpression, ...]
    competitor_names: tuple[StrictStr, ...]
    comparison_markers: tuple[StrictStr, ...]
    approval_claim_patterns: tuple[StrictStr, ...]
    speculation_markers: tuple[StrictStr, ...]


def load_policy(path: Path) -> ContentPolicyV1:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyError(f"policy fixture unreadable: {exc}") from exc
    try:
        return ContentPolicyV1.model_validate(raw)
    except ValidationError as exc:
        raise PolicyError(f"policy fixture invalid: {exc}") from exc


DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "content-policy.json"
)
