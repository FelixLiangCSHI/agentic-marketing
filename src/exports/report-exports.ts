import { listSnapshotMetrics } from "@/analysis/metric-catalog";
import type { ActionPlan } from "@/domain/action-plan";
import type {
  AnalysisPeriod,
  AnalysisSnapshot,
  Metric,
  SourceReference,
} from "@/domain/analysis";
import type { EvidenceStrategyBundle } from "@/domain/strategy";
import { csvDocument, safeFileSlug } from "@/exports/csv-utils";

export interface ReportExportInput {
  projectId: string;
  snapshot: AnalysisSnapshot;
  strategyBundle: EvidenceStrategyBundle;
  plan: ActionPlan | null;
}

export interface ExportArtifact {
  fileName: string;
  mimeType: string;
  content: string;
}

export interface ReportExportArtifacts {
  markdown: ExportArtifact;
  calendarCsv: ExportArtifact;
  structuredJson: ExportArtifact;
}

const PRIVATE_EXPORT_KEYS = new Set([
  "apiKey",
  "api_key",
  "authorization",
  "buffer",
  "bytes",
  "credentials",
  "debug",
  "internalConfig",
  "internalPrompt",
  "preview",
  "rawValues",
  "secret",
  "stack",
  "systemPrompt",
]);

function isSourceReference(value: object): value is SourceReference {
  return (
    "module" in value &&
    "fileName" in value &&
    "sheetName" in value &&
    "rowStart" in value &&
    "rowEnd" in value &&
    "fields" in value
  );
}

function publicSourceReference(reference: SourceReference) {
  return {
    sourceId: [
      reference.module,
      reference.sheetName,
      `${reference.rowStart}-${reference.rowEnd}`,
    ].join(":"),
    module: reference.module,
    sheetName: reference.sheetName,
    rowStart: reference.rowStart,
    rowEnd: reference.rowEnd,
    fields: reference.fields,
  };
}

function sanitizeForExport(value: unknown): unknown {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }

  if (Array.isArray(value)) {
    return value.map(sanitizeForExport);
  }

  if (typeof value === "object") {
    if (isSourceReference(value)) {
      return publicSourceReference(value);
    }

    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !PRIVATE_EXPORT_KEYS.has(key))
        .map(([key, child]) => [key, sanitizeForExport(child)]),
    );
  }

  return undefined;
}

function projectSlug(projectId: string): string {
  return safeFileSlug(projectId, "linkedin-project");
}

function exportFileName(
  projectId: string,
  type: "analysis-report" | "content-calendar" | "analysis-data",
  extension: "md" | "csv" | "json",
  generatedAt: Date,
): string {
  return `${projectSlug(projectId)}-${type}-${generatedAt
    .toISOString()
    .slice(0, 10)}.${extension}`;
}

function periodLabel(period: AnalysisPeriod | null): string {
  return period
    ? `${period.start} to ${period.end} (${period.granularity}, sample ${period.sampleSize})`
    : "unavailable";
}

function modulesLabel(modules: readonly string[]): string {
  return modules.length > 0 ? modules.join("、") : "unavailable";
}

function metricLine(metric: Metric): string {
  const reasons =
    metric.reliabilityReasons.length > 0
      ? metric.reliabilityReasons.join("；")
      : "No additional details";
  return [
    `- **${metric.label}** (\`${metric.metricId}\`): ${metric.formattedValue}`,
    `  - Reliability: ${metric.reliability} (${reasons})`,
    `  - Date range: ${periodLabel(metric.period)}`,
    `  - Formula: ${metric.formula}`,
    `  - Source modules: ${modulesLabel(metric.sourceModules)}`,
    `  - Evidence ID：\`${metric.metricId}\``,
  ].join("\n");
}

export function generateMarkdownReport(input: ReportExportInput): string {
  const { snapshot, strategyBundle, plan } = input;
  const metrics = listSnapshotMetrics(snapshot);
  const qualityIssues = snapshot.quality.issues;
  const insights = strategyBundle.insights;
  const strategies = strategyBundle.strategies;
  const limitations = new Set([
    "LinkedIn exports are primarily aggregate data and cannot identify visitors, followers, or individual purchase intent.",
    "The visitor-to-follower proxy is not a user-level conversion rate.",
    "Temporal correlation between publishing and metric changes does not show content caused growth.",
    "Unsupported metrics display as unavailable and are not estimated.",
    ...(plan?.risksAndLimitations ?? []),
  ]);

  const lines = [
    `# LinkedIn Marketing Analysis Report: ${input.projectId}`,
    "",
    `- Project: ${input.projectId}`,
    `- Snapshot ID：\`${snapshot.snapshotId}\``,
    `- Prepared: ${plan?.updatedAt ?? strategyBundle.generatedAt}`,
    `- Analysis period: ${periodLabel(snapshot.analysisPeriod)}`,
    `- Data modules: ${modulesLabel(snapshot.sourceModules)}`,
    `- Prompt version: ${strategyBundle.promptVersion}${
      plan ? ` / ${plan.promptVersion}` : ""
    }`,
    `- Data mode: ${snapshot.inputMode === "mock" ? "Synthetic Mock" : "User Upload"}`,
    "",
    "## Executive Summary",
    "",
    plan?.executiveSummary ??
      "Deterministic metrics and evidence-led findings are available; a confirmed 30-day action plan has not been generated.",
    "",
    "## Evidence",
    "",
    "### Data Scope",
    "",
    `- Follower records: ${snapshot.records.followers}`,
    `- Visitor records: ${snapshot.records.visitors}`,
    `- Content records: ${snapshot.records.content}`,
    `- Shared analysis period: ${periodLabel(snapshot.analysisPeriod)}`,
    "",
    "### Data Quality",
    "",
    `- Blocking issues: ${snapshot.quality.blockingIssueCount}`,
    `- Warnings: ${snapshot.quality.warningCount}`,
    `- Eligible for findings: ${snapshot.canEnterInsights ? "Yes" : "No"}`,
    ...(qualityIssues.length > 0
      ? qualityIssues.map(
          (issue) =>
            `- [${issue.severity}] \`${issue.code}\` · ${issue.module}：${issue.message}（blocksAnalysis: ${issue.blocksAnalysis ? "yes" : "no"}）`,
        )
      : ["- No quality issue is recorded; this does not establish coverage of every business question."]),
    "",
    "### Metrics",
    "",
    ...metrics.flatMap((metric) => [metricLine(metric), ""]),
    "## Key Findings",
    "",
    ...(insights.length > 0
      ? insights.flatMap((insight) => [
          `### ${insight.title}`,
          "",
          `- Status: ${insight.approvalStatus}`,
          `- ${insight.report.executiveSummary}`,
          `- Evidence IDs：${insight.evidence
            .map((item) => `\`${item.metricId}\``)
            .join("、")}`,
          "",
        ])
      : ["- No reportable finding is available.", ""]),
    "## Business Implications",
    "",
    ...(insights.length > 0
      ? insights.flatMap((insight) =>
          insight.report.businessImplications.map((item) => `- ${item}`),
        )
      : ["- No material business implication is available."]),
    "",
    "## Recommendations",
    "",
    ...(strategies.length > 0
      ? strategies.flatMap((strategy) => [
          `### ${strategy.title}`,
          "",
          `- Status: ${strategy.approvalStatus}`,
          `- ${strategy.report.executiveSummary}`,
          `- Source insights: ${strategy.insightIds
            .map((id) => `\`${id}\``)
            .join("、")}`,
          `- Evidence IDs：${strategy.metricIds
            .map((id) => `\`${id}\``)
            .join("、")}`,
          ...strategy.report.recommendations.map((action) => `- ${action}`),
          "",
        ])
      : ["- No approved recommendation is available.", ""]),
    "## Confidence Level",
    "",
    ...(insights.length > 0
      ? insights.map(
          (insight) =>
            `- ${insight.title}: ${insight.report.confidenceLevel}`,
        )
      : ["- Low"]),
    "",
    "## Observed Trends",
    "",
    ...(insights.length > 0
      ? insights.flatMap((insight) =>
          insight.report.observedTrends.map((item) => `- ${item}`),
        )
      : ["- No confirmed trend is available."]),
    "",
    "## 30-Day Action Plan",
    "",
    ...(plan
      ? [
          `- Plan ID：\`${plan.planId}\``,
          `- Status: ${plan.status}`,
          `- Plan range: ${plan.startDate} to ${plan.endDate}`,
          "- Assumptions:",
          ...plan.assumptions.map((item) => `  - ${item}`),
          "",
          ...plan.fourWeekPlan.flatMap((week) => [
            `### Week ${week.weekNumber} · ${week.dateRange.start} to ${week.dateRange.end}`,
            "",
            `- Objective: ${week.objective}`,
            `- Owner: ${week.ownerPlaceholder}`,
            `- CTA：${week.callToAction}`,
            `- KPI Evidence IDs：${week.kpiMetricIds
              .map((id) => `\`${id}\``)
              .join("、")}`,
            ...week.tasks.map(
              (task) =>
                `- Task (${task.dueDate}): ${task.title} · ${task.status}`,
            ),
            "",
          ]),
          "### Content calendar",
          "",
          ...plan.contentCalendar.map(
            (item) =>
              `- ${item.date} ${item.scheduledTime} (${item.timeZone}) · ${item.topic} · ${item.channel} · ${item.contentFormat} · Approval ${item.status} · Handoff ${item.workflowStatus}${
                item.isExperiment ? " · Experiment" : ""
              } · Strategy \`${item.strategyId}\` · KPI ${item.measurementMetricIds
                .map((id) => `\`${id}\``)
                .join("、")}`,
          ),
          "",
          "### KPI review plan",
          "",
          ...plan.kpiReviewPlan.map(
            (review) =>
              `- ${review.reviewDate} · ${review.action} · KPI ${review.metricIds
                .map((id) => `\`${id}\``)
                .join("、")} · ${review.comparisonRule}`,
          ),
          "",
          "### Questions for the next import",
          "",
          ...plan.nextImportQuestions.map((question) => `- ${question}`),
          "",
        ]
      : ["- A 30-day action plan has not been generated.", ""]),
    "## Limitations",
    "",
    ...[...limitations].map((item) => `- ${item}`),
    "",
  ];

  return lines.join("\n");
}

export function generateContentCalendarCsv(plan: ActionPlan): string {
  const rows: unknown[][] = [
    [
      "Date",
      "Time",
      "Time zone",
      "Channel",
      "Topic",
      "Content format",
      "Target audience",
      "Publishing copy",
      "Core message",
      "CTA",
      "Link",
      "Media link",
      "Strategy ID",
      "Measurement metrics",
      "Approval status",
      "Buffer workflow",
      "Experiment",
      "Experiment hypothesis",
      "Success criteria",
      "Review date",
      "Owner",
    ],
    ...plan.contentCalendar.map((item) => [
      item.date,
      item.scheduledTime,
      item.timeZone,
      item.channel,
      item.topic,
      item.contentFormat,
      item.targetAudience,
      item.postText,
      item.coreMessage,
      item.callToAction,
      item.linkUrl,
      item.mediaUrls,
      item.strategyId,
      item.measurementMetricIds,
      item.status,
      item.workflowStatus,
      item.isExperiment ? "Yes" : "No",
      item.experiment?.hypothesis ?? "",
      item.experiment?.successCriteria ?? "",
      item.experiment?.reviewDate ?? "",
      item.ownerPlaceholder,
    ]),
  ];

  return csvDocument(rows);
}

export function generateStructuredAnalysisJson(
  input: ReportExportInput,
  generatedAt: Date = new Date(),
): string {
  const payload = {
    exportVersion: "1.0",
    projectId: input.projectId,
    generatedAt: generatedAt.toISOString(),
    privacy: {
      containsRawFile: false,
      containsRawRows: false,
      sourceFileNamesOmitted: true,
      containsApiKeysOrInternalPrompts: false,
    },
    snapshot: input.snapshot,
    strategyBundle: input.strategyBundle,
    actionPlan: input.plan,
  };

  return `${JSON.stringify(sanitizeForExport(payload), null, 2)}\n`;
}

export function createReportExportArtifacts(
  input: ReportExportInput,
  generatedAt: Date = new Date(),
): ReportExportArtifacts {
  const markdown = generateMarkdownReport(input);
  const calendarCsv = input.plan ? generateContentCalendarCsv(input.plan) : "";
  const structuredJson = generateStructuredAnalysisJson(input, generatedAt);

  return {
    markdown: {
      fileName: exportFileName(
        input.projectId,
        "analysis-report",
        "md",
        generatedAt,
      ),
      mimeType: "text/markdown;charset=utf-8",
      content: markdown,
    },
    calendarCsv: {
      fileName: exportFileName(
        input.projectId,
        "content-calendar",
        "csv",
        generatedAt,
      ),
      mimeType: "text/csv;charset=utf-8",
      content: calendarCsv,
    },
    structuredJson: {
      fileName: exportFileName(
        input.projectId,
        "analysis-data",
        "json",
        generatedAt,
      ),
      mimeType: "application/json;charset=utf-8",
      content: structuredJson,
    },
  };
}
