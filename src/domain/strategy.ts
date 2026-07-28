import type {
  AnalysisPeriod,
  MetricReliability,
  SourceReference,
} from "@/domain/analysis";
import type { LinkedInModule } from "@/domain/linkedin";

export type ApprovalStatus = "draft" | "approved" | "rejected";
export type InsightCategory =
  | "audience"
  | "content"
  | "opportunity"
  | "risk";

export interface MetricEvidenceReference {
  metricId: string;
  label: string;
  formattedValue: string;
  period: AnalysisPeriod | null;
  sourceModules: LinkedInModule[];
  sourceReferences: SourceReference[];
  reliability: MetricReliability;
  caveat?: string;
}

export interface EvidenceInsight {
  insightId: string;
  snapshotId: string;
  category: InsightCategory;
  title: string;
  statement: string;
  possibleMeaning: string;
  suggestedValidation: string;
  evidence: MetricEvidenceReference[];
  confidence: "high" | "medium" | "low";
  limitations: string[];
  approvalStatus: ApprovalStatus;
}

export interface StrategyRecommendation {
  strategyId: string;
  snapshotId: string;
  title: string;
  objective: string;
  rationale: string;
  actions: string[];
  insightIds: string[];
  metricIds: string[];
  approvalStatus: ApprovalStatus;
  editedByUser: boolean;
}

export interface BusinessGoal {
  goalId: string;
  statement: string;
  confirmed: boolean;
  confirmedAt: string;
  userDefinedTarget?: {
    metricId: string;
    value: number;
    unit: string;
    explicitlySetByUser: true;
  };
}

export interface EvidenceStrategyBundle {
  promptVersion: "evidence-strategy-v1.0";
  snapshotId: string;
  generatedAt: string;
  insights: EvidenceInsight[];
  strategies: StrategyRecommendation[];
}
