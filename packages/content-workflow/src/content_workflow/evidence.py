"""Bridge workflow artifacts to the harness Goal Check.

Goal Check only verifies that required evidence artifacts exist; it never
mutates workflow state and never substitutes for the human reviewer.
"""

from __future__ import annotations

from harness_core.context import ArtifactRef
from harness_core.goal import GoalSpec

from content_workflow.contracts import model_hash
from content_workflow.workflow import WorkflowSnapshot

CONTENT_GOAL_SPEC = GoalSpec(
    required_evidence=frozenset(
        {"brief", "copy", "compliance_report", "review_decision"}
    )
)


def build_goal_evidence(snapshot: WorkflowSnapshot) -> dict[str, ArtifactRef]:
    """Collect evidence refs from a run snapshot (present artifacts only)."""
    evidence: dict[str, ArtifactRef] = {}
    thread = snapshot.thread_id
    if snapshot.brief is not None:
        evidence["brief"] = ArtifactRef(
            uri=f"workflow://{thread}/brief",
            sha256=model_hash(snapshot.brief),
            summary="content brief",
        )
    if snapshot.copy_draft is not None:
        evidence["copy"] = ArtifactRef(
            uri=f"workflow://{thread}/copy",
            sha256=model_hash(snapshot.copy_draft),
            summary="copy draft",
        )
    if snapshot.compliance is not None:
        evidence["compliance_report"] = ArtifactRef(
            uri=f"workflow://{thread}/compliance",
            sha256=model_hash(snapshot.compliance),
            summary="compliance report",
        )
    if snapshot.review is not None:
        evidence["review_decision"] = ArtifactRef(
            uri=f"workflow://{thread}/review",
            sha256=model_hash(snapshot.review),
            summary="human review decision",
        )
    return evidence
