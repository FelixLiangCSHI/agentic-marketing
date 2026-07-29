import {
  availableMetricCatalog,
  metricCatalog,
} from "@/analysis/metric-catalog";
import type {
  ActionPlan,
  ActionPlanInput,
  ActionPlanPreferences,
  ActionPlanValidationIssue,
  ActionPlanValidationResult,
  ContentCalendarItem,
  ExperimentDefinition,
  FourWeekPlanItem,
  KpiDefinition,
  PlanItemStatus,
  PlanRevision,
  SocialChannel,
  WeekTask,
} from "@/domain/action-plan";
import {
  addDays,
  isValidIanaTimeZone,
  isValidIsoDate,
  isValidTime,
  localDateInTimeZone,
} from "@/utils/date-time";
import { stableId } from "@/utils/stable-id";

export { addDays, localDateInTimeZone } from "@/utils/date-time";

const MAX_POSTS_PER_WEEK = 7;
const PLAN_DURATION_DAYS = 30;
const CONTENT_CHANNELS: readonly SocialChannel[] = [
  "linkedin_page",
  "linkedin_profile",
];
const POST_TIMES = ["09:30", "14:00", "11:00", "16:30"] as const;

const FUTURE_KPI_DEFINITIONS: readonly KpiDefinition[] = [
  {
    metricId: "future.content.itemImpressions",
    label: "Post-level impressions in the next import",
    source: "future_collection",
    availability: "collect_next_import",
  },
  {
    metricId: "future.content.itemClicks",
    label: "Post-level clicks in the next import",
    source: "future_collection",
    availability: "collect_next_import",
  },
  {
    metricId: "future.content.itemEngagementRate",
    label: "Post-level engagement rate in the next import",
    source: "future_collection",
    availability: "collect_next_import",
  },
];

const PREFERRED_SNAPSHOT_KPIS = [
  "content.impressions",
  "content.ctr",
  "content.engagementRate",
  "visitors.pageViewsTotal",
  "followers.newTotal",
] as const;

const POST_OFFSETS: Record<number, readonly number[]> = {
  1: [2],
  2: [1, 4],
  3: [1, 3, 5],
  4: [0, 2, 4, 6],
  5: [0, 1, 3, 4, 6],
  6: [0, 1, 2, 3, 4, 5],
  7: [0, 1, 2, 3, 4, 5, 6],
};

export type ActionPlanAgentErrorCode =
  | "VALIDATION_FAILED"
  | "GENERATION_CANCELLED";

export class ActionPlanAgentError extends Error {
  constructor(
    public readonly code: ActionPlanAgentErrorCode,
    message: string,
    public readonly issues: ActionPlanValidationIssue[] = [],
  ) {
    super(message);
    this.name = "ActionPlanAgentError";
  }
}

export function defaultPlanStartDate(
  timeZone: string,
  now: Date = new Date(),
): string {
  const localToday = localDateInTimeZone(now, timeZone);
  if (!localToday) {
    throw new ActionPlanAgentError(
      "VALIDATION_FAILED",
      "The workspace time zone could not be resolved.",
      [
        {
          code: "INVALID_TIME_ZONE",
          path: "preferences.timeZone",
          message: `Time zone ${timeZone} is not supported.`,
        },
      ],
    );
  }
  return addDays(localToday, 1);
}

function inputValidationIssues(
  input: ActionPlanInput,
  now: Date,
): ActionPlanValidationIssue[] {
  const issues: ActionPlanValidationIssue[] = [];
  const approvedInsightIds = new Set(
    input.approvedInsights.map((item) => item.insightId),
  );
  const knownMetrics = metricCatalog(input.snapshot);

  if (!input.snapshot.canEnterInsights) {
    issues.push({
      code: "SNAPSHOT_BLOCKED",
      path: "snapshot.canEnterInsights",
      message: "Blocking snapshot quality issues prevent plan preparation.",
    });
  }
  if (!input.businessGoal.confirmed || !input.businessGoal.statement.trim()) {
    issues.push({
      code: "BUSINESS_GOAL_NOT_CONFIRMED",
      path: "businessGoal",
      message: "Confirm the business goal first.",
    });
  }
  for (const insight of input.approvedInsights) {
    if (insight.approvalStatus !== "approved") {
      issues.push({
        code: "INSIGHT_NOT_APPROVED",
        path: `approvedInsights.${insight.insightId}`,
        message: `Insight ${insight.insightId} is not approved.`,
      });
    }
    if (insight.snapshotId !== input.snapshot.snapshotId) {
      issues.push({
        code: "SNAPSHOT_REFERENCE_MISMATCH",
        path: `approvedInsights.${insight.insightId}.snapshotId`,
        message: `Insight ${insight.insightId} does not belong to the current snapshot.`,
      });
    }
    for (const reference of insight.evidence) {
      if (!knownMetrics.has(reference.metricId)) {
        issues.push({
          code: "INSIGHT_REFERENCE_INVALID",
          path: `approvedInsights.${insight.insightId}.evidence`,
          message: `Insight ${insight.insightId} references unknown metric ${reference.metricId}.`,
        });
      }
    }
  }
  for (const strategy of input.approvedStrategies) {
    if (strategy.approvalStatus !== "approved") {
      issues.push({
        code: "STRATEGY_NOT_APPROVED",
        path: `approvedStrategies.${strategy.strategyId}`,
        message: `Strategy ${strategy.strategyId} is not approved.`,
      });
    }
    if (strategy.snapshotId !== input.snapshot.snapshotId) {
      issues.push({
        code: "SNAPSHOT_REFERENCE_MISMATCH",
        path: `approvedStrategies.${strategy.strategyId}.snapshotId`,
        message: `Strategy ${strategy.strategyId} does not belong to the current snapshot.`,
      });
    }
    for (const insightId of strategy.insightIds) {
      if (!approvedInsightIds.has(insightId)) {
        issues.push({
          code: "STRATEGY_INSIGHT_NOT_APPROVED",
          path: `approvedStrategies.${strategy.strategyId}.insightIds`,
          message: `Strategy ${strategy.strategyId} references unapproved insight ${insightId}.`,
        });
      }
    }
    for (const metricId of strategy.metricIds) {
      if (!knownMetrics.has(metricId)) {
        issues.push({
          code: "STRATEGY_REFERENCE_INVALID",
          path: `approvedStrategies.${strategy.strategyId}.metricIds`,
          message: `Strategy ${strategy.strategyId} references unknown metric ${metricId}.`,
        });
      }
    }
  }
  if (
    input.approvedInsights.length === 0 ||
    input.approvedStrategies.length === 0
  ) {
    issues.push({
      code:
        input.approvedInsights.length === 0
          ? "INSIGHT_NOT_APPROVED"
          : "STRATEGY_NOT_APPROVED",
      path:
        input.approvedInsights.length === 0
          ? "approvedInsights"
          : "approvedStrategies",
      message: "At least one approved insight and strategy are required.",
    });
  }

  const localToday = localDateInTimeZone(now, input.preferences.timeZone);
  if (!localToday) {
    issues.push({
      code: "INVALID_TIME_ZONE",
      path: "preferences.timeZone",
      message: `Time zone ${input.preferences.timeZone} is not supported.`,
    });
  }
  if (!isValidIsoDate(input.preferences.startDate)) {
    issues.push({
      code: "INVALID_START_DATE",
      path: "preferences.startDate",
      message: "The plan start date must use YYYY-MM-DD.",
    });
  } else if (localToday && input.preferences.startDate < localToday) {
    issues.push({
      code: "START_DATE_IN_PAST",
      path: "preferences.startDate",
      message: `The plan start date cannot be before ${localToday} in the workspace time zone.`,
    });
  }
  if (
    !Number.isInteger(input.preferences.postsPerWeek) ||
    input.preferences.postsPerWeek < 1 ||
    input.preferences.postsPerWeek > MAX_POSTS_PER_WEEK
  ) {
    issues.push({
      code: "INVALID_POSTS_PER_WEEK",
      path: "preferences.postsPerWeek",
      message: `Weekly publishing capacity must be an integer from 1–${MAX_POSTS_PER_WEEK}.`,
    });
  }
  return issues;
}

function ownerPlaceholder(preferences: ActionPlanPreferences): string {
  if (preferences.teamSize === null) {
    return "To assign: content owner";
  }
  return preferences.teamSize === 1
    ? "Team lead (to assign)"
    : "To assign: content planning and publishing owner";
}

function contentFormats(preferences: ActionPlanPreferences): string[] {
  const resources = preferences.contentResources.join(" ").toLowerCase();
  const formats = ["Short text post", "Document carousel"];
  if (resources.includes("video")) {
    formats.push("Short video");
  }
  if (
    resources.includes("design") ||
    resources.includes("design") ||
    resources.includes("image")
  ) {
    formats.push("Text with image");
  }
  return formats;
}

function mediaRequirement(contentFormat: string): string | null {
  if (contentFormat.includes("carousel")) {
    return "Prepare carousel assets that can be separated into individual images.";
  }
  if (contentFormat.includes("video")) {
    return "Prepare the reviewed video file for manual publishing.";
  }
  if (contentFormat.includes("image")) {
    return "Prepare one relevant image with a public direct link.";
  }
  return null;
}

function snapshotKpiDefinitions(input: ActionPlanInput): KpiDefinition[] {
  const available = availableMetricCatalog(input.snapshot);
  return PREFERRED_SNAPSHOT_KPIS.flatMap((metricId) => {
    const metric = available.get(metricId);
    return metric
      ? [
          {
            metricId,
            label: metric.label,
            source: "snapshot" as const,
            availability: "available" as const,
          },
        ]
      : [];
  });
}

function kpisForPlan(definitions: readonly KpiDefinition[]): string[] {
  const current = definitions
    .filter((definition) => definition.source === "snapshot")
    .slice(0, 3)
    .map((definition) => definition.metricId);
  return [
    ...current,
    "future.content.itemImpressions",
    "future.content.itemClicks",
    "future.content.itemEngagementRate",
  ];
}

function dateWithin(date: string, start: string, end: string): boolean {
  return date >= start && date <= end;
}

function makeRevision(
  changeType: PlanRevision["changeType"],
  summary: string,
  now: Date,
): PlanRevision {
  const changedAt = now.toISOString();
  return {
    revisionId: `revision-${changedAt.replace(/\D/g, "")}`,
    changedAt,
    changeType,
    summary,
  };
}

function buildSchedule(
  input: ActionPlanInput,
  planId: string,
  endDate: string,
  metricIds: string[],
  generatedAt: string,
): {
  fourWeekPlan: FourWeekPlanItem[];
  contentCalendar: ContentCalendarItem[];
} {
  const calendar: ContentCalendarItem[] = [];
  const weeks: FourWeekPlanItem[] = [];
  const formats = contentFormats(input.preferences);
  const owner = ownerPlaceholder(input.preferences);
  const offsets = POST_OFFSETS[input.preferences.postsPerWeek];
  const topicAngles = [
    "Clinical workflow",
    "Clinical evidence",
    "Regulatory and FDA/CE status",
    "Patient outcomes",
    "Hospital procurement and economic value",
  ];

  for (let weekIndex = 0; weekIndex < 4; weekIndex += 1) {
    const weekNumber = (weekIndex + 1) as 1 | 2 | 3 | 4;
    const weekStart = addDays(input.preferences.startDate, weekIndex * 7);
    const weekEnd = addDays(weekStart, 6);
    const strategy =
      input.approvedStrategies[weekIndex % input.approvedStrategies.length];
    const contentItems = offsets.map((offset, postIndex) => {
      const sequence = weekIndex * input.preferences.postsPerWeek + postIndex + 1;
      const itemId = `${planId}-content-${sequence}`;
      const publishDate = addDays(weekStart, offset);
      const isExperiment = postIndex === 0 && (weekNumber === 1 || weekNumber === 3);
      const experimentMetricIds = metricIds.slice(0, 3);
      const topic = `${strategy.title}：${topicAngles[postIndex % topicAngles.length]}`;
      const contentFormat = formats[(sequence - 1) % formats.length];
      const coreMessage = strategy.actions[postIndex % strategy.actions.length];
      const callToAction =
        "Review approved clinical or regulatory materials and record aggregate engagement from healthcare and procurement audiences.";
      const experiment = isExperiment
        ? {
            experimentId: `${itemId}-experiment`,
            hypothesis: `If only the format changes for "${strategy.title}", comparable post-level metrics can indicate whether to continue testing it.`,
            successCriteria: `At review, compare ${experimentMetricIds.join(
              ", ",
            )} with the current snapshot baseline; record relative change without promising fixed growth.`,
            reviewDate: addDays(
              publishDate,
              Math.min(7, Math.max(0, Number(
                (new Date(`${endDate}T00:00:00.000Z`).valueOf() -
                  new Date(`${publishDate}T00:00:00.000Z`).valueOf()) /
                  86_400_000,
              ))),
            ),
            metricIds: experimentMetricIds,
          }
        : null;
      const item: ContentCalendarItem = {
        itemId,
        date: publishDate,
        topic,
        contentFormat,
        targetAudience: input.preferences.focusAudience,
        coreMessage,
        postText: "",
        channel: CONTENT_CHANNELS[(sequence - 1) % CONTENT_CHANNELS.length],
        scheduledTime: POST_TIMES[(sequence - 1) % POST_TIMES.length],
        timeZone: input.preferences.timeZone,
        mediaUrls: [],
        mediaRequirement: mediaRequirement(contentFormat),
        linkUrl: null,
        callToAction,
        campaignTag: null,
        strategyId: strategy.strategyId,
        sourceInsightIds: [...strategy.insightIds],
        measurementMetricIds: metricIds,
        status: "ai_draft",
        workflowStatus: "planning",
        validationStatus: "not_validated",
        validationIssues: [],
        isExperiment,
        experiment,
        ownerPlaceholder: owner,
        lastEditedAt: generatedAt,
      };
      calendar.push(item);
      return itemId;
    });

    const firstPublishDate =
      calendar.find((item) => item.itemId === contentItems[0])?.date ?? weekStart;
    const lastPublishDate =
      calendar.find(
        (item) => item.itemId === contentItems[contentItems.length - 1],
      )?.date ?? weekEnd;
    const previousReviewTask =
      weekNumber > 1 ? [`week-${weekNumber - 1}-review`] : [];
    const tasks: WeekTask[] = [
      {
        taskId: `week-${weekNumber}-prepare`,
        title: "Confirm product topic, clinical evidence, regulatory wording, and one CTA",
        ownerPlaceholder: owner,
        dueDate: weekStart,
        status: "ai_draft",
        dependencies: previousReviewTask,
      },
      {
        taskId: `week-${weekNumber}-publish`,
        title: "Publish to the calendar and record execution status",
        ownerPlaceholder: owner,
        dueDate: lastPublishDate,
        status: "ai_draft",
        dependencies: [`week-${weekNumber}-prepare`],
      },
      {
        taskId: `week-${weekNumber}-review`,
        title: "Review professional-audience engagement without inferring procurement or patient outcomes",
        ownerPlaceholder: owner,
        dueDate: weekEnd,
        status: "ai_draft",
        dependencies: [`week-${weekNumber}-publish`],
      },
    ];
    weeks.push({
      weekNumber,
      dateRange: { start: weekStart, end: weekEnd },
      objective: strategy.objective,
      tasks,
      contentItems,
      ownerPlaceholder: owner,
      publishDate: firstPublishDate,
      targetAudience: input.preferences.focusAudience,
      callToAction: "Use one professional CTA to approved clinical, regulatory, or economic-value material and review aggregate metrics in the next import.",
      kpiMetricIds: metricIds,
      reviewAction:
        "Compare weekly post metrics with the snapshot baseline, recording direction and limitations without treating correlation as causation.",
      dependencies: previousReviewTask,
    });
  }

  return { fourWeekPlan: weeks, contentCalendar: calendar };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isPlanItemStatus(value: unknown): value is PlanItemStatus {
  return (
    value === "ai_draft" || value === "confirmed" || value === "rejected"
  );
}

function isSocialChannel(value: unknown): value is SocialChannel {
  return value === "linkedin_page" || value === "linkedin_profile";
}

function isContentWorkflowStatus(value: unknown): boolean {
  return [
    "planning",
    "ready_for_buffer",
    "exported_to_buffer",
    "published",
    "failed",
  ].includes(String(value));
}

function isContentValidationStatus(value: unknown): boolean {
  return ["not_validated", "ready", "warning", "error"].includes(String(value));
}

function isNullableString(value: unknown): boolean {
  return value === null || typeof value === "string";
}

function isWeekTaskShape(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.taskId === "string" &&
    typeof value.title === "string" &&
    typeof value.ownerPlaceholder === "string" &&
    typeof value.dueDate === "string" &&
    isPlanItemStatus(value.status) &&
    isStringArray(value.dependencies)
  );
}

function isFourWeekPlanItemShape(value: unknown): boolean {
  return (
    isRecord(value) &&
    [1, 2, 3, 4].includes(Number(value.weekNumber)) &&
    isRecord(value.dateRange) &&
    typeof value.dateRange.start === "string" &&
    typeof value.dateRange.end === "string" &&
    typeof value.objective === "string" &&
    Array.isArray(value.tasks) &&
    value.tasks.every(isWeekTaskShape) &&
    isStringArray(value.contentItems) &&
    typeof value.ownerPlaceholder === "string" &&
    typeof value.publishDate === "string" &&
    typeof value.targetAudience === "string" &&
    typeof value.callToAction === "string" &&
    isStringArray(value.kpiMetricIds) &&
    typeof value.reviewAction === "string" &&
    isStringArray(value.dependencies)
  );
}

function isExperimentShape(value: unknown): value is ExperimentDefinition {
  return (
    isRecord(value) &&
    typeof value.experimentId === "string" &&
    typeof value.hypothesis === "string" &&
    typeof value.successCriteria === "string" &&
    typeof value.reviewDate === "string" &&
    isStringArray(value.metricIds)
  );
}

function isCalendarItemShape(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.itemId === "string" &&
    typeof value.date === "string" &&
    typeof value.topic === "string" &&
    typeof value.contentFormat === "string" &&
    typeof value.targetAudience === "string" &&
    typeof value.coreMessage === "string" &&
    typeof value.postText === "string" &&
    isSocialChannel(value.channel) &&
    typeof value.scheduledTime === "string" &&
    typeof value.timeZone === "string" &&
    isStringArray(value.mediaUrls) &&
    isNullableString(value.mediaRequirement) &&
    isNullableString(value.linkUrl) &&
    typeof value.callToAction === "string" &&
    isNullableString(value.campaignTag) &&
    typeof value.strategyId === "string" &&
    isStringArray(value.sourceInsightIds) &&
    isStringArray(value.measurementMetricIds) &&
    isPlanItemStatus(value.status) &&
    isContentWorkflowStatus(value.workflowStatus) &&
    isContentValidationStatus(value.validationStatus) &&
    isStringArray(value.validationIssues) &&
    typeof value.isExperiment === "boolean" &&
    (value.experiment === null || isExperimentShape(value.experiment)) &&
    typeof value.ownerPlaceholder === "string" &&
    typeof value.lastEditedAt === "string"
  );
}

function isKpiDefinitionShape(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.metricId === "string" &&
    typeof value.label === "string" &&
    (value.source === "snapshot" || value.source === "future_collection") &&
    (value.availability === "available" ||
      value.availability === "collect_next_import")
  );
}

function isKpiReviewShape(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.reviewId === "string" &&
    typeof value.reviewDate === "string" &&
    isStringArray(value.metricIds) &&
    typeof value.action === "string" &&
    typeof value.comparisonRule === "string"
  );
}

function isPlanRevisionShape(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.revisionId === "string" &&
    typeof value.changedAt === "string" &&
    [
      "calendar_item",
      "schedule",
      "audience",
      "plan_status",
      "buffer_handoff",
    ].includes(String(value.changeType)) &&
    typeof value.summary === "string"
  );
}

export function isActionPlanShape(value: unknown): value is ActionPlan {
  if (!isRecord(value)) {
    return false;
  }
  const candidate = value;
  return (
    candidate.schemaVersion === "1.1" &&
    (candidate.promptVersion === "action-plan-v1.0" ||
      candidate.promptVersion === "action-plan-v1.1") &&
    typeof candidate.planId === "string" &&
    typeof candidate.snapshotId === "string" &&
    (candidate.analysisPeriod === null ||
      (isRecord(candidate.analysisPeriod) &&
        typeof candidate.analysisPeriod.start === "string" &&
        typeof candidate.analysisPeriod.end === "string" &&
        typeof candidate.analysisPeriod.granularity === "string" &&
        typeof candidate.analysisPeriod.sampleSize === "number")) &&
    typeof candidate.generatedAt === "string" &&
    typeof candidate.updatedAt === "string" &&
    isStringArray(candidate.sourceModules) &&
    isStringArray(candidate.sourceInsightIds) &&
    isStringArray(candidate.sourceStrategyIds) &&
    isRecord(candidate.businessGoal) &&
    typeof candidate.businessGoal.goalId === "string" &&
    typeof candidate.businessGoal.statement === "string" &&
    typeof candidate.businessGoal.confirmed === "boolean" &&
    typeof candidate.businessGoal.confirmedAt === "string" &&
    isRecord(candidate.preferences) &&
    typeof candidate.preferences.startDate === "string" &&
    typeof candidate.preferences.timeZone === "string" &&
    typeof candidate.preferences.postsPerWeek === "number" &&
    Array.isArray(candidate.preferences.contentResources) &&
    candidate.preferences.contentResources.every(
      (resource) => typeof resource === "string",
    ) &&
    (candidate.preferences.teamSize === null ||
      typeof candidate.preferences.teamSize === "number") &&
    (candidate.preferences.targetMarket === null ||
      typeof candidate.preferences.targetMarket === "string") &&
    typeof candidate.preferences.focusAudience === "string" &&
    typeof candidate.startDate === "string" &&
    typeof candidate.endDate === "string" &&
    (candidate.status === "ai_draft" ||
      candidate.status === "user_confirmed" ||
      candidate.status === "revision_requested" ||
      candidate.status === "rejected") &&
    typeof candidate.executiveSummary === "string" &&
    isStringArray(candidate.assumptions) &&
    isStringArray(candidate.risksAndLimitations) &&
    Array.isArray(candidate.fourWeekPlan) &&
    candidate.fourWeekPlan.every(isFourWeekPlanItemShape) &&
    Array.isArray(candidate.contentCalendar) &&
    candidate.contentCalendar.every(isCalendarItemShape) &&
    Array.isArray(candidate.kpiDefinitions) &&
    candidate.kpiDefinitions.every(isKpiDefinitionShape) &&
    Array.isArray(candidate.kpiReviewPlan) &&
    candidate.kpiReviewPlan.every(isKpiReviewShape) &&
    isStringArray(candidate.nextImportQuestions) &&
    Array.isArray(candidate.revisionHistory) &&
    candidate.revisionHistory.every(isPlanRevisionShape)
  );
}

function migrateLegacyCalendarItem(
  value: unknown,
  index: number,
  timeZone: string,
  sourceInsightIds: string[],
  updatedAt: string,
): ContentCalendarItem | null {
  if (
    !isRecord(value) ||
    typeof value.itemId !== "string" ||
    typeof value.date !== "string" ||
    typeof value.topic !== "string" ||
    typeof value.contentFormat !== "string" ||
    typeof value.targetAudience !== "string" ||
    typeof value.coreMessage !== "string" ||
    typeof value.callToAction !== "string" ||
    typeof value.strategyId !== "string" ||
    !isStringArray(value.measurementMetricIds) ||
    !isPlanItemStatus(value.status) ||
    typeof value.isExperiment !== "boolean" ||
    (value.experiment !== null && !isExperimentShape(value.experiment)) ||
    typeof value.ownerPlaceholder !== "string"
  ) {
    return null;
  }
  const topic = value.topic;
  const coreMessage = value.coreMessage;
  const callToAction = value.callToAction;
  return {
    itemId: value.itemId,
    date: value.date,
    topic,
    contentFormat: value.contentFormat,
    targetAudience: value.targetAudience,
    coreMessage,
    postText: `${topic}\n\n${coreMessage}\n\n${callToAction}`,
    channel: CONTENT_CHANNELS[index % CONTENT_CHANNELS.length],
    scheduledTime: POST_TIMES[index % POST_TIMES.length],
    timeZone,
    mediaUrls: [],
    mediaRequirement: mediaRequirement(value.contentFormat),
    linkUrl: null,
    callToAction,
    campaignTag: null,
    strategyId: value.strategyId,
    sourceInsightIds: [...sourceInsightIds],
    measurementMetricIds: [...value.measurementMetricIds],
    status: value.status,
    workflowStatus: "planning",
    validationStatus: "not_validated",
    validationIssues: [],
    isExperiment: value.isExperiment,
    experiment: value.experiment,
    ownerPlaceholder: value.ownerPlaceholder,
    lastEditedAt: updatedAt,
  };
}

export function normalizeActionPlan(value: unknown): ActionPlan | null {
  if (isActionPlanShape(value)) {
    return value;
  }
  if (
    !isRecord(value) ||
    value.schemaVersion !== "1.0" ||
    value.promptVersion !== "action-plan-v1.0" ||
    !isStringArray(value.sourceInsightIds) ||
    typeof value.updatedAt !== "string" ||
    !Array.isArray(value.contentCalendar)
  ) {
    return null;
  }
  const preferences = value.preferences;
  if (!isRecord(preferences) || typeof preferences.timeZone !== "string") {
    return null;
  }
  const timeZone = preferences.timeZone;
  const sourceInsightIds = value.sourceInsightIds;
  const updatedAt = value.updatedAt;
  const migratedItems = value.contentCalendar.map((item, index) =>
    migrateLegacyCalendarItem(
      item,
      index,
      timeZone,
      sourceInsightIds,
      updatedAt,
    ),
  );
  if (migratedItems.some((item) => item === null)) {
    return null;
  }
  const migrated = {
    ...value,
    schemaVersion: "1.1",
    contentCalendar: migratedItems,
  };
  return isActionPlanShape(migrated) ? migrated : null;
}

export function validateActionPlan(
  plan: unknown,
  input: ActionPlanInput,
  now: Date = new Date(),
): ActionPlanValidationResult {
  const issues = inputValidationIssues(input, now);
  if (!isActionPlanShape(plan)) {
    issues.push({
      code: "INVALID_PLAN_STRUCTURE",
      path: "plan",
      message: "Plan output does not match the ActionPlan structure.",
    });
    return { valid: false, issues };
  }

  const approvedInsightIds = new Set(
    input.approvedInsights.map((item) => item.insightId),
  );
  const approvedStrategyIds = new Set(
    input.approvedStrategies.map((item) => item.strategyId),
  );
  const availableMetrics = availableMetricCatalog(input.snapshot);
  const kpiDefinitions = new Map(
    plan.kpiDefinitions.map((definition) => [
      definition.metricId,
      definition,
    ]),
  );
  const allKpiReferences: Array<{ path: string; metricId: string }> = [];
  const taskIds = new Set(
    plan.fourWeekPlan.flatMap((week) =>
      week.tasks.map((task) => task.taskId),
    ),
  );
  const contentItemIds = new Set(
    plan.contentCalendar.map((item) => item.itemId),
  );

  if (plan.snapshotId !== input.snapshot.snapshotId) {
    issues.push({
      code: "SNAPSHOT_REFERENCE_MISMATCH",
      path: "plan.snapshotId",
      message: "The plan does not reference the current snapshot.",
    });
  }
  if (
    plan.startDate !== input.preferences.startDate ||
    plan.preferences.startDate !== input.preferences.startDate ||
    plan.preferences.timeZone !== input.preferences.timeZone ||
    plan.preferences.postsPerWeek !== input.preferences.postsPerWeek ||
    !isValidIsoDate(plan.startDate) ||
    !isValidIsoDate(plan.endDate) ||
    plan.endDate !== addDays(plan.startDate, PLAN_DURATION_DAYS - 1)
  ) {
    issues.push({
      code: "INVALID_PLAN_STRUCTURE",
      path: "plan.preferences",
      message: "The plan did not preserve the confirmed date, time zone, or publishing capacity.",
    });
  }
  for (const insightId of plan.sourceInsightIds) {
    if (!approvedInsightIds.has(insightId)) {
      issues.push({
        code: "INSIGHT_NOT_APPROVED",
        path: "plan.sourceInsightIds",
        message: `The plan references unapproved insight ${insightId}.`,
      });
    }
  }
  for (const strategyId of plan.sourceStrategyIds) {
    if (!approvedStrategyIds.has(strategyId)) {
      issues.push({
        code: "STRATEGY_NOT_APPROVED",
        path: "plan.sourceStrategyIds",
        message: `The plan references unapproved strategy ${strategyId}.`,
      });
    }
  }
  if (
    plan.sourceInsightIds.length !== approvedInsightIds.size ||
    [...approvedInsightIds].some(
      (insightId) => !plan.sourceInsightIds.includes(insightId),
    )
  ) {
    issues.push({
      code: "INSIGHT_REFERENCE_INVALID",
      path: "plan.sourceInsightIds",
      message: "The plan must retain every approved insight reference.",
    });
  }
  if (
    plan.sourceStrategyIds.length !== approvedStrategyIds.size ||
    [...approvedStrategyIds].some(
      (strategyId) => !plan.sourceStrategyIds.includes(strategyId),
    )
  ) {
    issues.push({
      code: "STRATEGY_REFERENCE_INVALID",
      path: "plan.sourceStrategyIds",
      message: "The plan must retain every approved strategy reference.",
    });
  }
  if (plan.fourWeekPlan.length !== 4) {
    issues.push({
      code: "INVALID_PLAN_STRUCTURE",
      path: "plan.fourWeekPlan",
      message: "The action plan must contain exactly four weeks.",
    });
  }

  const localToday = localDateInTimeZone(now, plan.preferences.timeZone);
  const seenDates = new Set<string>();
  for (const item of plan.contentCalendar) {
    if (
      !isValidTime(item.scheduledTime) ||
      !isValidIanaTimeZone(item.timeZone)
    ) {
      issues.push({
        code: "INVALID_PLAN_STRUCTURE",
        path: `plan.contentCalendar.${item.itemId}.scheduledTime`,
        message: `Content item ${item.itemId} has an invalid publishing time or time zone.`,
      });
    }
    if (
      !dateWithin(item.date, plan.startDate, plan.endDate) ||
      (localToday !== null && item.date < localToday)
    ) {
      issues.push({
        code: "DATE_OUTSIDE_PLAN",
        path: `plan.contentCalendar.${item.itemId}.date`,
        message: `Content date ${item.date} is outside the plan range.`,
      });
    }
    if (seenDates.has(item.date)) {
      issues.push({
        code: "DATE_CONFLICT",
        path: `plan.contentCalendar.${item.itemId}.date`,
        message: `Content on ${item.date} has an unexplained publishing conflict.`,
      });
    }
    seenDates.add(item.date);
    if (!approvedStrategyIds.has(item.strategyId)) {
      issues.push({
        code: "STRATEGY_REFERENCE_INVALID",
        path: `plan.contentCalendar.${item.itemId}.strategyId`,
        message: `The content item references unapproved strategy ${item.strategyId}.`,
      });
    }
    for (const insightId of item.sourceInsightIds) {
      if (!approvedInsightIds.has(insightId)) {
        issues.push({
          code: "INSIGHT_REFERENCE_INVALID",
          path: `plan.contentCalendar.${item.itemId}.sourceInsightIds`,
          message: `The content item references unapproved insight ${insightId}.`,
        });
      }
    }
    item.measurementMetricIds.forEach((metricId) =>
      allKpiReferences.push({
        path: `plan.contentCalendar.${item.itemId}.measurementMetricIds`,
        metricId,
      }),
    );
    if (
      item.isExperiment &&
      (!item.experiment ||
        !item.experiment.hypothesis.trim() ||
        !item.experiment.successCriteria.trim() ||
        !isValidIsoDate(item.experiment.reviewDate) ||
        item.experiment.reviewDate < item.date ||
        item.experiment.reviewDate > plan.endDate ||
        item.experiment.metricIds.length === 0)
    ) {
      issues.push({
        code: "EXPERIMENT_INCOMPLETE",
        path: `plan.contentCalendar.${item.itemId}.experiment`,
        message: "Experiments require a hypothesis, success criteria, review date, and KPI.",
      });
    }
    item.experiment?.metricIds.forEach((metricId) =>
      allKpiReferences.push({
        path: `plan.contentCalendar.${item.itemId}.experiment.metricIds`,
        metricId,
      }),
    );
  }
  if (!plan.contentCalendar.some((item) => item.isExperiment)) {
    issues.push({
      code: "EXPERIMENT_INCOMPLETE",
      path: "plan.contentCalendar",
      message: "The plan requires at least one clearly marked experiment.",
    });
  }
  if (
    contentItemIds.size !== plan.contentCalendar.length ||
    plan.contentCalendar.length !== plan.preferences.postsPerWeek * 4
  ) {
    issues.push({
      code: "INVALID_PLAN_STRUCTURE",
      path: "plan.contentCalendar",
      message: "The calendar must contain unique items within weekly capacity for all four weeks.",
    });
  }

  const referencedContentItems = plan.fourWeekPlan.flatMap(
    (week) => week.contentItems,
  );
  for (const week of plan.fourWeekPlan) {
    const expectedWeekStart = addDays(
      plan.startDate,
      (week.weekNumber - 1) * 7,
    );
    if (
      week.contentItems.length !== plan.preferences.postsPerWeek ||
      week.dateRange.start !== expectedWeekStart ||
      week.dateRange.end !== addDays(expectedWeekStart, 6) ||
      !dateWithin(week.publishDate, week.dateRange.start, week.dateRange.end)
    ) {
      issues.push({
        code: "INVALID_PLAN_STRUCTURE",
        path: `plan.fourWeekPlan.${week.weekNumber}`,
        message: `Week ${week.weekNumber} dates or item count do not match the settings.`,
      });
    }
    if (
      week.contentItems.some((itemId) => !contentItemIds.has(itemId)) ||
      week.dependencies.some((taskId) => !taskIds.has(taskId))
    ) {
      issues.push({
        code: "INVALID_PLAN_STRUCTURE",
        path: `plan.fourWeekPlan.${week.weekNumber}`,
        message: `Week ${week.weekNumber} has an invalid content or task dependency reference.`,
      });
    }
    for (const task of week.tasks) {
      if (
        !dateWithin(task.dueDate, plan.startDate, plan.endDate) ||
        task.dependencies.includes(task.taskId) ||
        task.dependencies.some((taskId) => !taskIds.has(taskId))
      ) {
        issues.push({
          code: "INVALID_PLAN_STRUCTURE",
          path: `plan.fourWeekPlan.${week.weekNumber}.tasks.${task.taskId}`,
          message: `Task ${task.taskId} has an invalid date or dependency.`,
        });
      }
    }
    week.kpiMetricIds.forEach((metricId) =>
      allKpiReferences.push({
        path: `plan.fourWeekPlan.${week.weekNumber}.kpiMetricIds`,
        metricId,
      }),
    );
  }
  if (
    referencedContentItems.length !== contentItemIds.size ||
    new Set(referencedContentItems).size !== referencedContentItems.length
  ) {
    issues.push({
      code: "INVALID_PLAN_STRUCTURE",
      path: "plan.fourWeekPlan.contentItems",
      message: "Content references in the four-week plan must be unique and complete.",
    });
  }
  for (const review of plan.kpiReviewPlan) {
    if (!dateWithin(review.reviewDate, plan.startDate, plan.endDate)) {
      issues.push({
        code: "DATE_OUTSIDE_PLAN",
        path: `plan.kpiReviewPlan.${review.reviewId}.reviewDate`,
        message: `KPI review date ${review.reviewDate} is outside the plan range.`,
      });
    }
    review.metricIds.forEach((metricId) =>
      allKpiReferences.push({
        path: `plan.kpiReviewPlan.${review.reviewId}.metricIds`,
        metricId,
      }),
    );
  }

  for (const [metricId, definition] of kpiDefinitions) {
    if (
      definition.source === "snapshot" &&
      !availableMetrics.has(metricId)
    ) {
      issues.push({
        code: "KPI_REFERENCE_INVALID",
        path: `plan.kpiDefinitions.${metricId}`,
        message: `KPI ${metricId} is unavailable in the current snapshot.`,
      });
    }
    if (
      definition.source === "future_collection" &&
      !FUTURE_KPI_DEFINITIONS.some(
        (candidate) => candidate.metricId === metricId,
      )
    ) {
      issues.push({
        code: "KPI_REFERENCE_INVALID",
        path: `plan.kpiDefinitions.${metricId}`,
        message: `Future KPI ${metricId} is not in the approved measurement catalog.`,
      });
    }
  }
  if (kpiDefinitions.size !== plan.kpiDefinitions.length) {
    issues.push({
      code: "KPI_REFERENCE_INVALID",
      path: "plan.kpiDefinitions",
      message: "KPI definitions contain duplicate metric IDs.",
    });
  }
  for (const reference of allKpiReferences) {
    if (!kpiDefinitions.has(reference.metricId)) {
      issues.push({
        code: "KPI_REFERENCE_INVALID",
        path: reference.path,
        message: `KPI reference ${reference.metricId} has no valid definition.`,
      });
    }
  }

  const calendarByWeek = new Map<number, number>();
  for (const item of plan.contentCalendar) {
    const daysFromStart =
      (new Date(`${item.date}T00:00:00.000Z`).valueOf() -
        new Date(`${plan.startDate}T00:00:00.000Z`).valueOf()) /
      86_400_000;
    const week = Math.floor(daysFromStart / 7) + 1;
    calendarByWeek.set(week, (calendarByWeek.get(week) ?? 0) + 1);
  }
  for (let week = 1; week <= 4; week += 1) {
    if ((calendarByWeek.get(week) ?? 0) > plan.preferences.postsPerWeek) {
      issues.push({
        code: "INVALID_POSTS_PER_WEEK",
        path: `plan.contentCalendar.week${week}`,
        message: `Week ${week} exceeds the configured content limit.`,
      });
    }
  }

  return { valid: issues.length === 0, issues };
}

export function generateActionPlan(
  input: ActionPlanInput,
  now: Date = new Date(),
): ActionPlan {
  const inputIssues = inputValidationIssues(input, now);
  if (inputIssues.length > 0) {
    throw new ActionPlanAgentError(
      "VALIDATION_FAILED",
      inputIssues[0].message,
      inputIssues,
    );
  }

  const generatedAt = now.toISOString();
  const planId = stableId(
    "plan",
    JSON.stringify({
      snapshotId: input.snapshot.snapshotId,
      goalId: input.businessGoal.goalId,
      insightIds: input.approvedInsights
        .map((item) => item.insightId)
        .sort(),
      strategyIds: input.approvedStrategies
        .map((item) => item.strategyId)
        .sort(),
      preferences: input.preferences,
    }),
  );
  const endDate = addDays(input.preferences.startDate, PLAN_DURATION_DAYS - 1);
  const currentDefinitions = snapshotKpiDefinitions(input);
  const kpiDefinitions = [
    ...currentDefinitions,
    ...FUTURE_KPI_DEFINITIONS,
  ];
  const kpiMetricIds = kpisForPlan(kpiDefinitions);
  const schedule = buildSchedule(
    input,
    planId,
    endDate,
    kpiMetricIds,
    generatedAt,
  );
  const userTarget = input.businessGoal.userDefinedTarget;
  const targetStatement = userTarget
    ? ` The confirmed target is ${userTarget.metricId} at ${userTarget.value} ${userTarget.unit}; this value is a user-defined objective, not a forecast.`
    : "";
  const executiveSummary = `The four-week plan operationalizes the confirmed business goal, “${input.businessGoal.statement},” through a consistent publishing cadence, controlled experiments, and scheduled performance reviews. The plan does not forecast growth or apply individual-level attribution.${targetStatement}`;
  const plan: ActionPlan = {
    schemaVersion: "1.1",
    promptVersion: "action-plan-v1.1",
    planId,
    snapshotId: input.snapshot.snapshotId,
    analysisPeriod: input.snapshot.analysisPeriod,
    generatedAt,
    updatedAt: generatedAt,
    sourceModules: input.snapshot.sourceModules,
    sourceInsightIds: input.approvedInsights.map((item) => item.insightId),
    sourceStrategyIds: input.approvedStrategies.map((item) => item.strategyId),
    businessGoal: input.businessGoal,
    preferences: { ...input.preferences },
    startDate: input.preferences.startDate,
    endDate,
    status: "ai_draft",
    executiveSummary,
    report: {
      executiveSummary,
      keyFindings: input.approvedInsights.map(
        (insight) => insight.report.executiveSummary,
      ),
      businessImplications: input.approvedStrategies.map(
        (strategy) => strategy.report.businessImplications[0] ?? strategy.objective,
      ),
      recommendations: input.approvedStrategies.flatMap(
        (strategy) => strategy.actions,
      ),
      confidenceLevel: input.approvedInsights.some(
        (insight) => insight.confidence === "low",
      )
        ? "Low"
        : input.approvedInsights.every(
              (insight) => insight.confidence === "high",
            )
          ? "High"
          : "Medium",
      evidence: input.approvedInsights.flatMap((insight) =>
        insight.evidence.map(
          (reference) =>
            `${reference.label}: ${reference.formattedValue} (${reference.metricId})`,
        ),
      ),
      observedTrends: input.approvedInsights.flatMap(
        (insight) => insight.report.observedTrends,
      ),
    },
    assumptions: [
      input.preferences.teamSize === null
        ? "Team size is not specified; owner fields remain unassigned."
        : `Confirmed team size: ${input.preferences.teamSize}. Named owners remain to be assigned.`,
      input.preferences.contentResources.length === 0
        ? "No content-resource inventory is available; the plan uses text posts and document carousels."
        : `Available content resources: ${input.preferences.contentResources.join(", ")}.`,
      `Maximum weekly publishing volume: ${input.preferences.postsPerWeek}; time zone: ${input.preferences.timeZone}.`,
    ],
    risksAndLimitations: [
      "LinkedIn data is aggregated and cannot verify healthcare professional roles, KOL identities, or hospital procurement intent.",
      "The Visitor-to-Follower Proxy is not a verified user-level conversion rate.",
      "Correlation between publishing windows and metric changes does not establish causation.",
      "Future KPI results require like-for-like collection in the next import and cannot be forecast from the current data.",
    ],
    ...schedule,
    kpiDefinitions,
    kpiReviewPlan: schedule.fourWeekPlan.map((week) => ({
      reviewId: `week-${week.weekNumber}-kpi-review`,
      reviewDate: week.dateRange.end,
      metricIds: week.kpiMetricIds,
      action: week.reviewAction,
      comparisonRule:
        "Compare only with the current snapshot baseline and equivalent future data; do not describe correlation as causation.",
    })),
    nextImportQuestions: [
      "Does the next import cover the complete plan date range?",
      "Are post-level impressions, clicks, and engagement rates available under consistent definitions?",
      "Which experiments were published as planned, changed, or cancelled?",
      "Are compliant records of professional engagement, expert feedback, or procurement milestones available to validate outcomes?",
    ],
    revisionHistory: [],
  };

  const validation = validateActionPlan(plan, input, now);
  if (!validation.valid) {
    throw new ActionPlanAgentError(
      "VALIDATION_FAILED",
      validation.issues[0].message,
      validation.issues,
    );
  }
  return plan;
}

function waitForGeneration(
  delayMs: number,
  signal: AbortSignal | undefined,
): Promise<void> {
  if (signal?.aborted) {
    return Promise.reject(
      new ActionPlanAgentError("GENERATION_CANCELLED", "Plan preparation was cancelled."),
    );
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, delayMs);
    function onAbort() {
      clearTimeout(timer);
      reject(
        new ActionPlanAgentError("GENERATION_CANCELLED", "Plan preparation was cancelled."),
      );
    }
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

export async function runActionPlanAgent(
  input: ActionPlanInput,
  options: {
    signal?: AbortSignal;
    delayMs?: number;
    now?: Date;
  } = {},
): Promise<ActionPlan> {
  await waitForGeneration(options.delayMs ?? 350, options.signal);
  if (options.signal?.aborted) {
    throw new ActionPlanAgentError(
      "GENERATION_CANCELLED",
      "Plan preparation was cancelled.",
    );
  }
  return generateActionPlan(input, options.now);
}

export interface ActionPlanModelAdapter {
  mode: "mock" | "model";
  generate(
    input: ActionPlanInput,
    options: { signal?: AbortSignal },
  ): Promise<unknown>;
}

export async function runValidatedActionPlanAdapter(
  adapter: ActionPlanModelAdapter,
  input: ActionPlanInput,
  options: {
    signal?: AbortSignal;
    now?: Date;
  } = {},
): Promise<ActionPlan> {
  if (options.signal?.aborted) {
    throw new ActionPlanAgentError(
      "GENERATION_CANCELLED",
      "Plan preparation was cancelled.",
    );
  }
  const output = await adapter.generate(input, { signal: options.signal });
  if (options.signal?.aborted) {
    throw new ActionPlanAgentError(
      "GENERATION_CANCELLED",
      "Plan preparation was cancelled.",
    );
  }
  const validation = validateActionPlan(output, input, options.now);
  if (!validation.valid || !isActionPlanShape(output)) {
    throw new ActionPlanAgentError(
      "VALIDATION_FAILED",
      validation.issues[0]?.message ?? "Plan output structure is invalid.",
      validation.issues,
    );
  }
  return output;
}

export function reviseCalendarItem(
  plan: ActionPlan,
  itemId: string,
  patch: Partial<
    Pick<
      ContentCalendarItem,
      | "topic"
      | "contentFormat"
      | "targetAudience"
      | "postText"
      | "channel"
      | "date"
      | "scheduledTime"
      | "timeZone"
      | "mediaUrls"
      | "linkUrl"
      | "callToAction"
      | "campaignTag"
      | "status"
    >
  >,
  now: Date = new Date(),
): ActionPlan {
  const item = plan.contentCalendar.find((candidate) => candidate.itemId === itemId);
  if (!item) {
    throw new Error(`Unknown content calendar item: ${itemId}`);
  }
  const updatedAt = now.toISOString();
  return {
    ...plan,
    status: "ai_draft",
    updatedAt,
    contentCalendar: plan.contentCalendar.map((candidate) => {
      if (candidate.itemId !== itemId) {
        return candidate;
      }
      const revised: ContentCalendarItem =
        {
          ...candidate,
          ...patch,
          mediaRequirement:
            patch.contentFormat === undefined
              ? candidate.mediaRequirement
              : mediaRequirement(patch.contentFormat),
          workflowStatus: "planning",
          validationStatus: "not_validated",
          validationIssues: [],
          lastEditedAt: updatedAt,
        };
      return {
        ...revised,
        postText: patch.postText === undefined ? "" : revised.postText,
        status:
          patch.status ??
          (revised.status === "rejected" ? "rejected" : "ai_draft"),
        workflowStatus: "planning",
      };
    }),
    revisionHistory: [
      ...plan.revisionHistory,
      makeRevision(
        "calendar_item",
        `Updated content item ${itemId}: ${Object.keys(patch).join(", ")}`,
        now,
      ),
    ],
  };
}

export function reviseActionPlanSchedule(
  plan: ActionPlan,
  input: ActionPlanInput,
  preferences: ActionPlanPreferences,
  now: Date = new Date(),
): ActionPlan {
  const regenerated = generateActionPlan(
    { ...input, preferences },
    now,
  );
  return {
    ...plan,
    preferences: regenerated.preferences,
    startDate: regenerated.startDate,
    endDate: regenerated.endDate,
    updatedAt: now.toISOString(),
    status: "ai_draft",
    fourWeekPlan: regenerated.fourWeekPlan,
    contentCalendar: regenerated.contentCalendar,
    kpiReviewPlan: regenerated.kpiReviewPlan,
    assumptions: regenerated.assumptions,
    revisionHistory: [
      ...plan.revisionHistory,
      makeRevision(
        preferences.focusAudience !== plan.preferences.focusAudience
          ? "audience"
          : "schedule",
        "Updated the plan start date, publishing capacity, or focus audience without rerunning the snapshot.",
        now,
      ),
    ],
  };
}

export function confirmActionPlan(
  plan: ActionPlan,
  now: Date = new Date(),
): ActionPlan {
  return {
    ...plan,
    status: "user_confirmed",
    updatedAt: now.toISOString(),
    fourWeekPlan: plan.fourWeekPlan.map((week) => ({
      ...week,
      tasks: week.tasks.map((task) => ({
        ...task,
        status: task.status === "rejected" ? "rejected" : "confirmed",
      })),
    })),
    contentCalendar: plan.contentCalendar.map((item) => ({
      ...item,
      status: item.status === "rejected" ? "rejected" : "confirmed",
      postText:
        item.status === "rejected"
          ? ""
          : `${item.topic}\n\n${item.coreMessage}\n\n${item.callToAction}`,
    })),
    revisionHistory: [
      ...plan.revisionHistory,
      makeRevision("plan_status", "Reviewer approved the current action plan.", now),
    ],
  };
}

export function reviewActionPlan(
  plan: ActionPlan,
  status: "revision_requested" | "rejected",
  now: Date = new Date(),
): ActionPlan {
  return {
    ...plan,
    status,
    updatedAt: now.toISOString(),
    fourWeekPlan: plan.fourWeekPlan.map((week) => ({
      ...week,
      tasks: week.tasks.map((task) => ({
        ...task,
        status: task.status === "rejected" ? "rejected" : "ai_draft",
      })),
    })),
    contentCalendar: plan.contentCalendar.map((item) => ({
      ...item,
      postText: "",
      status: item.status === "rejected" ? "rejected" : "ai_draft",
      workflowStatus: "planning",
    })),
    revisionHistory: [
      ...plan.revisionHistory,
      makeRevision(
        "plan_status",
        status === "rejected"
          ? "Reviewer rejected the current action plan."
          : "Reviewer requested revisions to the current action plan.",
        now,
      ),
    ],
  };
}
