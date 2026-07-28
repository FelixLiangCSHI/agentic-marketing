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
    ? `${period.start} 至 ${period.end}（${period.granularity}，样本 ${period.sampleSize}）`
    : "unavailable";
}

function modulesLabel(modules: readonly string[]): string {
  return modules.length > 0 ? modules.join("、") : "unavailable";
}

function metricLine(metric: Metric): string {
  const reasons =
    metric.reliabilityReasons.length > 0
      ? metric.reliabilityReasons.join("；")
      : "无额外说明";
  return [
    `- **${metric.label}** (\`${metric.metricId}\`): ${metric.formattedValue}`,
    `  - 可靠性：${metric.reliability}（${reasons}）`,
    `  - 时间范围：${periodLabel(metric.period)}`,
    `  - 公式：${metric.formula}`,
    `  - 来源模块：${modulesLabel(metric.sourceModules)}`,
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
    "LinkedIn 导出主要为聚合数据，不能识别匿名访客、具体关注者或个人购买意向。",
    "Visitor-to-Follower Proxy 不是用户级真实转化率。",
    "发布窗口与指标变化的时间相关性不代表内容导致增长。",
    "无法支持的指标显示 unavailable，不进行估算。",
    ...(plan?.risksAndLimitations ?? []),
  ]);

  const lines = [
    `# LinkedIn Marketing 分析报告：${input.projectId}`,
    "",
    `- 项目标识：${input.projectId}`,
    `- Snapshot ID：\`${snapshot.snapshotId}\``,
    `- 生成时间：${plan?.updatedAt ?? strategyBundle.generatedAt}`,
    `- 分析时间范围：${periodLabel(snapshot.analysisPeriod)}`,
    `- 数据模块：${modulesLabel(snapshot.sourceModules)}`,
    `- Prompt 版本：${strategyBundle.promptVersion}${
      plan ? ` / ${plan.promptVersion}` : ""
    }`,
    `- 数据模式：${snapshot.inputMode === "mock" ? "Synthetic Mock" : "用户上传"}`,
    "",
    "## Executive Summary",
    "",
    plan?.executiveSummary ??
      "当前已完成确定性指标和证据洞察，尚未生成经用户确认的 30 天行动计划。",
    "",
    "## 数据范围",
    "",
    `- Followers 记录：${snapshot.records.followers}`,
    `- Visitors 记录：${snapshot.records.visitors}`,
    `- Content 记录：${snapshot.records.content}`,
    `- 共同分析范围：${periodLabel(snapshot.analysisPeriod)}`,
    "",
    "## 数据质量",
    "",
    `- 阻断问题：${snapshot.quality.blockingIssueCount}`,
    `- Warning：${snapshot.quality.warningCount}`,
    `- 可进入洞察：${snapshot.canEnterInsights ? "是" : "否"}`,
    ...(qualityIssues.length > 0
      ? qualityIssues.map(
          (issue) =>
            `- [${issue.severity}] \`${issue.code}\` · ${issue.module}：${issue.message}（blocksAnalysis: ${issue.blocksAnalysis ? "yes" : "no"}）`,
        )
      : ["- 未记录质量问题；这不代表数据能够回答所有业务问题。"]),
    "",
    "## 指标",
    "",
    ...metrics.flatMap((metric) => [metricLine(metric), ""]),
    "## 洞察",
    "",
    ...(insights.length > 0
      ? insights.flatMap((insight) => [
          `### ${insight.title}`,
          "",
          `- 状态：${insight.approvalStatus}`,
          `- 结论：${insight.statement}`,
          `- 可能意味着：${insight.possibleMeaning}`,
          `- 建议验证：${insight.suggestedValidation}`,
          `- Confidence：${insight.confidence}`,
          `- Evidence IDs：${insight.evidence
            .map((item) => `\`${item.metricId}\``)
            .join("、")}`,
          "",
        ])
      : ["- 尚无可导出的洞察。", ""]),
    "## 建议",
    "",
    ...(strategies.length > 0
      ? strategies.flatMap((strategy) => [
          `### ${strategy.title}`,
          "",
          `- 状态：${strategy.approvalStatus}`,
          `- 目标：${strategy.objective}`,
          `- 依据：${strategy.rationale}`,
          `- 来源洞察：${strategy.insightIds
            .map((id) => `\`${id}\``)
            .join("、")}`,
          `- Evidence IDs：${strategy.metricIds
            .map((id) => `\`${id}\``)
            .join("、")}`,
          ...strategy.actions.map((action) => `- 行动：${action}`),
          "",
        ])
      : ["- 尚无可导出的策略建议。", ""]),
    "## 30 天计划",
    "",
    ...(plan
      ? [
          `- Plan ID：\`${plan.planId}\``,
          `- 状态：${plan.status}`,
          `- 计划范围：${plan.startDate} 至 ${plan.endDate}`,
          "- 假设：",
          ...plan.assumptions.map((item) => `  - ${item}`),
          "",
          ...plan.fourWeekPlan.flatMap((week) => [
            `### 第 ${week.weekNumber} 周 · ${week.dateRange.start} 至 ${week.dateRange.end}`,
            "",
            `- 目标：${week.objective}`,
            `- 负责人：${week.ownerPlaceholder}`,
            `- CTA：${week.callToAction}`,
            `- KPI Evidence IDs：${week.kpiMetricIds
              .map((id) => `\`${id}\``)
              .join("、")}`,
            ...week.tasks.map(
              (task) =>
                `- 任务（${task.dueDate}）：${task.title} · ${task.status}`,
            ),
            "",
          ]),
          "### 内容日历",
          "",
          ...plan.contentCalendar.map(
            (item) =>
              `- ${item.date} ${item.scheduledTime} (${item.timeZone}) · ${item.topic} · ${item.channel} · ${item.contentFormat} · 审批 ${item.status} · 交接 ${item.workflowStatus}${
                item.isExperiment ? " · 实验" : ""
              } · Strategy \`${item.strategyId}\` · KPI ${item.measurementMetricIds
                .map((id) => `\`${id}\``)
                .join("、")}`,
          ),
          "",
          "### KPI 复盘计划",
          "",
          ...plan.kpiReviewPlan.map(
            (review) =>
              `- ${review.reviewDate} · ${review.action} · KPI ${review.metricIds
                .map((id) => `\`${id}\``)
                .join("、")} · ${review.comparisonRule}`,
          ),
          "",
          "### 下一次导入问题",
          "",
          ...plan.nextImportQuestions.map((question) => `- ${question}`),
          "",
        ]
      : ["- 尚未生成 30 天行动计划。", ""]),
    "## 限制说明",
    "",
    ...[...limitations].map((item) => `- ${item}`),
    "",
  ];

  return lines.join("\n");
}

export function generateContentCalendarCsv(plan: ActionPlan): string {
  const rows: unknown[][] = [
    [
      "日期",
      "时间",
      "时区",
      "渠道",
      "主题",
      "内容形式",
      "目标受众",
      "发布文案",
      "核心信息",
      "CTA",
      "链接",
      "媒体链接",
      "策略 ID",
      "衡量指标",
      "审批状态",
      "Buffer 工作流",
      "是否实验",
      "实验假设",
      "成功标准",
      "复盘日期",
      "负责人",
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
      item.isExperiment ? "是" : "否",
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
