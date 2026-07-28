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
            message: `缺少 ${module} 标准化记录。`,
            affectedRows: [],
            suggestedAction: `上传并确认 ${module} 数据后重新生成 Snapshot。`,
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
        message: "模块时间范围没有共同重叠区间，不能进行跨模块比较。",
        affectedRows: [],
        suggestedAction: "重新导出具有共同时间范围的数据。",
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
        message: `模块粒度不一致：${[...regularGranularities].join(" / ")}，不能直接逐期比较。`,
        affectedRows: [],
        suggestedAction: "将各模块重新导出为相同的日、周或月粒度。",
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
      message: `发现 ${gaps.length} 个超过预期 ${expected.expected} 天的日期缺口。`,
      affectedRows: referencesForRecords(records, [
        module === "content" ? "publishedAt" : "date",
      ]),
      suggestedAction: "检查导出范围、筛选条件和缺失周期。",
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
      message: `${duplicates.length} 条记录被标记为重复；指标引擎会排除这些记录。`,
      affectedRows: referencesForRecords(duplicates, []),
      suggestedAction: "确认重复记录来源；如非重复，请回到字段映射修正。",
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
        message: `${field} 空值比例为 ${(rate * 100).toFixed(0)}%。`,
        affectedRows: referencesForRecords(missing, [field]),
        suggestedAction: "确认该字段是否存在于原始导出，或缩小依赖该字段的分析范围。",
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
        message: `${invalid.length} 条记录包含无效数字。`,
        affectedRows: referencesForRecords(invalid, []),
        suggestedAction: "回到识别结果检查原始值和字段映射。",
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
        message: `${negatives.length} 条记录包含负数指标。`,
        affectedRows: referencesForRecords(negatives, []),
        suggestedAction: "确认负数是否代表修正值；否则修复源数据。",
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
        message: `${percentages.length} 条记录包含超出 0%–100% 的百分比。`,
        affectedRows: referencesForRecords(percentages, []),
        suggestedAction: "确认百分比缩放和字段含义。",
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
          message: `${affected.length} 个周期的关注者总数低于前一期。`,
          affectedRows: referencesForRecords(affected, ["totalFollowers"]),
          suggestedAction: "确认是否为取消关注、口径变更或导出异常。",
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
          message: `${affected.length} 条记录的独立访客大于页面浏览量。`,
          affectedRows: referencesForRecords(affected, [
            "uniqueVisitors",
            "pageViews",
          ]),
          suggestedAction: "检查 Visitors 字段映射是否混用了不同页面或口径。",
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
          message: `${affected.length} 条内容的互动组成项与展示量关系异常。`,
          affectedRows: referencesForRecords(affected, [
            "impressions",
            "clicks",
            "reactions",
            "comments",
            "reposts",
          ]),
          suggestedAction: "确认指标是否来自相同口径和时间窗口。",
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
            message: `${module} 仅有 ${records.length} 条记录，结果仅适合作方向观察。`,
            affectedRows: referencesForRecords(records, []),
            suggestedAction: "扩大导出时间范围或增加样本量。",
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
          message: `${affected.length} 条内容发布时间不在 Followers 与 Visitors 共同范围内。`,
          affectedRows: referencesForRecords(affected, ["publishedAt"]),
          suggestedAction: "跨模块分析时只使用共同时间范围内的内容。",
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
