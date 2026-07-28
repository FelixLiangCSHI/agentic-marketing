import {
  createMetric,
  dateKey,
  formatMetricValue,
  inPeriod,
  median,
  numberField,
  overlapPeriods,
  periodForRecords,
  referencesForRecords,
  reliabilityForCoverage,
  safeDivide,
  sumAvailable,
  unavailableMetric,
  utcDay,
} from "@/analysis/shared";
import type {
  AnalysisInput,
  AnalysisPeriod,
  ContentMetrics,
  CrossModuleMetrics,
  FollowersMetrics,
  GroupMetric,
  Metric,
  MetricReliability,
  MetricSeries,
  RankedItem,
  RankedMetric,
  VisitorsMetrics,
} from "@/domain/analysis";
import type {
  ContentRecord,
  FollowersRecord,
  LinkedInModule,
  NormalizedLinkedInRecord,
  StandardField,
  VisitorsRecord,
} from "@/domain/linkedin";

type NumericField =
  | "totalFollowers"
  | "newFollowers"
  | "organicFollowers"
  | "sponsoredFollowers"
  | "demographicCount"
  | "demographicPercentage"
  | "pageViews"
  | "uniqueVisitors"
  | "customButtonClicks"
  | "impressions"
  | "uniqueImpressions"
  | "clicks"
  | "reactions"
  | "comments"
  | "reposts"
  | "engagementRate"
  | "clickThroughRate";

const MIN_GROUP_SAMPLE = 3;

type ContentClickThroughPair = ContentRecord & {
  impressions: number;
  clicks: number;
};

type ContentEngagementPair = ContentClickThroughPair & {
  reactions: number;
  comments: number;
  reposts: number;
};

function isContentClickThroughPair(
  record: ContentRecord,
): record is ContentClickThroughPair {
  return record.impressions !== null && record.clicks !== null;
}

function isContentEngagementPair(
  record: ContentRecord,
): record is ContentEngagementPair {
  return (
    isContentClickThroughPair(record) &&
    record.reactions !== null &&
    record.comments !== null &&
    record.reposts !== null
  );
}

function contentEngagements(record: ContentEngagementPair): number {
  return record.clicks + record.reactions + record.comments + record.reposts;
}

function hasComparablePeriodGap(
  leftDate: string,
  rightDate: string,
  granularity: AnalysisPeriod["granularity"],
): boolean {
  const difference = utcDay(rightDate) - utcDay(leftDate);
  if (granularity === "daily") {
    return difference >= 1 && difference <= 2;
  }
  if (granularity === "weekly") {
    return difference >= 6 && difference <= 8;
  }
  if (granularity === "monthly") {
    return difference >= 27 && difference <= 32;
  }
  return false;
}

function withoutDuplicates<T extends NormalizedLinkedInRecord>(
  records: readonly T[],
): T[] {
  return records.filter((record) => !record.isDuplicate);
}

function temporalFollowers(records: readonly FollowersRecord[]): FollowersRecord[] {
  return withoutDuplicates(records)
    .filter((record) => record.date !== null)
    .sort((left, right) =>
      (left.date as string).localeCompare(right.date as string),
    );
}

function temporalVisitors(records: readonly VisitorsRecord[]): VisitorsRecord[] {
  return withoutDuplicates(records)
    .filter((record) => record.date !== null)
    .sort((left, right) =>
      (left.date as string).localeCompare(right.date as string),
    );
}

function selectedContentRecords(records: readonly ContentRecord[]): {
  records: ContentRecord[];
  reason: string;
} {
  const unique = withoutDuplicates(records);
  const itemRecords = unique.filter(
    (record) => record.contentId !== null || record.title !== null,
  );
  return itemRecords.length > 0
    ? {
        records: itemRecords,
        reason: "优先使用具有内容标识的逐帖记录，未混入日级汇总。",
      }
    : {
        records: unique,
        reason: "没有逐帖记录，使用唯一可用的时间序列记录。",
      };
}

function metricFromValues(input: {
  metricId: string;
  label: string;
  values: readonly (number | null)[];
  value: number | null;
  unit: Metric["unit"];
  formula: string;
  period: AnalysisPeriod | null;
  records: readonly NormalizedLinkedInRecord[];
  fields: StandardField[];
  sourceModules: LinkedInModule[];
  minReliableSample?: number;
  extraReasons?: string[];
  caveat?: string;
}): Metric {
  const coverage = reliabilityForCoverage(
    input.values.filter((value) => value !== null).length,
    input.values.length,
    {
      minReliableSample: input.minReliableSample,
      extraReasons: input.extraReasons,
      blocked: input.value === null,
    },
  );
  return createMetric({
    metricId: input.metricId,
    label: input.label,
    value: input.value,
    unit: input.unit,
    formula: input.formula,
    period: input.period,
    sourceModules: input.sourceModules,
    sourceReferences:
      input.value === null
        ? []
        : referencesForRecords(input.records, input.fields),
    reliability: coverage.reliability,
    reliabilityReasons: coverage.reasons,
    caveat: input.caveat,
  });
}

function sumMetric(input: {
  metricId: string;
  label: string;
  records: readonly NormalizedLinkedInRecord[];
  field: NumericField;
  sourceModule: LinkedInModule;
  period: AnalysisPeriod | null;
  extraReasons?: string[];
}): Metric {
  const values = input.records.map((record) =>
    numberField(record, input.field),
  );
  return metricFromValues({
    metricId: input.metricId,
    label: input.label,
    values,
    value: sumAvailable(values),
    unit: "count",
    formula: `SUM(${input.field})，排除已标记重复记录；null 不参与，0 保留`,
    period: input.period,
    records: input.records,
    fields: [input.field],
    sourceModules: [input.sourceModule],
    extraReasons: input.extraReasons,
  });
}

function unavailableSeries(input: {
  seriesId: string;
  label: string;
  unit: MetricSeries["unit"];
  sourceModules: LinkedInModule[];
  reasons: string[];
}): MetricSeries {
  return {
    seriesId: input.seriesId,
    label: input.label,
    unit: input.unit,
    period: null,
    points: [],
    reliability: "unavailable",
    reliabilityReasons: input.reasons,
    sourceModules: input.sourceModules,
  };
}

function buildSeries<T extends FollowersRecord | VisitorsRecord>(
  records: readonly T[],
  field: NumericField,
  seriesId: string,
  label: string,
  module: "followers" | "visitors",
): MetricSeries {
  const available = records.filter(
    (record) => record.date !== null && numberField(record, field) !== null,
  );
  if (available.length === 0) {
    return unavailableSeries({
      seriesId,
      label,
      unit: "count",
      sourceModules: [module],
      reasons: [`缺少 ${field} 的带日期有效值。`],
    });
  }
  const period = periodForRecords(available);
  const reliability = reliabilityForCoverage(
    available.length,
    records.length,
  );
  return {
    seriesId,
    label,
    unit: "count",
    period,
    points: available.map((record) => {
      const value = numberField(record, field) as number;
      return {
        period: record.date as string,
        value,
        formattedValue: formatMetricValue(value, "count"),
        sourceReferences: referencesForRecords([record], [field]),
      };
    }),
    reliability: reliability.reliability,
    reliabilityReasons: reliability.reasons,
    sourceModules: [module],
  };
}

function demographicTopN(
  module: "followers" | "visitors",
  records: readonly (FollowersRecord | VisitorsRecord)[],
  period: AnalysisPeriod | null,
  topN = 5,
): RankedMetric[] {
  const demographic = withoutDuplicates(records).filter(
    (record) =>
      record.demographicDimension !== null &&
      record.demographicValue !== null &&
      (record.demographicCount !== null ||
        record.demographicPercentage !== null),
  );
  const dimensions = [
    ...new Set(
      demographic.map((record) => record.demographicDimension as string),
    ),
  ].sort();

  return dimensions.map((dimension) => {
    const dimensionRecords = demographic.filter(
      (record) => record.demographicDimension === dimension,
    );
    const groups = new Map<
      string,
      { value: number; records: (FollowersRecord | VisitorsRecord)[] }
    >();
    for (const record of dimensionRecords) {
      const key = record.demographicValue as string;
      const metricValue =
        record.demographicCount ?? record.demographicPercentage;
      if (metricValue === null) {
        continue;
      }
      const group = groups.get(key) ?? { value: 0, records: [] };
      group.value += metricValue;
      group.records.push(record);
      groups.set(key, group);
    }
    const sorted = [...groups.entries()].sort(
      ([leftKey, left], [rightKey, right]) =>
        right.value - left.value || leftKey.localeCompare(rightKey),
    );
    const items = rankItems(
      sorted.slice(0, topN).map(([key, group]) => ({
        key,
        label: key,
        value: group.value,
        records: group.records,
      })),
      dimensionRecords.some((record) => record.demographicCount !== null)
        ? "count"
        : "percentage",
      ["demographicValue", "demographicCount", "demographicPercentage"],
    );
    return {
      metricId: `${module}.demographic.${dimension}`,
      label: `${dimension} Top ${topN}`,
      formula:
        "按 demographicDimension / demographicValue 分组，对可用 count 求和；无 count 时使用 percentage",
      period,
      sourceModules: [module],
      items,
      reliability:
        items.length === 0
          ? "unavailable"
          : dimensionRecords.length < MIN_GROUP_SAMPLE
            ? "directional"
            : "reliable",
      reliabilityReasons:
        dimensionRecords.length < MIN_GROUP_SAMPLE
          ? [`${dimension} 仅 ${dimensionRecords.length} 条画像记录。`]
          : ["画像分组样本量满足当前规则。"],
    };
  });
}

function rankItems(
  entries: readonly {
    key: string;
    label: string;
    value: number;
    records: readonly NormalizedLinkedInRecord[];
  }[],
  unit: Metric["unit"],
  fields: StandardField[],
): RankedItem[] {
  const sorted = [...entries].sort(
    (left, right) =>
      right.value - left.value || left.key.localeCompare(right.key),
  );
  let previousValue: number | null = null;
  let previousRank = 0;
  return sorted.map((entry, index) => {
    const tied = previousValue === entry.value;
    const rank = tied ? previousRank : index + 1;
    previousValue = entry.value;
    previousRank = rank;
    return {
      rank,
      tied,
      key: entry.key,
      label: entry.label,
      value: entry.value,
      formattedValue: formatMetricValue(entry.value, unit),
      reliability:
        entry.records.length < MIN_GROUP_SAMPLE
          ? "directional"
          : "reliable",
      reliabilityReasons:
        entry.records.length < MIN_GROUP_SAMPLE
          ? [`分组样本仅 ${entry.records.length} 条。`]
          : ["分组样本量满足当前规则。"],
      sourceReferences: referencesForRecords(entry.records, fields),
    };
  });
}

export function calculateFollowersMetrics(
  records: readonly FollowersRecord[],
): FollowersMetrics {
  const temporal = temporalFollowers(records);
  const period = periodForRecords(temporal);
  const totals = temporal.filter(
    (record) => record.totalFollowers !== null,
  );
  const first = totals[0];
  const last = totals.at(-1);
  const start = first?.totalFollowers ?? null;
  const end = last?.totalFollowers ?? null;
  const net = start !== null && end !== null ? end - start : null;
  const growthRate = safeDivide(net, start);
  const totalReasons =
    totals.length < 2
      ? ["需要至少两个带 totalFollowers 的可比较周期。"]
      : [];
  const startMetric = metricFromValues({
    metricId: "followers.start",
    label: "起始关注者数",
    values: temporal.map((record) => record.totalFollowers),
    value: start,
    unit: "count",
    formula: "按日期升序后的首个非 null totalFollowers",
    period,
    records: first ? [first] : [],
    fields: ["date", "totalFollowers"],
    sourceModules: ["followers"],
    minReliableSample: 1,
    extraReasons: totalReasons,
  });
  const endMetric = metricFromValues({
    metricId: "followers.end",
    label: "结束关注者数",
    values: temporal.map((record) => record.totalFollowers),
    value: end,
    unit: "count",
    formula: "按日期升序后的最后一个非 null totalFollowers",
    period,
    records: last ? [last] : [],
    fields: ["date", "totalFollowers"],
    sourceModules: ["followers"],
    minReliableSample: 1,
    extraReasons: totalReasons,
  });
  const netMetric = metricFromValues({
    metricId: "followers.netGrowth",
    label: "净增长",
    values: totals.map((record) => record.totalFollowers),
    value: net,
    unit: "count",
    formula: "结束 totalFollowers − 起始 totalFollowers",
    period,
    records: first && last ? [first, last] : [],
    fields: ["date", "totalFollowers"],
    sourceModules: ["followers"],
    minReliableSample: 2,
    extraReasons: totalReasons,
  });
  const growthMetric = metricFromValues({
    metricId: "followers.growthRate",
    label: "关注者增长率",
    values: totals.map((record) => record.totalFollowers),
    value: growthRate,
    unit: "percentage",
    formula:
      "(结束 totalFollowers − 起始 totalFollowers) ÷ 起始 totalFollowers；起始为 0 时 unavailable",
    period,
    records: first && last ? [first, last] : [],
    fields: ["date", "totalFollowers"],
    sourceModules: ["followers"],
    minReliableSample: 2,
    extraReasons:
      start === 0
        ? ["起始关注者为 0，不能计算增长率。"]
        : totalReasons,
  });
  const mixRecords = temporal.filter(
    (record) =>
      record.organicFollowers !== null &&
      record.sponsoredFollowers !== null,
  );
  const organicValues = mixRecords.map((record) => record.organicFollowers);
  const sponsoredValues = mixRecords.map((record) => record.sponsoredFollowers);
  const organic = sumAvailable(organicValues);
  const sponsored = sumAvailable(sponsoredValues);
  const mixTotal =
    organic !== null && sponsored !== null ? organic + sponsored : null;
  const mixPeriod = periodForRecords(mixRecords);
  const mixCoverageReasons =
    mixRecords.length < temporal.length
      ? [
          `仅 ${mixRecords.length}/${temporal.length} 个周期同时具备 Organic 与 Sponsored。`,
        ]
      : [];

  return {
    startFollowers: startMetric,
    endFollowers: endMetric,
    netGrowth: netMetric,
    growthRate: growthMetric,
    newFollowersTotal: sumMetric({
      metricId: "followers.newTotal",
      label: "新增关注者总量",
      records: temporal,
      field: "newFollowers",
      sourceModule: "followers",
      period,
    }),
    organicShare: metricFromValues({
      metricId: "followers.organicShare",
      label: "Organic 占比",
      values: temporal.map((record) =>
        record.organicFollowers !== null &&
        record.sponsoredFollowers !== null
          ? record.organicFollowers
          : null,
      ),
      value: safeDivide(organic, mixTotal),
      unit: "percentage",
      formula:
        "在 Organic 与 Sponsored 均非 null 的相同周期中，SUM(organicFollowers) ÷ (SUM(organicFollowers) + SUM(sponsoredFollowers))",
      period: mixPeriod,
      records: mixRecords,
      fields: ["organicFollowers", "sponsoredFollowers"],
      sourceModules: ["followers"],
      extraReasons: [
        ...mixCoverageReasons,
        ...(mixTotal === 0 ? ["Organic 与 Sponsored 合计为 0。"] : []),
      ],
    }),
    sponsoredShare: metricFromValues({
      metricId: "followers.sponsoredShare",
      label: "Sponsored 占比",
      values: temporal.map((record) =>
        record.organicFollowers !== null &&
        record.sponsoredFollowers !== null
          ? record.sponsoredFollowers
          : null,
      ),
      value: safeDivide(sponsored, mixTotal),
      unit: "percentage",
      formula:
        "在 Organic 与 Sponsored 均非 null 的相同周期中，SUM(sponsoredFollowers) ÷ (SUM(organicFollowers) + SUM(sponsoredFollowers))",
      period: mixPeriod,
      records: mixRecords,
      fields: ["organicFollowers", "sponsoredFollowers"],
      sourceModules: ["followers"],
      extraReasons: [
        ...mixCoverageReasons,
        ...(mixTotal === 0 ? ["Organic 与 Sponsored 合计为 0。"] : []),
      ],
    }),
    newFollowersTrend: buildSeries(
      temporal,
      "newFollowers",
      "followers.newTrend",
      "每期新增关注者",
      "followers",
    ),
    demographicTopN: demographicTopN(
      "followers",
      records,
      periodForRecords(records),
    ),
    demographicTrend: unavailableMetric({
      metricId: "followers.demographicTrend",
      label: "画像变化趋势",
      unit: "text",
      formula:
        "同一 demographicDimension / demographicValue 在至少两个日期快照间比较",
      sourceModules: ["followers"],
      reliabilityReasons: [
        "当前标准模型中的画像记录没有可比较的日期快照。",
      ],
    }),
  };
}

export function calculateVisitorsMetrics(
  records: readonly VisitorsRecord[],
): VisitorsMetrics {
  const temporal = temporalVisitors(records);
  const period = periodForRecords(temporal);
  const completePairs = temporal.filter(
    (record) =>
      record.pageViews !== null && record.uniqueVisitors !== null,
  );
  const pairedPageViewsTotal = sumAvailable(
    completePairs.map((record) => record.pageViews),
  );
  const pairedUniqueVisitorsTotal = sumAvailable(
    completePairs.map((record) => record.uniqueVisitors),
  );
  const pairPeriod = periodForRecords(completePairs);
  const pairCoverageReasons =
    completePairs.length < temporal.length
      ? [
          `仅 ${completePairs.length}/${temporal.length} 个周期同时具备 Page Views 与 Unique Visitors。`,
        ]
      : [];
  const comparable = temporal.filter(
    (record) => record.pageViews !== null,
  );
  const lastTwo = comparable.slice(-2);
  const periodChangePeriod = periodForRecords(lastTwo);
  const periodChangeComparable =
    lastTwo.length === 2 &&
    period !== null &&
    period.granularity !== "irregular" &&
    hasComparablePeriodGap(
      lastTwo[0].date as string,
      lastTwo[1].date as string,
      period.granularity,
    );
  const periodChange =
    periodChangeComparable
      ? safeDivide(
          (lastTwo[1].pageViews as number) -
            (lastTwo[0].pageViews as number),
          lastTwo[0].pageViews,
        )
      : null;

  return {
    pageViewsTotal: sumMetric({
      metricId: "visitors.pageViewsTotal",
      label: "Page Views 总量",
      records: temporal,
      field: "pageViews",
      sourceModule: "visitors",
      period,
    }),
    uniqueVisitorsTotal: sumMetric({
      metricId: "visitors.uniqueVisitorsTotal",
      label: "Unique Visitors 总量",
      records: temporal,
      field: "uniqueVisitors",
      sourceModule: "visitors",
      period,
    }),
    pageViewsPerVisitor: metricFromValues({
      metricId: "visitors.pageViewsPerVisitor",
      label: "平均 Page Views per Visitor",
      values: temporal.map((record) =>
        record.pageViews !== null && record.uniqueVisitors !== null
          ? record.uniqueVisitors
          : null,
      ),
      value: safeDivide(pairedPageViewsTotal, pairedUniqueVisitorsTotal),
      unit: "ratio",
      formula:
        "在 pageViews 与 uniqueVisitors 均非 null 的相同记录中，SUM(pageViews) ÷ SUM(uniqueVisitors)",
      period: pairPeriod,
      records: completePairs,
      fields: ["pageViews", "uniqueVisitors"],
      sourceModules: ["visitors"],
      extraReasons: [
        ...pairCoverageReasons,
        ...(pairedUniqueVisitorsTotal === 0
          ? ["成对完整记录的 Unique Visitors 合计为 0。"]
          : []),
      ],
    }),
    customButtonClicksTotal: sumMetric({
      metricId: "visitors.customButtonClicks",
      label: "Custom Button Clicks",
      records: temporal,
      field: "customButtonClicks",
      sourceModule: "visitors",
      period,
    }),
    pageViewsTrend: buildSeries(
      temporal,
      "pageViews",
      "visitors.pageViewsTrend",
      "Page Views 趋势",
      "visitors",
    ),
    uniqueVisitorsTrend: buildSeries(
      temporal,
      "uniqueVisitors",
      "visitors.uniqueVisitorsTrend",
      "Unique Visitors 趋势",
      "visitors",
    ),
    periodOverPeriodChange: metricFromValues({
      metricId: "visitors.periodChange",
      label: "Page Views 环比变化",
      values: lastTwo.map((record) => record.pageViews),
      value: periodChange,
      unit: "percentage",
      formula: "(最新一期 pageViews − 前一期 pageViews) ÷ 前一期 pageViews",
      period: periodChangePeriod,
      records: lastTwo,
      fields: ["date", "pageViews"],
      sourceModules: ["visitors"],
      minReliableSample: 2,
      extraReasons:
        lastTwo.length < 2
          ? ["至少需要两个可比较周期。"]
          : !periodChangeComparable
            ? ["最新两个有效周期的间隔不符合日、周或月可比粒度。"]
          : lastTwo[0].pageViews === 0
            ? ["前一期 Page Views 为 0。"]
            : [],
    }),
    demographicTopN: demographicTopN(
      "visitors",
      records,
      periodForRecords(records),
    ),
  };
}

function contentPerformance(record: ContentRecord): number | null {
  if (isContentEngagementPair(record) && record.impressions > 0) {
    return contentEngagements(record) / record.impressions;
  }
  return record.engagementRate;
}

function contentLabel(record: ContentRecord): string {
  return (
    record.title ??
    record.contentId ??
    `${record.source.sheetName} 第 ${record.source.rowNumber} 行`
  );
}

function contentGroupMetrics(
  records: readonly ContentRecord[],
  groupBy: (record: ContentRecord) => string | null,
  prefix: string,
  period: AnalysisPeriod | null,
): GroupMetric[] {
  const groups = new Map<string, ContentRecord[]>();
  for (const record of records) {
    const key = groupBy(record);
    if (!key) {
      continue;
    }
    const group = groups.get(key) ?? [];
    group.push(record);
    groups.set(key, group);
  }

  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, group]) => {
      const impressions = group.map((record) => record.impressions);
      const clickThroughPairs = group.filter(isContentClickThroughPair);
      const pairedClicks = sumAvailable(
        clickThroughPairs.map((record) => record.clicks),
      );
      const pairedImpressions = sumAvailable(
        clickThroughPairs.map((record) => record.impressions),
      );
      const engagementValues = group
        .map(contentPerformance)
        .filter((value): value is number => value !== null);
      const groupReliability: MetricReliability =
        group.length < MIN_GROUP_SAMPLE ? "directional" : "reliable";
      const reasons =
        group.length < MIN_GROUP_SAMPLE
          ? [`分组仅 ${group.length} 条内容，低于 ${MIN_GROUP_SAMPLE} 条规则。`]
          : ["分组样本量满足当前规则。"];

      return {
        key,
        label: key,
        sampleSize: group.length,
        reliability: groupReliability,
        reliabilityReasons: reasons,
        metrics: [
          metricFromValues({
            metricId: `${prefix}.${key}.impressions`,
            label: "Impressions",
            values: impressions,
            value: sumAvailable(impressions),
            unit: "count",
            formula: "组内 SUM(impressions)",
            period,
            records: group,
            fields: ["impressions"],
            sourceModules: ["content"],
            minReliableSample: MIN_GROUP_SAMPLE,
            extraReasons: reasons,
          }),
          metricFromValues({
            metricId: `${prefix}.${key}.ctr`,
            label: "CTR",
            values: group.map((record) =>
              isContentClickThroughPair(record) ? record.clicks : null,
            ),
            value: safeDivide(pairedClicks, pairedImpressions),
            unit: "percentage",
            formula:
              "组内仅在 clicks 与 impressions 均非 null 的相同记录中，SUM(clicks) ÷ SUM(impressions)",
            period: periodForRecords(clickThroughPairs),
            records: clickThroughPairs,
            fields: ["clicks", "impressions"],
            sourceModules: ["content"],
            minReliableSample: MIN_GROUP_SAMPLE,
            extraReasons: [
              ...reasons,
              ...(clickThroughPairs.length < group.length
                ? [
                    `仅 ${clickThroughPairs.length}/${group.length} 条组内内容同时具备 clicks 与 impressions。`,
                  ]
                : []),
              ...(pairedImpressions === 0
                ? ["成对完整记录的 Impressions 合计为 0。"]
                : []),
            ],
          }),
          metricFromValues({
            metricId: `${prefix}.${key}.medianEngagement`,
            label: "中位互动率",
            values: group.map(contentPerformance),
            value: median(engagementValues),
            unit: "percentage",
            formula: "MEDIAN(逐条内容互动率)",
            period,
            records: group,
            fields: [
              "impressions",
              "clicks",
              "reactions",
              "comments",
              "reposts",
              "engagementRate",
            ],
            sourceModules: ["content"],
            minReliableSample: MIN_GROUP_SAMPLE,
            extraReasons: reasons,
          }),
        ],
      };
    });
}

export function calculateContentMetrics(
  inputRecords: readonly ContentRecord[],
): ContentMetrics {
  const selection = selectedContentRecords(inputRecords);
  const records = selection.records;
  const period = periodForRecords(records);
  const clickThroughPairs = records.filter(isContentClickThroughPair);
  const pairedClicks = sumAvailable(
    clickThroughPairs.map((record) => record.clicks),
  );
  const pairedClickImpressions = sumAvailable(
    clickThroughPairs.map((record) => record.impressions),
  );
  const engagementPairs = records.filter(isContentEngagementPair);
  const engagementValues = records
    .map(contentPerformance)
    .filter((value): value is number => value !== null);
  const totalEngagements = sumAvailable(
    engagementPairs.map(contentEngagements),
  );
  const engagementImpressions = sumAvailable(
    engagementPairs.map((record) => record.impressions),
  );
  const engagementCoverageReasons =
    engagementPairs.length < records.length
      ? [
          `仅 ${engagementPairs.length}/${records.length} 条内容同时具备 impressions、clicks、reactions、comments 与 reposts。`,
        ]
      : [];
  const clickThroughCoverageReasons =
    clickThroughPairs.length < records.length
      ? [
          `仅 ${clickThroughPairs.length}/${records.length} 条内容同时具备 clicks 与 impressions。`,
        ]
      : [];
  const rankingEntries = records.flatMap((record) => {
    const value = contentPerformance(record);
    return value === null
      ? []
      : [
          {
            key: `${record.source.fileName}:${record.source.sheetName}:${record.source.rowNumber}`,
            label: contentLabel(record),
            value,
            records: [record],
          },
        ];
  });
  const rankingItems = rankItems(
    rankingEntries,
    "percentage",
    [
      "impressions",
      "clicks",
      "reactions",
      "comments",
      "reposts",
      "engagementRate",
    ],
  );
  const rankingReliability = reliabilityForCoverage(
    rankingItems.length,
    records.length,
    { extraReasons: [selection.reason] },
  );
  const weekdays = [
    "星期日",
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
  ];

  return {
    publishedCount: metricFromValues({
      metricId: "content.publishedCount",
      label: "发布内容数量",
      values: records.map((record) =>
        record.publishedAt === null ? null : 1,
      ),
      value:
        records.filter((record) => record.publishedAt !== null).length || null,
      unit: "count",
      formula: "COUNT(具有 publishedAt 的唯一逐帖记录)",
      period,
      records,
      fields: ["publishedAt", "contentId", "title"],
      sourceModules: ["content"],
      extraReasons: [selection.reason],
    }),
    impressionsTotal: sumMetric({
      metricId: "content.impressions",
      label: "Impressions 总量",
      records,
      field: "impressions",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    clicksTotal: sumMetric({
      metricId: "content.clicks",
      label: "Clicks 总量",
      records,
      field: "clicks",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    reactionsTotal: sumMetric({
      metricId: "content.reactions",
      label: "Reactions 总量",
      records,
      field: "reactions",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    commentsTotal: sumMetric({
      metricId: "content.comments",
      label: "Comments 总量",
      records,
      field: "comments",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    repostsTotal: sumMetric({
      metricId: "content.reposts",
      label: "Reposts 总量",
      records,
      field: "reposts",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    clickThroughRate: metricFromValues({
      metricId: "content.ctr",
      label: "Content CTR",
      values: records.map((record) =>
        record.clicks !== null && record.impressions !== null
          ? record.clicks
          : null,
      ),
      value: safeDivide(pairedClicks, pairedClickImpressions),
      unit: "percentage",
      formula:
        "在 clicks 与 impressions 均非 null 的相同记录中，SUM(clicks) ÷ SUM(impressions)",
      period: periodForRecords(clickThroughPairs),
      records: clickThroughPairs,
      fields: ["clicks", "impressions"],
      sourceModules: ["content"],
      extraReasons: [
        selection.reason,
        ...clickThroughCoverageReasons,
        ...(pairedClickImpressions === 0
          ? ["成对完整记录的 Impressions 合计为 0。"]
          : []),
      ],
    }),
    engagementRate: metricFromValues({
      metricId: "content.engagementRate",
      label: "Content Engagement Rate",
      values: records.map((record) =>
        isContentEngagementPair(record)
          ? contentEngagements(record)
          : null,
      ),
      value: safeDivide(totalEngagements, engagementImpressions),
      unit: "percentage",
      formula:
        "仅在五个字段均非 null 的相同记录中，SUM(clicks + reactions + comments + reposts) ÷ SUM(impressions)",
      period: periodForRecords(engagementPairs),
      records: engagementPairs,
      fields: [
        "clicks",
        "reactions",
        "comments",
        "reposts",
        "impressions",
      ],
      sourceModules: ["content"],
      extraReasons: [
        selection.reason,
        ...engagementCoverageReasons,
        ...(engagementImpressions === 0
          ? ["成对完整记录的 Impressions 合计为 0。"]
          : []),
      ],
    }),
    medianEngagementRate: metricFromValues({
      metricId: "content.medianEngagementRate",
      label: "内容互动率中位数",
      values: records.map(contentPerformance),
      value: median(engagementValues),
      unit: "percentage",
      formula: "MEDIAN(逐条内容互动率)",
      period,
      records,
      fields: [
        "impressions",
        "clicks",
        "reactions",
        "comments",
        "reposts",
        "engagementRate",
      ],
      sourceModules: ["content"],
      extraReasons: [selection.reason],
    }),
    contentRanking: {
      metricId: "content.ranking",
      label: "内容表现排名",
      formula:
        "优先按 (clicks + reactions + comments + reposts) ÷ impressions 排名；缺少组成项时使用导出 engagementRate",
      period,
      sourceModules: ["content"],
      items: rankingItems,
      reliability: rankingReliability.reliability,
      reliabilityReasons: rankingReliability.reasons,
    },
    byContentType: contentGroupMetrics(
      records,
      (record) => record.contentType,
      "content.type",
      period,
    ),
    byWeekday: contentGroupMetrics(
      records,
      (record) =>
        record.publishedAt
          ? weekdays[new Date(record.publishedAt).getUTCDay()]
          : null,
      "content.weekday",
      period,
    ),
  };
}

function pearsonCorrelation(
  pairs: readonly { x: number; y: number }[],
): number | null {
  if (pairs.length < 3) {
    return null;
  }
  const meanX =
    pairs.reduce((sum, pair) => sum + pair.x, 0) / pairs.length;
  const meanY =
    pairs.reduce((sum, pair) => sum + pair.y, 0) / pairs.length;
  const numerator = pairs.reduce(
    (sum, pair) => sum + (pair.x - meanX) * (pair.y - meanY),
    0,
  );
  const denominatorX = Math.sqrt(
    pairs.reduce((sum, pair) => sum + (pair.x - meanX) ** 2, 0),
  );
  const denominatorY = Math.sqrt(
    pairs.reduce((sum, pair) => sum + (pair.y - meanY) ** 2, 0),
  );
  if (denominatorX === 0 || denominatorY === 0) {
    return null;
  }
  return numerator / (denominatorX * denominatorY);
}

export function calculateCrossModuleMetrics(
  input: AnalysisInput,
): CrossModuleMetrics {
  const followers = temporalFollowers(input.records.followers);
  const visitors = temporalVisitors(input.records.visitors);
  const content = selectedContentRecords(input.records.content).records;
  const followerPeriod = periodForRecords(followers);
  const visitorPeriod = periodForRecords(visitors);
  const overlap = overlapPeriods([followerPeriod, visitorPeriod]);
  const sameGranularity =
    followerPeriod !== null &&
    visitorPeriod !== null &&
    followerPeriod.granularity !== "irregular" &&
    followerPeriod.granularity === visitorPeriod.granularity;

  const followerByDate = new Map(
    followers.flatMap((record) =>
      record.date && record.newFollowers !== null
        ? [[dateKey(record.date), record] as const]
        : [],
    ),
  );
  const visitorByDate = new Map(
    visitors.flatMap((record) =>
      record.date && record.uniqueVisitors !== null
        ? [[dateKey(record.date), record] as const]
        : [],
    ),
  );
  const commonDates = [...followerByDate.keys()]
    .filter((date) => visitorByDate.has(date))
    .sort();
  const candidateDates = overlap
    ? [
        ...new Set(
          [...followers, ...visitors].flatMap((record) => {
            const date = record.date;
            return date && inPeriod(record, overlap) ? [dateKey(date)] : [];
          }),
        ),
      ].sort()
    : [];
  const pairCoverageValues = candidateDates.map((date) =>
    followerByDate.has(date) && visitorByDate.has(date) ? 1 : null,
  );
  const trendPairs = commonDates.map((date) => ({
    date,
    follower: followerByDate.get(date) as FollowersRecord,
    visitor: visitorByDate.get(date) as VisitorsRecord,
  }));
  const commonPeriodBase = periodForRecords(
    trendPairs.flatMap(({ follower, visitor }) => [follower, visitor]),
  );
  const commonPeriod = commonPeriodBase
    ? { ...commonPeriodBase, sampleSize: trendPairs.length }
    : null;
  const trendCorrelation =
    sameGranularity && overlap
      ? pearsonCorrelation(
          trendPairs.map(({ follower, visitor }) => ({
            x: visitor.uniqueVisitors as number,
            y: follower.newFollowers as number,
          })),
        )
      : null;
  const pairedNewFollowers = sumAvailable(
    trendPairs.map(({ follower }) => follower.newFollowers),
  );
  const pairedUniqueVisitors = sumAvailable(
    trendPairs.map(({ visitor }) => visitor.uniqueVisitors),
  );
  const proxyRatio =
    sameGranularity && overlap
      ? safeDivide(pairedNewFollowers, pairedUniqueVisitors)
      : null;
  const pairedAudienceRecords = trendPairs.flatMap(
    ({ follower, visitor }) => [follower, visitor],
  );

  const contentCountByDate = new Map<string, ContentRecord[]>();
  for (const record of content) {
    if (!record.publishedAt) {
      continue;
    }
    const key = dateKey(record.publishedAt);
    const group = contentCountByDate.get(key) ?? [];
    group.push(record);
    contentCountByDate.set(key, group);
  }
  const publishingPairs = commonDates.flatMap((date) => {
    const posts = contentCountByDate.get(date) ?? [];
    const follower = followerByDate.get(date);
    const visitor = visitorByDate.get(date);
    if (!follower || !visitor) {
      return [];
    }
    return [
      {
        x: posts.length,
        y:
          (follower.newFollowers as number) +
          (visitor.uniqueVisitors as number),
      },
    ];
  });
  const publishingCorrelation =
    sameGranularity && overlap
      ? pearsonCorrelation(publishingPairs)
      : null;

  return {
    visitorFollowerTrendComparison: metricFromValues({
      metricId: "cross.visitorFollowerTrend",
      label: "Visitors 与 Followers 同期趋势相关性",
      values: pairCoverageValues,
      value: trendCorrelation,
      unit: "score",
      formula:
        "Pearson correlation(同期 uniqueVisitors, 同期 newFollowers)，至少 3 个同粒度共同周期",
      period: commonPeriod,
      records: trendPairs.flatMap(({ follower, visitor }) => [
        follower,
        visitor,
      ]),
      fields: ["date", "uniqueVisitors", "newFollowers"],
      sourceModules: ["visitors", "followers"],
      minReliableSample: 3,
      extraReasons: [
        "相关性只描述时间上的共同变化，不表示因果关系。",
        ...(!sameGranularity
          ? ["Followers 与 Visitors 粒度不一致或不规则。"]
          : []),
        ...(trendPairs.length < 3
          ? [`共同周期仅 ${trendPairs.length} 个。`]
          : []),
      ],
      caveat: "相关性不代表 Visitors 导致 Followers 增长，反之亦然。",
    }),
    visitorToFollowerProxyRatio: metricFromValues({
      metricId: "cross.visitorToFollowerProxy",
      label: "Visitor-to-Follower Proxy Ratio",
      values: candidateDates.map((date) =>
        followerByDate.has(date) && visitorByDate.has(date)
          ? (visitorByDate.get(date)?.uniqueVisitors ?? null)
          : null,
      ),
      value: proxyRatio,
      unit: "percentage",
      formula:
        "在 newFollowers 与 uniqueVisitors 均存在的同日期周期中，SUM(newFollowers) ÷ SUM(uniqueVisitors)",
      period: commonPeriod,
      records: pairedAudienceRecords,
      fields: ["date", "newFollowers", "uniqueVisitors"],
      sourceModules: ["followers", "visitors"],
      extraReasons: [
        "这是聚合数据代理比率，不是用户级真实转化率。",
        ...(!sameGranularity
          ? ["Followers 与 Visitors 粒度不一致或不规则。"]
          : []),
        ...(trendPairs.length === 0
          ? ["没有 newFollowers 与 uniqueVisitors 均存在的同日期周期。"]
          : []),
        ...(pairedUniqueVisitors === 0
          ? ["同日期成对周期内 Unique Visitors 合计为 0。"]
          : []),
      ],
      caveat:
        "该指标不能识别某位访客是否成为关注者，也不能当作真实转化率。",
    }),
    publishingWindowCorrelation: metricFromValues({
      metricId: "cross.publishingWindowCorrelation",
      label: "发布窗口与受众变化的时间相关性",
      values: pairCoverageValues,
      value: publishingCorrelation,
      unit: "score",
      formula:
        "Pearson correlation(同期发布数量, 同期 newFollowers + uniqueVisitors)，至少 3 个同粒度共同周期",
      period: commonPeriod,
      records: [
        ...content.filter(
          (record) =>
            record.publishedAt !== null &&
            commonDates.includes(dateKey(record.publishedAt)),
        ),
        ...pairedAudienceRecords,
      ],
      fields: [
        "publishedAt",
        "newFollowers",
        "uniqueVisitors",
      ],
      sourceModules: ["content", "followers", "visitors"],
      minReliableSample: 3,
      extraReasons: [
        "只衡量同期相关性，不表示内容发布导致受众变化。",
        ...(!sameGranularity
          ? ["模块粒度不一致或不规则。"]
          : []),
        ...(publishingPairs.length < 3
          ? [`可比较发布周期仅 ${publishingPairs.length} 个。`]
          : []),
      ],
      caveat: "不得将该时间相关性表述为内容发布造成增长。",
    }),
  };
}
