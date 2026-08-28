import {
  calculateContentMetrics,
  calculateCrossModuleMetrics,
  calculateFollowersMetrics,
  calculateVisitorsMetrics,
} from "@/analysis/metrics-engine";
import { evaluateDataQuality } from "@/analysis/quality-engine";
import { overlapPeriods, periodForRecords } from "@/analysis/shared";
import type {
  AnalysisInput,
  AnalysisSnapshot,
} from "@/domain/analysis";
import {
  LINKEDIN_MODULES,
  type FileParseResult,
  type LinkedInModule,
} from "@/domain/linkedin";
import { stableId } from "@/utils/stable-id";

function snapshotIdForInput(input: AnalysisInput): string {
  const signature = LINKEDIN_MODULES.flatMap((module) =>
    input.records[module].map((record) => {
      const normalizedRecord = Object.fromEntries(
        Object.entries(record)
          .filter(
            ([key]) => key !== "rawValues" && key !== "issueReferences",
          )
          .sort(([left], [right]) => left.localeCompare(right)),
      );
      return JSON.stringify(normalizedRecord);
    }),
  )
    .sort()
    .join("\n");
  return stableId("snapshot-1", signature);
}

export function analysisInputFromParseResults(
  results: Partial<Record<LinkedInModule, FileParseResult>>,
  inputMode: AnalysisInput["inputMode"],
): AnalysisInput {
  // 受控事实（ADR-005）：只吸收通过 sheet 级门控的记录，
  // 避免无效 sheet 的数据混入确定性指标。
  const allRecords = LINKEDIN_MODULES.flatMap(
    (module) =>
      results[module]?.workbook.sheets
        .filter((sheet) => sheet.canProceed)
        .flatMap((sheet) => sheet.records) ?? [],
  );
  return {
    inputMode,
    records: {
      followers: allRecords.filter(
        (record) => record.module === "followers",
      ),
      visitors: allRecords.filter(
        (record) => record.module === "visitors",
      ),
      content: allRecords.filter((record) => record.module === "content"),
    },
  };
}

export function generateAnalysisSnapshot(
  input: AnalysisInput,
): AnalysisSnapshot {
  const quality = evaluateDataQuality(input);
  const periods = [
    periodForRecords(input.records.followers),
    periodForRecords(input.records.visitors),
    periodForRecords(input.records.content),
  ];

  return {
    snapshotId: snapshotIdForInput(input),
    snapshotVersion: "1.0",
    generatedAt: new Date().toISOString(),
    inputMode: input.inputMode,
    quality,
    metrics: {
      followers: calculateFollowersMetrics(input.records.followers),
      visitors: calculateVisitorsMetrics(input.records.visitors),
      content: calculateContentMetrics(input.records.content),
      crossModule: calculateCrossModuleMetrics(input),
    },
    analysisPeriod: overlapPeriods(periods),
    sourceModules: LINKEDIN_MODULES.filter(
      (module) => input.records[module].length > 0,
    ),
    canEnterInsights: !quality.hasBlockingIssues,
    records: {
      followers: input.records.followers.length,
      visitors: input.records.visitors.length,
      content: input.records.content.length,
    },
  };
}
