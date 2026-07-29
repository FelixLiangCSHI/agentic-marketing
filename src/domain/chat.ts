import type { AnalysisPeriod, SourceReference } from "@/domain/analysis";
import type { LinkedInModule } from "@/domain/linkedin";
import type { ConsultingReport } from "@/domain/consulting-report";

export type ChatIntent =
  | "metric_query"
  | "trend_explanation"
  | "quality_explanation"
  | "insight_evidence"
  | "content_recommendation"
  | "plan_modification"
  | "unavailable"
  | "security_refusal";

export type ChatAnswerStatus = "answered" | "unavailable" | "refused";

export interface ChatMetricCitation {
  metricId: string;
  label: string;
  formattedValue: string;
  period: AnalysisPeriod | null;
  sourceModules: LinkedInModule[];
  sourceReferences: SourceReference[];
}

export interface ChatEvidenceCitation {
  citationId: string;
  kind: "metric" | "quality" | "insight" | "strategy" | "plan";
  label: string;
  metric: ChatMetricCitation | null;
}

export type SuggestedPlanChange =
  | {
      type: "posts_per_week";
      postsPerWeek: number;
    }
  | {
      type: "focus_audience";
      focusAudience: string;
    };

export interface ChatAnswer {
  answerId: string;
  promptVersion: "evidence-chat-v1.0";
  intent: ChatIntent;
  status: ChatAnswerStatus;
  report: ConsultingReport;
  citations: ChatEvidenceCitation[];
  suggestedPlanChange: SuggestedPlanChange | null;
}
