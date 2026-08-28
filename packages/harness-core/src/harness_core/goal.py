"""Goal Check: evidence in, verdict out.

Checks only that the required evidence artifacts exist. It never mutates
workflow state and never issues domain (e.g. Medical) conclusions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from harness_core.context import ArtifactRef


@dataclass(frozen=True, slots=True)
class GoalSpec:
    required_evidence: frozenset[str]


@dataclass(frozen=True, slots=True)
class GoalResult:
    passed: bool
    missing: tuple[str, ...]


def check_goal(spec: GoalSpec, evidence: Mapping[str, ArtifactRef]) -> GoalResult:
    missing = tuple(sorted(key for key in spec.required_evidence if key not in evidence))
    return GoalResult(passed=not missing, missing=missing)
