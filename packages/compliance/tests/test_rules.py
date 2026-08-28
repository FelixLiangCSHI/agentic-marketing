"""Deterministic rule tests (written first per the subphase prompt):
banned expressions, expired claims, missing disclosure, cross-market,
competitor comparison, fabricated approval, headline length, missing
media, speculation — each with rule ID, claim ID, severity, source and
suggested rework node.
"""

from __future__ import annotations

from builders import AS_OF, make_brief, make_claim, make_draft, make_media
from content_workflow.contracts import ContentBriefV1, CopyDraftV1, MediaAssetV1

from dmt_compliance import (
    DEFAULT_POLICY_PATH,
    ComplianceIssueV1,
    claim_id_for,
    load_policy,
    run_rules,
)

POLICY = load_policy(DEFAULT_POLICY_PATH)


def _run(
    draft: CopyDraftV1,
    brief: ContentBriefV1 | None = None,
    media: tuple[MediaAssetV1, ...] = (),
    requested: tuple[str, ...] = ("image",),
    as_of: str = AS_OF,
) -> tuple[ComplianceIssueV1, ...]:
    return run_rules(
        policy=POLICY,
        brief=brief or make_brief(),
        draft=draft,
        media=media or (make_media(),),
        requested_media_types=requested,
        as_of=as_of,
    )


def _rules(issues: tuple[ComplianceIssueV1, ...]) -> set[str]:
    return {issue.rule_id for issue in issues}


class TestCleanContent:
    def test_grounded_draft_has_no_issues(self) -> None:
        assert _run(make_draft()) == ()


class TestClaimSourceRules:
    def test_uncited_claim_is_critical_copy_issue(self) -> None:
        claim = make_claim("Novel efficacy claim.", cited=False)
        issues = _run(make_draft(claims=(make_claim(), claim)))
        found = [i for i in issues if i.rule_id == "R-CITE-001"]
        assert len(found) == 1
        assert found[0].severity == "critical"
        assert found[0].suggested_rework_node == "copy_issue"
        assert found[0].claim_id == claim_id_for("Novel efficacy claim.")
        assert found[0].source_reference is None

    def test_expired_claim_is_critical_fact_issue_with_source(self) -> None:
        claim = make_claim("Old dosing claim.", expires_at="2026-05-01T00:00:00Z")
        issues = _run(make_draft(claims=(claim,)))
        found = [i for i in issues if i.rule_id == "R-EXP-002"]
        assert len(found) == 1
        assert found[0].severity == "critical"
        assert found[0].suggested_rework_node == "fact_issue"
        assert found[0].source_reference is not None
        assert found[0].source_reference.expires_at == "2026-05-01T00:00:00Z"

    def test_unexpired_claim_passes(self) -> None:
        issues = _run(make_draft(claims=(make_claim(expires_at=None),)))
        assert "R-EXP-002" not in _rules(issues)

    def test_cross_market_claim_is_critical_fact_issue(self) -> None:
        claim = make_claim("CN-only claim.", market="CN")
        issues = _run(make_draft(claims=(claim,)))
        found = [i for i in issues if i.rule_id == "R-MKT-003"]
        assert len(found) == 1
        assert found[0].severity == "critical"
        assert found[0].suggested_rework_node == "fact_issue"
        assert found[0].source_reference is not None
        assert found[0].source_reference.market == "CN"


class TestExpressionRules:
    def test_policy_banned_expression_detected_with_policy_severity(self) -> None:
        issues = _run(make_draft(body="This is a miracle cure for everyone."))
        found = [i for i in issues if i.rule_id == "R-BAN-004"]
        assert any(i.severity == "critical" for i in found)
        assert all(i.suggested_rework_node == "copy_issue" for i in found)

    def test_brief_banned_phrase_also_detected(self) -> None:
        issues = _run(make_draft(body="Our cure-all approach."))
        assert "R-BAN-004" in _rules(issues)

    def test_competitor_comparison_requires_name_and_marker(self) -> None:
        both = _run(make_draft(body="Product Alpha is better than CompetitorX."))
        assert "R-CMP-005" in _rules(both)
        name_only = _run(make_draft(body="CompetitorX also sells medicine."))
        assert "R-CMP-005" not in _rules(name_only)
        marker_only = _run(make_draft(body="This is better than before."))
        assert "R-CMP-005" not in _rules(marker_only)

    def test_fabricated_regulator_approval_is_critical(self) -> None:
        issues = _run(make_draft(body="Product Alpha is FDA approved for all uses."))
        found = [i for i in issues if i.rule_id == "R-APR-006"]
        assert len(found) == 1
        assert found[0].severity == "critical"

    def test_speculation_as_fact_is_major(self) -> None:
        issues = _run(make_draft(body="It probably works for most patients."))
        found = [i for i in issues if i.rule_id == "R-SPEC-010"]
        assert found and found[0].severity == "major"


class TestStructuralRules:
    def test_missing_disclosure_is_major_copy_issue(self) -> None:
        draft = make_draft(body="Only the claim.", disclosures=())
        issues = _run(draft)
        found = [i for i in issues if i.rule_id == "R-DIS-007"]
        assert found and found[0].severity == "major"
        assert found[0].suggested_rework_node == "copy_issue"

    def test_headline_length_is_minor(self) -> None:
        brief = make_brief(max_headline_chars=10)
        issues = _run(make_draft(headline="A far too long headline"), brief=brief)
        found = [i for i in issues if i.rule_id == "R-LEN-008"]
        assert found and found[0].severity == "minor"

    def test_missing_requested_media_is_asset_issue(self) -> None:
        issues = run_rules(
            policy=POLICY,
            brief=make_brief(),
            draft=make_draft(),
            media=(),
            requested_media_types=("image",),
            as_of=AS_OF,
        )
        found = [i for i in issues if i.rule_id == "R-MED-009"]
        assert found and found[0].suggested_rework_node == "asset_issue"


class TestDeterminism:
    def test_same_input_same_issue_ids(self) -> None:
        draft = make_draft(body="A miracle cure, better than CompetitorX.")
        first = _run(draft)
        second = _run(draft)
        assert [i.issue_id for i in first] == [i.issue_id for i in second]
