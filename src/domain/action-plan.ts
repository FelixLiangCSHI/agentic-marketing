import type { AnalysisPeriod, AnalysisSnapshot } from "@/domain/analysis";
import type { LinkedInModule } from "@/domain/linkedin";
import type {
  BusinessGoal,
  EvidenceInsight,
  StrategyRecommendation,
} from "@/domain/strategy";

export type PlanItemStatus = "ai_draft" | "confirmed" | "rejected";
export type ActionPlanStatus = "ai_draft" | "user_confirmed";
export type SocialChannel = "linkedin_page" | "linkedin_profile";
export type ContentWorkflowStatus =
  | "planning"
  | "ready_for_buffer"
  | "exported_to_buffer"
  | "published"
  | "failed";
export type ContentValidationStatus =
  | "not_validated"
  | "ready"
  | "warning"
  | "error";

export interface ActionPlanPreferences {
  startDate: string;
  timeZone: string;
  postsPerWeek: number;
  teamSize: number | null;
  contentResources: string[];
  targetMarket: string | null;
  focusAudience: string;
}

export interface ActionPlanInput {
  snapshot: AnalysisSnapshot;
  businessGoal: BusinessGoal;
  approvedInsights: EvidenceInsight[];
  approvedStrategies: StrategyRecommendation[];
  preferences: ActionPlanPreferences;
}

export interface ExperimentDefinition {
  experimentId: string;
  hypothesis: string;
  successCriteria: string;
  reviewDate: string;
  metricIds: string[];
}

export interface WeekTask {
  taskId: string;
  title: string;
  ownerPlaceholder: string;
  dueDate: string;
  status: PlanItemStatus;
  dependencies: string[];
}

export interface FourWeekPlanItem {
  weekNumber: 1 | 2 | 3 | 4;
  dateRange: {
    start: string;
    end: string;
  };
  objective: string;
  tasks: WeekTask[];
  contentItems: string[];
  ownerPlaceholder: string;
  publishDate: string;
  targetAudience: string;
  callToAction: string;
  kpiMetricIds: string[];
  reviewAction: string;
  dependencies: string[];
}

export interface ContentCalendarItem {
  itemId: string;
  date: string;
  topic: string;
  contentFormat: string;
  targetAudience: string;
  coreMessage: string;
  postText: string;
  channel: SocialChannel;
  scheduledTime: string;
  timeZone: string;
  mediaUrls: string[];
  mediaRequirement: string | null;
  linkUrl: string | null;
  callToAction: string;
  campaignTag: string | null;
  strategyId: string;
  sourceInsightIds: string[];
  measurementMetricIds: string[];
  status: PlanItemStatus;
  workflowStatus: ContentWorkflowStatus;
  validationStatus: ContentValidationStatus;
  validationIssues: string[];
  isExperiment: boolean;
  experiment: ExperimentDefinition | null;
  ownerPlaceholder: string;
  lastEditedAt: string;
}

export interface KpiDefinition {
  metricId: string;
  label: string;
  source: "snapshot" | "future_collection";
  availability: "available" | "collect_next_import";
}

export interface KpiReviewItem {
  reviewId: string;
  reviewDate: string;
  metricIds: string[];
  action: string;
  comparisonRule: string;
}

export interface PlanRevision {
  revisionId: string;
  changedAt: string;
  changeType:
    | "calendar_item"
    | "schedule"
    | "audience"
    | "plan_status"
    | "buffer_handoff";
  summary: string;
}

export interface ActionPlan {
  schemaVersion: "1.1";
  promptVersion: "action-plan-v1.0" | "action-plan-v1.1";
  planId: string;
  snapshotId: string;
  analysisPeriod: AnalysisPeriod | null;
  generatedAt: string;
  updatedAt: string;
  sourceModules: LinkedInModule[];
  sourceInsightIds: string[];
  sourceStrategyIds: string[];
  businessGoal: BusinessGoal;
  preferences: ActionPlanPreferences;
  startDate: string;
  endDate: string;
  status: ActionPlanStatus;
  executiveSummary: string;
  assumptions: string[];
  risksAndLimitations: string[];
  fourWeekPlan: FourWeekPlanItem[];
  contentCalendar: ContentCalendarItem[];
  kpiDefinitions: KpiDefinition[];
  kpiReviewPlan: KpiReviewItem[];
  nextImportQuestions: string[];
  revisionHistory: PlanRevision[];
}

export type ActionPlanValidationCode =
  | "BUSINESS_GOAL_NOT_CONFIRMED"
  | "INSIGHT_NOT_APPROVED"
  | "INSIGHT_REFERENCE_INVALID"
  | "STRATEGY_NOT_APPROVED"
  | "STRATEGY_INSIGHT_NOT_APPROVED"
  | "SNAPSHOT_REFERENCE_MISMATCH"
  | "SNAPSHOT_BLOCKED"
  | "INVALID_TIME_ZONE"
  | "INVALID_START_DATE"
  | "START_DATE_IN_PAST"
  | "INVALID_POSTS_PER_WEEK"
  | "INVALID_PLAN_STRUCTURE"
  | "DATE_OUTSIDE_PLAN"
  | "DATE_CONFLICT"
  | "KPI_REFERENCE_INVALID"
  | "STRATEGY_REFERENCE_INVALID"
  | "EXPERIMENT_INCOMPLETE";

export interface ActionPlanValidationIssue {
  code: ActionPlanValidationCode;
  path: string;
  message: string;
}

export interface ActionPlanValidationResult {
  valid: boolean;
  issues: ActionPlanValidationIssue[];
}
