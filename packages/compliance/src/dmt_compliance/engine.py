"""Compliance engine: deterministic rules first, critic questions second.

``automated_status`` is derived exclusively from rule issues: any
``critical`` issue blocks. Critic output is appended as questions for the
human reviewers and can never change the status — there is no code path
from critic output to ``automated_status``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from content_workflow.contracts import (
    ContentBriefV1,
    CopyDraftV1,
    MediaAssetV1,
    model_hash,
)

from dmt_compliance.contracts import (
    AutomatedStatus,
    ComplianceResultV1,
    CriticQuestionV1,
    content_version_id_for,
)
from dmt_compliance.critic import Critic
from dmt_compliance.policy import ContentPolicyV1
from dmt_compliance.rules import CHECKED_RULES, run_rules


class ComplianceEngine:
    """One policy-bound compliance engine instance."""

    def __init__(self, policy: ContentPolicyV1, *, critic: Critic | None = None) -> None:
        self._policy = policy
        self._critic = critic

    @property
    def policy_version(self) -> str:
        return self._policy.policy_version

    def evaluate(
        self,
        *,
        brief: ContentBriefV1,
        draft: CopyDraftV1,
        media: Sequence[MediaAssetV1] = (),
        requested_media_types: Sequence[str] = (),
        as_of: str,
    ) -> ComplianceResultV1:
        issues = run_rules(
            policy=self._policy,
            brief=brief,
            draft=draft,
            media=media,
            requested_media_types=requested_media_types,
            as_of=as_of,
        )
        # 状态只由确定性规则决定；Critic 输出在此之后才被读取。
        automated_status: AutomatedStatus = (
            "BLOCKED" if any(i.severity == "critical" for i in issues) else "PASS"
        )
        questions: tuple[CriticQuestionV1, ...] = ()
        if self._critic is not None:
            questions = tuple(self._critic.review(brief, draft))
        content_version_id = content_version_id_for(
            model_hash(draft), *(asset.sha256 for asset in media)
        )
        result_id = "cr-" + hashlib.sha256(
            f"{content_version_id}|{self._policy.policy_version}".encode("utf-8")
        ).hexdigest()[:24]
        return ComplianceResultV1(
            compliance_result_id=result_id,
            content_version_id=content_version_id,
            policy_version=self._policy.policy_version,
            issues=issues,
            critic_questions=questions,
            checked_rules=CHECKED_RULES,
            automated_status=automated_status,
            reviewer_status="PENDING",
        )
