import {
  CONTENT_METRIC_FIELDS,
  FOLLOWERS_METRIC_FIELDS,
  VISITORS_METRIC_FIELDS,
  type AnalysisInput,
  type AnalysisPeriod,
  type DataQualitySnapshot,
  type ModuleQualitySummary,
  type QualityIssue,
} from "@/domain/analysis";
import {
  LINKEDIN_MODULES,
  type LinkedInModule,
  type NormalizedLinkedInRecord,
  type StandardField,
} from "@/domain/linkedin";
import {
  dateKey,
  fieldValue,
  overlapPeriods,
  periodForRecords,
  referencesForRecords,
  sortedUniqueDates,
  utcDay,
} from "@/analysis/shared";

const HIGH_NULL_RATE = 0.3;
const MIN_SAMPLE_SIZE = 3;

const MODULE_FIELDS: Record<LinkedInModule, readonly StandardField[]> = {
  followers: FOLLOWERS_METRIC_FIELDS,
  visitors: VISITORS_METRIC_FIELDS,
  content: CONTENT_METRIC_FIELDS,
};

function issue(input: QualityIssue): QualityIssue {
  return input;
}

function countIssueSeverities(
  issues: readonly QualityIssue[],
  module: LinkedInModule,
): ModuleQualitySummary["issueCount"] {
  return {
    info: issues.filter(
      (item) => item.module === module && item.severity === "info",
    ).length,
    warning: issues.filter(
      (item) => item.module === module && item.severity === "warning",
    ).length,
    error: issues.filter(
      (item) => item.module === module && item.severity === "error",
    ).length,
  };
}

function nullRates(
  records: readonly NormalizedLinkedInRecord[],
  fields: readonly StandardField[],
): Partial<Record<StandardField, number>> {
  if (records.length === 0) {
    return {};
  }

  return Object.fromEntries(
    fields.map((field) => {
      const nullCount = records.filter(
        (record) => fieldValue(record, field) === null,
      ).length;
      return [field, nullCount / records.length];
    }),
  );
}

function checkMissingModules(input: AnalysisInput): QualityIssue[] {
  return LINKEDIN_MODULES.flatMap((module) =>
    input.records[module].length === 0
      ? [
          issue({
            code: "MISSING_MODULE",
            severity: "error",
            module,
            field: null,
            message: `Standardized ${module} records are missing.`,
            affectedRows: [],
            suggestedAction: `Upload and confirm ${module} data, then prepare a new snapshot.`,
            blocksAnalysis: true,
          }),
        ]
      : [],
  );
}

function checkOverlapAndGranularity(
  periods: Record<LinkedInModule, AnalysisPeriod | null>,
): QualityIssue[] {
  const available = LINKEDIN_MODULES.filter(
    (module) => periods[module] !== null,
  );
  if (available.length < 2) {
    return [];
  }

  const overlap = overlapPeriods(available.map((module) => periods[module]));
  const issues: QualityIssue[] = [];
  if (!overlap) {
    issues.push(
      issue({
        code: "TIME_RANGE_NO_OVERLAP",
        severity: "error",
        module: "cross-module",
        field: null,
        message: "Module date ranges do not overlap, so cross-module comparison is unavailable.",
        affectedRows: [],
        suggestedAction: "Export data with a common date range.",
        blocksAnalysis: true,
      }),
    );
  }

  const regularGranularities = new Set(
    available.flatMap((module) => {
      const granularity = periods[module]?.granularity;
      return granularity && granularity !== "irregular"
        ? [granularity]
        : [];
    }),
  );
  if (regularGranularities.size > 1) {
    issues.push(
      issue({
        code: "GRANULARITY_MISMATCH",
        severity: "warning",
        module: "cross-module",
        field: null,
        message: `Module granularity differs (${[...regularGranularities].join(" / ")}), preventing direct period comparison.`,
        affectedRows: [],
        suggestedAction: "Export each module at the same daily, weekly, or monthly granularity.",
        blocksAnalysis: true,
      }),
    );
  }
  return issues;
}

function expectedGapDays(granularity: AnalysisPeriod["granularity"]): {
  expected: number;
  tolerance: number;
} | null {
  if (granularity === "daily") {
    return { expected: 1, tolerance: 1 };
  }
  if (granularity === "weekly") {
    return { expected: 7, tolerance: 2 };
  }
  if (granularity === "monthly") {
    return { expected: 30, tolerance: 5 };
  }
  return null;
}

function checkDateGaps(
  module: LinkedInModule,
  records: readonly NormalizedLinkedInRecord[],
  period: AnalysisPeriod | null,
): QualityIssue[] {
  if (!period) {
    return [];
  }
  const expected = expectedGapDays(period.granularity);
  if (!expected) {
    return [];
  }
  const dates = sortedUniqueDates(records);
  const gaps = dates.slice(1).filter((date, index) => {
    const difference = utcDay(date) - utcDay(dates[index]);
    return difference > expected.expected + expected.tolerance;
  });
  if (gaps.length === 0) {
    return [];
  }

  return [
    issue({
      code: "DATE_GAP",
      severity: "warning",
      module,
      field: module === "content" ? "publishedAt" : "date",
      message: `${gaps.length} date gaps exceed the expected ${expected.expected} days.`,
      affectedRows: referencesForRecords(records, [
        module === "content" ? "publishedAt" : "date",
      ]),
      suggestedAction: "Check export ranges, filters, and missing periods.",
      blocksAnalysis: false,
    }),
  ];
}

function checkDuplicates(
  module: LinkedInModule,
  records: readonly NormalizedLinkedInRecord[],
): QualityIssue[] {
  const duplicates = records.filter((record) => record.isDuplicate);
  if (duplicates.length === 0) {
    return [];
  }
  return [
    issue({
      code: "DUPLICATE_RECORD",
      severity: "warning",
      module,
      field: null,
      message: `${duplicates.length} records are marked as duplicates and excluded from metrics.`,
      affectedRows: referencesForRecords(duplicates, []),
      suggestedAction: "Confirm duplicate sources or correct the field mapping.",
      blocksAnalysis: false,
    }),
  ];
}

function checkNullRates(
  module: LinkedInModule,
  records: readonly NormalizedLinkedInRecord[],
): QualityIssue[] {
  if (records.length === 0) {
    return [];
  }
  return MODULE_FIELDS[module].flatMap((field) => {
    const missing = records.filter(
      (record) => fieldValue(record, field) === null,
    );
    const rate = missing.length / records.length;
    if (rate < HIGH_NULL_RATE || missing.length === records.length) {
      return [];
    }
    return [
      issue({
        code: "NULL_RATE_HIGH",
        severity: "warning",
        module,
        field,
        message: `${field} is empty in ${(rate * 100).toFixed(0)}% of records.`,
        affectedRows: referencesForRecords(missing, [field]),
        suggestedAction: "Confirm the source field or narrow analyses that depend on it.",
        blocksAnalysis: false,
      }),
    ];
  });
}

function checkParserIssues(
  module: LinkedInModule,
  records: readonly NormalizedLinkedInRecord[],
): QualityIssue[] {
  const invalid = records.filter((record) =>
    record.issueReferences.some(
      (reference) => reference.code === "INVALID_NUMBER",
    ),
  );
  const negatives = records.filter((record) =>
    record.issueReferences.some(
      (reference) => reference.code === "NEGATIVE_VALUE",
    ),
  );
  const percentages = records.filter((record) =>
    record.issueReferences.some(
      (reference) => reference.code === "PERCENTAGE_OUT_OF_RANGE",
    ),
  );
  const issues: QualityIssue[] = [];

  if (invalid.length > 0) {
    issues.push(
      issue({
        code: "INVALID_NUMERIC_VALUE",
        severity: "error",
        module,
        field: null,
        message: `${invalid.length} records contain invalid numbers.`,
        affectedRows: referencesForRecords(invalid, []),
        suggestedAction: "Review source values and field mappings.",
        blocksAnalysis: true,
      }),
    );
  }
  if (negatives.length > 0) {
    issues.push(
      issue({
        code: "NEGATIVE_METRIC",
        severity: "warning",
        module,
        field: null,
        message: `${negatives.length} records contain negative metrics.`,
        affectedRows: referencesForRecords(negatives, []),
        suggestedAction: "Confirm whether negatives are corrections; otherwise fix the source data.",
        blocksAnalysis: false,
      }),
    );
  }
  if (percentages.length > 0) {
    issues.push(
      issue({
        code: "PERCENTAGE_OUT_OF_RANGE",
        severity: "warning",
        module,
        field: null,
        message: `${percentages.length} records contain percentages outside 0%–100%.`,
        affectedRows: referencesForRecords(percentages, []),
        suggestedAction: "Confirm percentage scaling and field meaning.",
        blocksAnalysis: false,
      }),
    );
  }
  return issues;
}

function checkFollowerDecrease(
  records: AnalysisInput["records"]["followers"],
): QualityIssue[] {
  const totals = records
    .filter(
      (record) =>
        !record.isDuplicate &&
        record.date !== null &&
        record.totalFollowers !== null,
    )
    .sort((left, right) =>
      (left.date as string).localeCompare(right.date as string),
    );
  const affected = totals.slice(1).filter(
    (record, index) =>
      (record.totalFollowers as number) <
      (totals[index].totalFollowers as number),
  );
  return affected.length === 0
    ? []
    : [
        issue({
          code: "FOLLOWER_TOTAL_DECREASE",
          severity: "warning",
          module: "followers",
          field: "totalFollowers",
          message: `${affected.length} periods have fewer total followers than the prior period.`,
          affectedRows: referencesForRecords(affected, ["totalFollowers"]),
          suggestedAction: "Check for unfollows, definition changes, or export anomalies.",
          blocksAnalysis: false,
        }),
      ];
}

function checkVisitorConsistency(
  records: AnalysisInput["records"]["visitors"],
): QualityIssue[] {
  const affected = records.filter(
    (record) =>
      record.pageViews !== null &&
      record.uniqueVisitors !== null &&
      record.uniqueVisitors > record.pageViews,
  );
  return affected.length === 0
    ? []
    : [
        issue({
          code: "UNIQUE_VISITORS_EXCEED_PAGE_VIEWS",
          severity: "error",
          module: "visitors",
          field: "uniqueVisitors",
          message: `${affected.length} records have more unique visitors than page views.`,
          affectedRows: referencesForRecords(affected, [
            "uniqueVisitors",
            "pageViews",
          ]),
          suggestedAction: "Check whether visitor mappings mix pages or definitions.",
          blocksAnalysis: true,
        }),
      ];
}

function checkContentEngagement(
  records: AnalysisInput["records"]["content"],
): QualityIssue[] {
  const affected = records.filter((record) => {
    if (record.impressions === null) {
      return false;
    }
    const components = [
      record.clicks,
      record.reactions,
      record.comments,
      record.reposts,
    ].filter((value): value is number => value !== null);
    return (
      components.some((value) => value > record.impressions!) ||
      components.reduce((sum, value) => sum + value, 0) >
        record.impressions * 2
    );
  });
  return affected.length === 0
    ? []
    : [
        issue({
          code: "CONTENT_ENGAGEMENT_COMPONENTS_INVALID",
          severity: "warning",
          module: "content",
          field: "engagementRate",
          message: `${affected.length} content records have engagement components inconsistent with impressions.`,
          affectedRows: referencesForRecords(affected, [
            "impressions",
            "clicks",
            "reactions",
            "comments",
            "reposts",
          ]),
          suggestedAction: "Confirm metrics use the same definitions and time window.",
          blocksAnalysis: false,
        }),
      ];
}

function checkSmallSamples(input: AnalysisInput): QualityIssue[] {
  return LINKEDIN_MODULES.flatMap((module) => {
    const records = input.records[module];
    return records.length > 0 && records.length < MIN_SAMPLE_SIZE
      ? [
          issue({
            code: "SAMPLE_TOO_SMALL",
            severity: "warning",
            module,
            field: null,
            message: `${module} has only ${records.length} records, so results are directional.`,
            affectedRows: referencesForRecords(records, []),
            suggestedAction: "Expand the export period or sample size.",
            blocksAnalysis: false,
          }),
        ]
      : [];
  });
}

function checkContentDates(
  content: AnalysisInput["records"]["content"],
  followerPeriod: AnalysisPeriod | null,
  visitorPeriod: AnalysisPeriod | null,
): QualityIssue[] {
  const comparisonPeriod = overlapPeriods([followerPeriod, visitorPeriod]);
  if (!comparisonPeriod) {
    return [];
  }
  const affected = content.filter(
    (record) =>
      record.publishedAt !== null &&
      (dateKey(record.publishedAt) < comparisonPeriod.start ||
        dateKey(record.publishedAt) > comparisonPeriod.end),
  );
  return affected.length === 0
    ? []
    : [
        issue({
          code: "CONTENT_DATE_OUTSIDE_RANGE",
          severity: "info",
          module: "content",
          field: "publishedAt",
          message: `${affected.length} content records fall outside the shared Followers and Visitors period.`,
          affectedRows: referencesForRecords(affected, ["publishedAt"]),
          suggestedAction: "Use only content in the shared period for cross-module analysis.",
          blocksAnalysis: false,
        }),
      ];
}

export function evaluateDataQuality(
  input: AnalysisInput,
): DataQualitySnapshot {
  const periods: Record<LinkedInModule, AnalysisPeriod | null> = {
    followers: periodForRecords(input.records.followers),
    visitors: periodForRecords(input.records.visitors),
    content: periodForRecords(input.records.content),
  };
  const issues: QualityIssue[] = [
    ...checkMissingModules(input),
    ...checkOverlapAndGranularity(periods),
    ...LINKEDIN_MODULES.flatMap((module) => [
      ...checkDateGaps(module, input.records[module], periods[module]),
      ...checkDuplicates(module, input.records[module]),
      ...checkNullRates(module, input.records[module]),
      ...checkParserIssues(module, input.records[module]),
    ]),
    ...checkFollowerDecrease(input.records.followers),
    ...checkVisitorConsistency(input.records.visitors),
    ...checkContentEngagement(input.records.content),
    ...checkSmallSamples(input),
    ...checkContentDates(
      input.records.content,
      periods.followers,
      periods.visitors,
    ),
  ].sort(
    (left, right) =>
      Number(right.blocksAnalysis) - Number(left.blocksAnalysis) ||
      left.severity.localeCompare(right.severity) ||
      left.code.localeCompare(right.code),
  );

  const moduleSummaries = Object.fromEntries(
    LINKEDIN_MODULES.map((module) => {
      const records = input.records[module];
      const summary: ModuleQualitySummary = {
        module,
        present: records.length > 0,
        totalRecords: records.length,
        duplicateRecords: records.filter((record) => record.isDuplicate)
          .length,
        nullRates: nullRates(records, MODULE_FIELDS[module]),
        period: periods[module],
        issueCount: countIssueSeverities(issues, module),
      };
      return [module, summary];
    }),
  ) as Record<LinkedInModule, ModuleQualitySummary>;

  return {
    issues,
    moduleSummaries,
    overlapPeriod: overlapPeriods(Object.values(periods)),
    hasBlockingIssues: issues.some((item) => item.blocksAnalysis),
    blockingIssueCount: issues.filter((item) => item.blocksAnalysis).length,
    warningCount: issues.filter((item) => item.severity === "warning").length,
    requiresWarningAcknowledgement: issues.some(
      (item) => item.severity === "warning" && !item.blocksAnalysis,
    ),
  };
}
