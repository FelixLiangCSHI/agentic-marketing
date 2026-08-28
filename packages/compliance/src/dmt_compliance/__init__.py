"""Deterministic compliance rules + model Critic + eval harness.

Phase 02 / Subphase 06. Rules cannot be overridden by any model output;
human Medical/Marketing review authority lives in the Control API.
"""

from dmt_compliance.contracts import (
    AutomatedStatus,
    ComplianceIssueV1,
    ComplianceResultV1,
    CriticQuestionV1,
    ReviewerStatus,
    ReworkNode,
    Severity,
    SourceReferenceV1,
    claim_id_for,
    content_version_id_for,
)
from dmt_compliance.critic import Critic, FakeCritic, default_critic_for
from dmt_compliance.engine import ComplianceEngine
from dmt_compliance.evals import (
    EvalReport,
    ExpectedFinding,
    LabeledCase,
    RuleConfusion,
    score_cases,
)
from dmt_compliance.policy import (
    DEFAULT_POLICY_PATH,
    BannedExpression,
    ContentPolicyV1,
    PolicyError,
    load_policy,
)
from dmt_compliance.rules import CHECKED_RULES, run_rules

__all__ = [
    "AutomatedStatus",
    "BannedExpression",
    "CHECKED_RULES",
    "ComplianceEngine",
    "ComplianceIssueV1",
    "ComplianceResultV1",
    "ContentPolicyV1",
    "Critic",
    "CriticQuestionV1",
    "DEFAULT_POLICY_PATH",
    "EvalReport",
    "ExpectedFinding",
    "FakeCritic",
    "LabeledCase",
    "PolicyError",
    "ReviewerStatus",
    "ReworkNode",
    "RuleConfusion",
    "Severity",
    "SourceReferenceV1",
    "claim_id_for",
    "content_version_id_for",
    "default_critic_for",
    "load_policy",
    "run_rules",
    "score_cases",
]
