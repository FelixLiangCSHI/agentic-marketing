import assert from "node:assert/strict";
import test from "node:test";

import {
  formatVersions,
  groupIssuesByNode,
  overallStatusLabel,
  sortIssues,
  suggestedReworkTarget,
  validateDecision,
  type ComplianceIssueView,
  type ReviewDetailView,
  type TrackView,
} from "@/domain/review";

function issue(overrides: Partial<ComplianceIssueView>): ComplianceIssueView {
  return {
    issue_id: "iss-1",
    rule_id: "R-CITE-001",
    claim_id: "claim-abc",
    severity: "critical",
    detail: "uncited claim",
    suggested_rework_node: "copy_issue",
    ...overrides,
  };
}

function track(overrides: Partial<TrackView> = {}): TrackView {
  return {
    status: "PENDING",
    decided_by: null,
    decided_at: null,
    reason: null,
    rework_target: null,
    ...overrides,
  };
}

function detail(overrides: Partial<ReviewDetailView> = {}): ReviewDetailView {
  return {
    review_id: "rev-0123456789abcdef",
    run_id: "run-0001",
    tenant: "tenant-cshi",
    status: "AWAITING_REVIEW",
    revision: 1,
    created_by: "carol",
    created_at: "2026-06-01T00:00:00Z",
    artifact_hash: `sha256:${"a".repeat(64)}`,
    policy_version: "1.0.0",
    workflow_version: "0.1.0",
    automated_status: "PASS",
    medical: track(),
    marketing: track(),
    content: { headline: "H" },
    issues: [],
    critic_questions: [],
    sources: [],
    ...overrides,
  };
}

test("issues sort critical first, stable by rule id", () => {
  const sorted = sortIssues([
    issue({ issue_id: "b", rule_id: "R-LEN-008", severity: "minor" }),
    issue({ issue_id: "c", rule_id: "R-DIS-007", severity: "major" }),
    issue({ issue_id: "a", rule_id: "R-CITE-001", severity: "critical" }),
  ]);
  assert.deepEqual(
    sorted.map((entry) => entry.rule_id),
    ["R-CITE-001", "R-DIS-007", "R-LEN-008"],
  );
});

test("issues group by suggested rework node", () => {
  const groups = groupIssuesByNode([
    issue({ issue_id: "a", suggested_rework_node: "copy_issue" }),
    issue({
      issue_id: "b",
      rule_id: "R-EXP-002",
      suggested_rework_node: "fact_issue",
    }),
    issue({
      issue_id: "c",
      rule_id: "R-MED-009",
      severity: "major",
      suggested_rework_node: "asset_issue",
    }),
  ]);
  assert.equal(groups.get("copy_issue")?.length, 1);
  assert.equal(groups.get("fact_issue")?.length, 1);
  assert.equal(groups.get("asset_issue")?.length, 1);
});

test("suggested rework target follows the most severe issue", () => {
  const target = suggestedReworkTarget([
    issue({ issue_id: "a", severity: "minor", suggested_rework_node: "copy_issue" }),
    issue({
      issue_id: "b",
      rule_id: "R-EXP-002",
      severity: "critical",
      suggested_rework_node: "fact_issue",
    }),
  ]);
  assert.equal(target, "fact_issue");
  assert.equal(suggestedReworkTarget([]), null);
});

test("approve is refused client-side when the gate is BLOCKED", () => {
  const result = validateDecision("BLOCKED", {
    decision: "approved",
    reason: "",
    rework_target: "",
  });
  assert.equal(result.ok, false);
  assert.equal(result.errors.length, 1);
});

test("approve passes when the gate is PASS", () => {
  const result = validateDecision("PASS", {
    decision: "approved",
    reason: "",
    rework_target: "",
  });
  assert.equal(result.ok, true);
});

test("reject requires reason and target node", () => {
  const missingBoth = validateDecision("PASS", {
    decision: "rejected",
    reason: "  ",
    rework_target: "",
  });
  assert.equal(missingBoth.ok, false);
  assert.equal(missingBoth.errors.length, 2);
  const complete = validateDecision("BLOCKED", {
    decision: "rejected",
    reason: "uncited claim",
    rework_target: "copy_issue",
  });
  assert.equal(complete.ok, true);
});

test("versions summary shows content, policy and workflow versions", () => {
  const lines = formatVersions(detail());
  assert.equal(lines.length, 3);
  assert.match(lines[0], /rev 1/);
  assert.match(lines[1], /1\.0\.0/);
});

test("overall status label reflects the two-track state", () => {
  assert.match(overallStatusLabel(detail()), /医学、市场/);
  assert.match(
    overallStatusLabel(detail({ medical: track({ status: "APPROVED" }) })),
    /市场/,
  );
  assert.match(overallStatusLabel(detail({ status: "APPROVED" })), /双轨/);
  assert.match(overallStatusLabel(detail({ status: "REJECTED" })), /驳回/);
});
