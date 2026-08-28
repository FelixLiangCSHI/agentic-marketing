"""Engine tests: structured result, blocking semantics, and the guarantee
that no critic output can override a deterministic rule failure."""

from __future__ import annotations

from builders import AS_OF, make_brief, make_claim, make_draft, make_media
from content_workflow.contracts import CopyDraftV1

from dmt_compliance import (
    DEFAULT_POLICY_PATH,
    ComplianceEngine,
    ComplianceResultV1,
    Critic,
    FakeCritic,
    load_policy,
)

POLICY = load_policy(DEFAULT_POLICY_PATH)


def _evaluate(draft: CopyDraftV1, *, critic: Critic | None = None) -> ComplianceResultV1:
    engine = ComplianceEngine(POLICY, critic=critic)
    return engine.evaluate(
        brief=make_brief(),
        draft=draft,
        media=(make_media(),),
        requested_media_types=("image",),
        as_of=AS_OF,
    )


class TestEngine:
    def test_result_is_structured_and_versioned(self) -> None:
        result = _evaluate(make_draft())
        assert isinstance(result, ComplianceResultV1)
        assert result.policy_version == POLICY.policy_version
        assert result.compliance_result_id.startswith("cr-")
        assert result.content_version_id.startswith("cv-")
        assert result.automated_status == "PASS"
        assert result.reviewer_status == "PENDING"
        assert result.checked_rules
        assert result.result_hash().startswith("sha256:")

    def test_critical_issue_blocks(self) -> None:
        result = _evaluate(make_draft(body="A miracle cure."))
        assert result.automated_status == "BLOCKED"

    def test_major_only_issues_pass_with_findings(self) -> None:
        result = _evaluate(make_draft(body="Claim text.", disclosures=()))
        assert result.automated_status == "PASS"
        assert any(i.rule_id == "R-DIS-007" for i in result.issues)

    def test_content_version_changes_with_content(self) -> None:
        first = _evaluate(make_draft())
        second = _evaluate(make_draft(headline="Different headline"))
        assert first.content_version_id != second.content_version_id


class TestCriticCannotOverride:
    def test_critic_adds_questions_only(self) -> None:
        draft = make_draft(body="The best treatment. " + make_claim().text)
        result = _evaluate(draft, critic=FakeCritic())
        assert result.critic_questions
        assert all(q.question for q in result.critic_questions)
        # 状态与规则一致，与 Critic 是否运行无关。
        assert result.automated_status == _evaluate(draft).automated_status

    def test_hostile_critic_verdict_never_flips_blocked_to_pass(self) -> None:
        blocked_draft = make_draft(body="A miracle cure, FDA approved.")
        result = _evaluate(blocked_draft, critic=FakeCritic(attempt_override=True))
        assert result.automated_status == "BLOCKED"
        # 敌意“判定”只能以问题形式存在，供人工审阅识别。
        assert any("VERDICT" in q.question for q in result.critic_questions)

    def test_critic_cannot_remove_issues(self) -> None:
        blocked_draft = make_draft(body="A miracle cure.")
        with_critic = _evaluate(blocked_draft, critic=FakeCritic(attempt_override=True))
        without = _evaluate(blocked_draft)
        assert {i.issue_id for i in with_critic.issues} == {
            i.issue_id for i in without.issues
        }
