"""Compliance eval harness: confusion matrix, recall and node accuracy.

Given labeled cases (expected rule findings) and engine results, computes:
- per-rule confusion counts (TP / FN / FP; TN per case-rule pair),
- Critical recall (must be 100%) and overall recall (>= 95%),
- suggested-rework-node accuracy (>= 95%),
- false-positive listing for human analysis.

Deterministic and side-effect free; used by both unit tests and the eval
gate under ``evals/``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dmt_compliance.contracts import ComplianceResultV1, ReworkNode, Severity
from dmt_compliance.rules import CHECKED_RULES


@dataclass(frozen=True)
class ExpectedFinding:
    rule_id: str
    severity: Severity
    suggested_rework_node: ReworkNode


@dataclass(frozen=True)
class LabeledCase:
    """One golden (no findings) or adversarial (expected findings) case."""

    name: str
    expected: tuple[ExpectedFinding, ...]


@dataclass
class RuleConfusion:
    true_positive: int = 0
    false_negative: int = 0
    false_positive: int = 0
    true_negative: int = 0


@dataclass
class EvalReport:
    cases: int = 0
    matrix: dict[str, RuleConfusion] = field(default_factory=dict)
    critical_expected: int = 0
    critical_found: int = 0
    expected_total: int = 0
    found_total: int = 0
    node_checked: int = 0
    node_correct: int = 0
    false_positives: list[str] = field(default_factory=list)

    @property
    def critical_recall(self) -> float:
        if self.critical_expected == 0:
            return 1.0
        return self.critical_found / self.critical_expected

    @property
    def overall_recall(self) -> float:
        if self.expected_total == 0:
            return 1.0
        return self.found_total / self.expected_total

    @property
    def node_accuracy(self) -> float:
        if self.node_checked == 0:
            return 1.0
        return self.node_correct / self.node_checked

    @property
    def critical_escapes(self) -> int:
        return self.critical_expected - self.critical_found

    def summary(self) -> dict[str, object]:
        return {
            "cases": self.cases,
            "critical_recall": round(self.critical_recall, 4),
            "overall_recall": round(self.overall_recall, 4),
            "node_accuracy": round(self.node_accuracy, 4),
            "critical_escapes": self.critical_escapes,
            "false_positives": list(self.false_positives),
            "matrix": {
                rule: {
                    "tp": c.true_positive,
                    "fn": c.false_negative,
                    "fp": c.false_positive,
                    "tn": c.true_negative,
                }
                for rule, c in sorted(self.matrix.items())
            },
        }


def score_cases(
    results: list[tuple[LabeledCase, ComplianceResultV1]],
) -> EvalReport:
    report = EvalReport()
    for rule in CHECKED_RULES:
        report.matrix[rule] = RuleConfusion()
    for case, result in results:
        report.cases += 1
        expected_by_rule = {finding.rule_id: finding for finding in case.expected}
        actual_rules = {issue.rule_id for issue in result.issues}
        for rule in CHECKED_RULES:
            confusion = report.matrix[rule]
            expected = rule in expected_by_rule
            actual = rule in actual_rules
            if expected and actual:
                confusion.true_positive += 1
            elif expected and not actual:
                confusion.false_negative += 1
            elif actual and not expected:
                confusion.false_positive += 1
                report.false_positives.append(f"{case.name}:{rule}")
            else:
                confusion.true_negative += 1
        for finding in case.expected:
            report.expected_total += 1
            if finding.severity == "critical":
                report.critical_expected += 1
            if finding.rule_id in actual_rules:
                report.found_total += 1
                if finding.severity == "critical":
                    report.critical_found += 1
                report.node_checked += 1
                actual_nodes = {
                    issue.suggested_rework_node
                    for issue in result.issues
                    if issue.rule_id == finding.rule_id
                }
                if finding.suggested_rework_node in actual_nodes:
                    report.node_correct += 1
    return report
