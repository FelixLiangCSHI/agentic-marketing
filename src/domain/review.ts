/**
 * Review 域视图模型（Phase 02 / Subphase 06）。
 *
 * 仅做展示与客户端预校验：真正的角色→轨道映射、hash 绑定、职责分离
 * 全部由 Control API 服务端强制执行——前端永远不能伪造审核人身份，
 * 也不能替模型翻转规则失败（BLOCKED 时 UI 直接禁用批准按钮）。
 */

export type Severity = "critical" | "major" | "minor";
export type ReworkNode = "fact_issue" | "copy_issue" | "asset_issue";
export type AutomatedStatus = "PASS" | "BLOCKED";

export interface ComplianceIssueView {
  issue_id: string;
  rule_id: string;
  claim_id: string | null;
  severity: Severity;
  detail: string;
  suggested_rework_node: ReworkNode;
}

export interface CriticQuestionView {
  question_id: string;
  claim_id: string | null;
  category: string;
  question: string;
}

export interface TrackView {
  status: "PENDING" | "APPROVED" | "REJECTED" | "INVALIDATED";
  decided_by: string | null;
  decided_at: string | null;
  reason: string | null;
  rework_target: string | null;
}

export interface ReviewDetailView {
  review_id: string;
  run_id: string;
  tenant: string;
  status: string;
  revision: number;
  created_by: string;
  created_at: string;
  artifact_hash: string;
  policy_version: string;
  workflow_version: string;
  automated_status: AutomatedStatus;
  medical: TrackView;
  marketing: TrackView;
  content: Record<string, unknown>;
  issues: ComplianceIssueView[];
  critic_questions: CriticQuestionView[];
  sources: Array<Record<string, unknown>>;
}

const SEVERITY_ORDER: Record<Severity, number> = {
  critical: 0,
  major: 1,
  minor: 2,
};

export const REWORK_NODE_LABELS: Record<ReworkNode, string> = {
  fact_issue: "事实/来源（重新检索）",
  copy_issue: "文案（重写 Copy）",
  asset_issue: "媒体资产（重新生成）",
};

/** 按严重度从高到低排序，同级按 rule_id 稳定排序。 */
export function sortIssues(
  issues: readonly ComplianceIssueView[],
): ComplianceIssueView[] {
  return [...issues].sort((a, b) => {
    const bySeverity = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
    if (bySeverity !== 0) return bySeverity;
    return a.rule_id.localeCompare(b.rule_id);
  });
}

/** 按建议返工节点分组，供审核人一眼看到“驳回应指向哪个节点”。 */
export function groupIssuesByNode(
  issues: readonly ComplianceIssueView[],
): Map<ReworkNode, ComplianceIssueView[]> {
  const groups = new Map<ReworkNode, ComplianceIssueView[]>();
  for (const issue of sortIssues(issues)) {
    const bucket = groups.get(issue.suggested_rework_node) ?? [];
    bucket.push(issue);
    groups.set(issue.suggested_rework_node, bucket);
  }
  return groups;
}

/** 驳回时预填的目标节点：取最严重 Issue 的建议节点。 */
export function suggestedReworkTarget(
  issues: readonly ComplianceIssueView[],
): ReworkNode | null {
  const sorted = sortIssues(issues);
  return sorted.length > 0 ? sorted[0].suggested_rework_node : null;
}

export interface DecisionInput {
  decision: "approved" | "rejected";
  reason: string;
  rework_target: ReworkNode | "";
}

export interface DecisionValidation {
  ok: boolean;
  errors: string[];
}

/**
 * 客户端预校验（服务端仍是最终权威）：
 * - BLOCKED 时禁止批准（规则失败不可被人工覆盖）；
 * - 驳回必须给理由与目标节点。
 */
export function validateDecision(
  automatedStatus: AutomatedStatus,
  input: DecisionInput,
): DecisionValidation {
  const errors: string[] = [];
  if (input.decision === "approved" && automatedStatus === "BLOCKED") {
    errors.push("合规规则未通过（BLOCKED），不能批准；请驳回并指定返工节点。");
  }
  if (input.decision === "rejected") {
    if (input.reason.trim().length === 0) {
      errors.push("驳回必须填写理由。");
    }
    if (input.rework_target === "") {
      errors.push("驳回必须选择返工目标节点。");
    }
  }
  return { ok: errors.length === 0, errors };
}

/** 版本与哈希的并排摘要（内容版本 / 政策版本 / 工作流版本）。 */
export function formatVersions(view: ReviewDetailView): string[] {
  return [
    `内容版本: ${view.artifact_hash.slice(0, 19)}… (rev ${view.revision})`,
    `政策版本: ${view.policy_version}`,
    `工作流版本: ${view.workflow_version}`,
  ];
}

/** 双轨状态摘要：两轨都 APPROVED 才算通过。 */
export function overallStatusLabel(view: ReviewDetailView): string {
  if (view.status === "APPROVED") return "已通过（医学 + 市场双轨）";
  if (view.status === "REJECTED") return "已驳回";
  const pending: string[] = [];
  if (view.medical.status !== "APPROVED") pending.push("医学");
  if (view.marketing.status !== "APPROVED") pending.push("市场");
  return `待审核（${pending.join("、")}）`;
}
