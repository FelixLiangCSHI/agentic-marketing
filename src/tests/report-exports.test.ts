import assert from "node:assert/strict";
import test from "node:test";

import { generateActionPlan } from "@/agents/action-plan-agent";
import {
  createReportExportArtifacts,
  generateContentCalendarCsv,
  generateStructuredAnalysisJson,
  type ReportExportInput,
} from "@/exports/report-exports";
import {
  approvedPlanningInput,
  PLANNING_NOW,
} from "@/tests/planning-fixtures";

function exportInput(): ReportExportInput {
  const planningInput = approvedPlanningInput();
  const plan = generateActionPlan(planningInput, PLANNING_NOW);
  return {
    projectId: "Synthetic APAC / Demo",
    snapshot: planningInput.snapshot,
    strategyBundle: {
      promptVersion: "evidence-strategy-v1.0",
      snapshotId: planningInput.snapshot.snapshotId,
      generatedAt: PLANNING_NOW.toISOString(),
      insights: planningInput.approvedInsights,
      strategies: planningInput.approvedStrategies,
    },
    plan,
  };
}

test("creates dated project filenames for all three export types", () => {
  const artifacts = createReportExportArtifacts(exportInput(), PLANNING_NOW);

  assert.equal(
    artifacts.markdown.fileName,
    "Synthetic-APAC-Demo-analysis-report-2026-07-28.md",
  );
  assert.equal(
    artifacts.calendarCsv.fileName,
    "Synthetic-APAC-Demo-content-calendar-2026-07-28.csv",
  );
  assert.equal(
    artifacts.structuredJson.fileName,
    "Synthetic-APAC-Demo-analysis-data-2026-07-28.json",
  );
});

test("Markdown report includes required sections and evidence identifiers", () => {
  const { markdown } = createReportExportArtifacts(
    exportInput(),
    PLANNING_NOW,
  );

  for (const heading of [
    "## Executive Summary",
    "## Key Findings",
    "## Business Implications",
    "## Recommendations",
    "## Confidence Level",
    "## Evidence",
    "## Observed Trends",
    "## 30-Day Action Plan",
    "## Limitations",
  ]) {
    assert.ok(markdown.content.includes(heading));
  }
  assert.ok(markdown.content.includes("followers.netGrowth"));
  assert.ok(markdown.content.includes("insight-audience-followers"));
  assert.ok(markdown.content.includes("相关性不代表内容导致增长"));
});

test("calendar CSV escapes formulas, quotes, commas, newlines, and Unicode", () => {
  const input = exportInput();
  assert.ok(input.plan);
  input.plan.contentCalendar[0] = {
    ...input.plan.contentCalendar[0],
    topic: '=HYPERLINK("https://invalid.example","危险,主题")',
    targetAudience: "+SUM(1,1)",
    coreMessage: "第一行\n第二行",
    callToAction: '@cmd "quoted"',
  };

  const csv = generateContentCalendarCsv(input.plan);

  assert.ok(csv.startsWith("\uFEFF"));
  assert.ok(csv.includes(`"'=HYPERLINK(""https://invalid.example""`));
  assert.ok(csv.includes(`"'+SUM(1,1)"`));
  assert.ok(csv.includes(`"'@cmd ""quoted"""`));
  assert.ok(csv.includes(`"第一行\n第二行"`));
  assert.ok(csv.includes("危险,主题"));
});

test("structured JSON omits source filenames, raw cells, secrets, and prompt text", () => {
  const input = exportInput();
  const json = generateStructuredAnalysisJson(input, PLANNING_NOW);
  const parsed = JSON.parse(json) as {
    privacy: Record<string, boolean>;
    snapshot: unknown;
  };

  assert.equal(parsed.privacy.containsRawFile, false);
  assert.equal(parsed.privacy.sourceFileNamesOmitted, true);
  assert.ok(json.includes('"sourceId"'));
  assert.ok(json.includes('"promptVersion"'));
  assert.ok(!json.includes('"fileName"'));
  assert.ok(!json.includes('"rawValues"'));
  assert.ok(!json.includes('"systemPrompt"'));
  assert.ok(!json.includes('"apiKey"'));
  assert.ok(!json.includes("synthetic_followers.csv"));
});

test("exports remain usable before a plan exists without inventing calendar rows", () => {
  const input = exportInput();
  input.plan = null;
  const artifacts = createReportExportArtifacts(input, PLANNING_NOW);

  assert.equal(artifacts.calendarCsv.content, "");
  assert.ok(
    artifacts.markdown.content.includes(
      "A 30-day action plan has not been generated.",
    ),
  );
  assert.equal(JSON.parse(artifacts.structuredJson.content).actionPlan, null);
});
