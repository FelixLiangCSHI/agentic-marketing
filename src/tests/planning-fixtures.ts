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
    statement: "Support hospital medical device evaluation with clinical evidence, regulatory progress, and economic value.",
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
      contentResources: [
        "clinical evidence",
        "regulatory materials",
        "health economics analysis",
        "expert interviews",
        "medical design",
      ],
      targetMarket: "North American and European hospital systems",
      focusAudience: "Healthcare professionals, clinical experts, procurement teams, and regulatory leaders",
    },
    ...overrides,
  };
}
