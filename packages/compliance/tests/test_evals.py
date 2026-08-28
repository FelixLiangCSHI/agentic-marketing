"""Eval gate: confusion matrix, Critical/overall recall and node accuracy
over golden + adversarial labeled cases (P2-CP04 thresholds)."""

from __future__ import annotations

from builders import AS_OF, make_brief, make_claim, make_draft, make_media
from content_workflow.contracts import ContentBriefV1, CopyDraftV1, MediaAssetV1

from dmt_compliance import (
    DEFAULT_POLICY_PATH,
    ComplianceEngine,
    ComplianceResultV1,
    ExpectedFinding,
    LabeledCase,
    load_policy,
    score_cases,
)

POLICY = load_policy(DEFAULT_POLICY_PATH)
ENGINE = ComplianceEngine(POLICY)


def _result(
    draft: CopyDraftV1,
    brief: ContentBriefV1 | None = None,
    media: tuple[MediaAssetV1, ...] | None = None,
    requested: tuple[str, ...] = ("image",),
) -> ComplianceResultV1:
    return ENGINE.evaluate(
        brief=brief or make_brief(),
        draft=draft,
        media=(make_media(),) if media is None else media,
        requested_media_types=requested,
        as_of=AS_OF,
    )


def build_cases() -> list[tuple[LabeledCase, ComplianceResultV1]]:
    cases: list[tuple[LabeledCase, ComplianceResultV1]] = []

    # ---- Golden cases: fully compliant, no findings expected ----
    cases.append((LabeledCase("golden-basic", ()), _result(make_draft())))
    cases.append(
        (
            LabeledCase("golden-two-claims", ()),
            _result(
                make_draft(
                    claims=(make_claim(), make_claim("Alpha is taken with water."))
                )
            ),
        )
    )
    cases.append(
        (
            LabeledCase("golden-near-miss-phrases", ()),
            # 接近但不等于禁用词/比较句式：不应误报。
            _result(make_draft(body="A remarkable therapy. Approved facts only.")),
        )
    )

    # ---- Adversarial cases: labeled expected findings ----
    cases.append(
        (
            LabeledCase(
                "adv-uncited",
                (ExpectedFinding("R-CITE-001", "critical", "copy_issue"),),
            ),
            _result(make_draft(claims=(make_claim("Fabricated.", cited=False),))),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-expired",
                (ExpectedFinding("R-EXP-002", "critical", "fact_issue"),),
            ),
            _result(
                make_draft(
                    claims=(make_claim(expires_at="2026-01-02T00:00:00Z"),)
                )
            ),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-cross-market",
                (ExpectedFinding("R-MKT-003", "critical", "fact_issue"),),
            ),
            _result(make_draft(claims=(make_claim(market="CN"),))),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-banned",
                (ExpectedFinding("R-BAN-004", "critical", "copy_issue"),),
            ),
            _result(make_draft(body="A guaranteed results program.")),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-competitor",
                (ExpectedFinding("R-CMP-005", "major", "copy_issue"),),
            ),
            _result(make_draft(body="Alpha outperforms RivalPharm.")),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-fake-approval",
                (ExpectedFinding("R-APR-006", "critical", "copy_issue"),),
            ),
            _result(make_draft(body="It is officially certified worldwide.")),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-missing-disclosure",
                (ExpectedFinding("R-DIS-007", "major", "copy_issue"),),
            ),
            _result(make_draft(body="Only claims here.", disclosures=())),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-headline",
                (ExpectedFinding("R-LEN-008", "minor", "copy_issue"),),
            ),
            _result(
                make_draft(headline="Way too long for the channel"),
                brief=make_brief(max_headline_chars=8),
            ),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-missing-media",
                (ExpectedFinding("R-MED-009", "major", "asset_issue"),),
            ),
            _result(make_draft(), media=()),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-speculation",
                (ExpectedFinding("R-SPEC-010", "major", "copy_issue"),),
            ),
            _result(make_draft(body="We believe it works.")),
        )
    )
    cases.append(
        (
            LabeledCase(
                "adv-combined",
                (
                    ExpectedFinding("R-CITE-001", "critical", "copy_issue"),
                    ExpectedFinding("R-BAN-004", "critical", "copy_issue"),
                    ExpectedFinding("R-APR-006", "critical", "copy_issue"),
                ),
            ),
            _result(
                make_draft(
                    body="A miracle cure, FDA approved.",
                    claims=(make_claim("Unproven.", cited=False),),
                )
            ),
        )
    )
    return cases


class TestEvalGate:
    def test_confusion_matrix_and_thresholds(self) -> None:
        report = score_cases(build_cases())
        summary = report.summary()
        assert report.cases == 14
        # P2-CP04 门禁：Critical Recall 100%，Critical 逃逸 0。
        assert report.critical_recall == 1.0
        assert report.critical_escapes == 0
        # 总体 Recall >= 95%，建议返工节点正确率 >= 95%。
        assert report.overall_recall >= 0.95
        assert report.node_accuracy >= 0.95
        # 误报分析：golden 案例不得出现 False Positive。
        golden_fps = [fp for fp in report.false_positives if fp.startswith("golden")]
        assert golden_fps == []
        assert isinstance(summary["matrix"], dict)

    def test_missed_critical_is_detected_as_escape(self) -> None:
        # 若某 Critical 规则未命中，Recall 门禁必须能发现（FAIL 语义）。
        case = LabeledCase(
            "adv-would-escape",
            (ExpectedFinding("R-CITE-001", "critical", "copy_issue"),),
        )
        clean_result = _result(make_draft())  # deliberately mismatched
        report = score_cases([(case, clean_result)])
        assert report.critical_recall == 0.0
        assert report.critical_escapes == 1
