import { generateEvidenceStrategyBundle } from "@/agents/evidence-strategy-agent";
import { generateAnalysisSnapshot } from "@/analysis/snapshot-engine";
import type { ActionPlanInput } from "@/domain/action-plan";
import type { BusinessGoal } from "@/domain/strategy";
import { handVerifiedInput } from "@/tests/analysis-fixtures";

export const PLANNING_NOW = new Date("2026-07-28T01:00:00.000Z");

export function approvedPlanningInput(
  overrides: Partial<ActionPlanInput> = {},
): ActionPlanInput {
  const snapshot = generateAnalysisSnapshot(handVerifiedInput());
  const bundle = generateEvidenceStrategyBundle(snapshot, PLANNING_NOW);
  const approvedInsights = bundle.insights.map((insight) => ({
    ...insight,
    approvalStatus: "approved" as const,
  }));
  const approvedStrategies = bundle.strategies.map((strategy) => ({
    ...strategy,
    approvalStatus: "approved" as const,
  }));
  const businessGoal: BusinessGoal = {
    goalId: "goal-synthetic",
    statement: "以临床证据、法规进展和经济价值支持医院医疗器械评估",
    confirmed: true,
    confirmedAt: PLANNING_NOW.toISOString(),
  };

  return {
    snapshot,
    businessGoal,
    approvedInsights,
    approvedStrategies,
    preferences: {
      startDate: "2026-07-29",
      timeZone: "Asia/Shanghai",
      postsPerWeek: 3,
      teamSize: null,
      contentResources: ["临床证据", "法规资料", "健康经济学分析", "KOL 访谈"],
      targetMarket: "北美与欧盟医院系统",
      focusAudience: "医疗专业人员、临床 KOL、医院采购和法规事务负责人",
    },
    ...overrides,
  };
}
