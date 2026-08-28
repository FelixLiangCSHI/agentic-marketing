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
        reason: "Post-level records with content identifiers are preferred over daily summaries.",
      }
    : {
        records: unique,
        reason: "No post-level records exist, so the available time-series records are used.",
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
    formula: `SUM(${input.field}), excluding flagged duplicates; null is omitted and zero retained`,
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
      reasons: [`No valid dated values are available for ${field}.`],
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
    // 单一计量单位：维度内只要存在 count 就按 count 排名，
    // 仅有 percentage 的记录被显式排除，避免 count/percentage 混加。
    const dimensionUnit = dimensionRecords.some(
      (record) => record.demographicCount !== null,
    )
      ? "count"
      : "percentage";
    const groups = new Map<
      string,
      { value: number; records: (FollowersRecord | VisitorsRecord)[] }
    >();
    let excludedRecords = 0;
    for (const record of dimensionRecords) {
      const key = record.demographicValue as string;
      const metricValue =
        dimensionUnit === "count"
          ? record.demographicCount
          : record.demographicPercentage;
      if (metricValue === null) {
        excludedRecords += 1;
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
      dimensionUnit,
      ["demographicValue", "demographicCount", "demographicPercentage"],
    );
    return {
      metricId: `${module}.demographic.${dimension}`,
      label: `${dimension} Top ${topN}`,
      formula:
        "Group by demographicDimension / demographicValue and rank by a single unit: sum counts when any count exists (percentage-only records excluded), otherwise sum percentages",
      period,
      sourceModules: [module],
      items,
      reliability:
        items.length === 0
          ? "unavailable"
          : dimensionRecords.length < MIN_GROUP_SAMPLE
            ? "directional"
            : "reliable",
      reliabilityReasons: [
        ...(dimensionRecords.length < MIN_GROUP_SAMPLE
          ? [`${dimension} has only ${dimensionRecords.length} audience records.`]
          : ["Audience segment sample size meets the current rule."]),
        ...(excludedRecords > 0
          ? [
              `${excludedRecords} record(s) excluded from the ${dimensionUnit} ranking because they only carry the other unit.`,
            ]
          : []),
      ],
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
          ? [`The group has only ${entry.records.length} samples.`]
          : ["Group sample size meets the current rule."],
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
      ? ["At least two comparable periods with totalFollowers are required."]
      : [];
  const startMetric = metricFromValues({
    metricId: "followers.start",
    label: "Starting followers",
    values: temporal.map((record) => record.totalFollowers),
    value: start,
    unit: "count",
    formula: "First non-null totalFollowers value in ascending date order",
    period,
    records: first ? [first] : [],
    fields: ["date", "totalFollowers"],
    sourceModules: ["followers"],
    minReliableSample: 1,
    extraReasons: totalReasons,
  });
  const endMetric = metricFromValues({
    metricId: "followers.end",
    label: "Ending followers",
    values: temporal.map((record) => record.totalFollowers),
    value: end,
    unit: "count",
    formula: "Last non-null totalFollowers value in ascending date order",
    period,
    records: last ? [last] : [],
    fields: ["date", "totalFollowers"],
    sourceModules: ["followers"],
    minReliableSample: 1,
    extraReasons: totalReasons,
  });
  const netMetric = metricFromValues({
    metricId: "followers.netGrowth",
    label: "Net growth",
    values: totals.map((record) => record.totalFollowers),
    value: net,
    unit: "count",
    formula: "Ending totalFollowers − starting totalFollowers",
    period,
    records: first && last ? [first, last] : [],
    fields: ["date", "totalFollowers"],
    sourceModules: ["followers"],
    minReliableSample: 2,
    extraReasons: totalReasons,
  });
  const growthMetric = metricFromValues({
    metricId: "followers.growthRate",
    label: "Follower growth rate",
    values: totals.map((record) => record.totalFollowers),
    value: growthRate,
    unit: "percentage",
    formula:
      "(ending totalFollowers − starting totalFollowers) ÷ starting totalFollowers; unavailable when starting value is zero",
    period,
    records: first && last ? [first, last] : [],
    fields: ["date", "totalFollowers"],
    sourceModules: ["followers"],
    minReliableSample: 2,
    extraReasons:
      start === 0
        ? ["Growth rate cannot be calculated because starting followers are zero."]
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
          `Only ${mixRecords.length}/${temporal.length} periods contain both organic and sponsored values.`,
        ]
      : [];

  return {
    startFollowers: startMetric,
    endFollowers: endMetric,
    netGrowth: netMetric,
    growthRate: growthMetric,
    newFollowersTotal: sumMetric({
      metricId: "followers.newTotal",
      label: "Total new followers",
      records: temporal,
      field: "newFollowers",
      sourceModule: "followers",
      period,
    }),
    organicShare: metricFromValues({
      metricId: "followers.organicShare",
      label: "Organic share",
      values: temporal.map((record) =>
        record.organicFollowers !== null &&
        record.sponsoredFollowers !== null
          ? record.organicFollowers
          : null,
      ),
      value: safeDivide(organic, mixTotal),
      unit: "percentage",
      formula:
        "For periods with both values: SUM(organicFollowers) ÷ (SUM(organicFollowers) + SUM(sponsoredFollowers))",
      period: mixPeriod,
      records: mixRecords,
      fields: ["organicFollowers", "sponsoredFollowers"],
      sourceModules: ["followers"],
      extraReasons: [
        ...mixCoverageReasons,
        ...(mixTotal === 0 ? ["Organic and sponsored values total zero."] : []),
      ],
    }),
    sponsoredShare: metricFromValues({
      metricId: "followers.sponsoredShare",
      label: "Sponsored share",
      values: temporal.map((record) =>
        record.organicFollowers !== null &&
        record.sponsoredFollowers !== null
          ? record.sponsoredFollowers
          : null,
      ),
      value: safeDivide(sponsored, mixTotal),
      unit: "percentage",
      formula:
        "For periods with both values: SUM(sponsoredFollowers) ÷ (SUM(organicFollowers) + SUM(sponsoredFollowers))",
      period: mixPeriod,
      records: mixRecords,
      fields: ["organicFollowers", "sponsoredFollowers"],
      sourceModules: ["followers"],
      extraReasons: [
        ...mixCoverageReasons,
        ...(mixTotal === 0 ? ["Organic and sponsored values total zero."] : []),
      ],
    }),
    newFollowersTrend: buildSeries(
      temporal,
      "newFollowers",
      "followers.newTrend",
      "New followers per period",
      "followers",
    ),
    demographicTopN: demographicTopN(
      "followers",
      records,
      periodForRecords(records),
    ),
    demographicTrend: unavailableMetric({
      metricId: "followers.demographicTrend",
      label: "Audience segment trend",
      unit: "text",
      formula:
        "Compare the same demographicDimension / demographicValue across at least two dated snapshots",
      sourceModules: ["followers"],
      reliabilityReasons: [
        "Audience records in the current model have no comparable dated snapshots.",
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
          `Only ${completePairs.length}/${temporal.length} periods contain both page views and unique visitors.`,
        ]
      : [];
  const comparable = temporal.filter(
    (record) => record.pageViews !== null,
  );
  // 粒度只由可比记录（含 pageViews）推断，避免稀疏无关字段
  // 使合法的环比周期被误判为不可比。
  const comparablePeriod = periodForRecords(comparable);
  const lastTwo = comparable.slice(-2);
  const periodChangePeriod = periodForRecords(lastTwo);
  const periodChangeComparable =
    lastTwo.length === 2 &&
    comparablePeriod !== null &&
    comparablePeriod.granularity !== "irregular" &&
    hasComparablePeriodGap(
      lastTwo[0].date as string,
      lastTwo[1].date as string,
      comparablePeriod.granularity,
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
      label: "Total page views",
      records: temporal,
      field: "pageViews",
      sourceModule: "visitors",
      period,
    }),
    uniqueVisitorsTotal: sumMetric({
      metricId: "visitors.uniqueVisitorsTotal",
      label: "Total unique visitors",
      records: temporal,
      field: "uniqueVisitors",
      sourceModule: "visitors",
      period,
    }),
    pageViewsPerVisitor: metricFromValues({
      metricId: "visitors.pageViewsPerVisitor",
      label: "Average page views per visitor",
      values: temporal.map((record) =>
        record.pageViews !== null && record.uniqueVisitors !== null
          ? record.uniqueVisitors
          : null,
      ),
      value: safeDivide(pairedPageViewsTotal, pairedUniqueVisitorsTotal),
      unit: "ratio",
      formula:
        "For records with both values: SUM(pageViews) ÷ SUM(uniqueVisitors)",
      period: pairPeriod,
      records: completePairs,
      fields: ["pageViews", "uniqueVisitors"],
      sourceModules: ["visitors"],
      extraReasons: [
        ...pairCoverageReasons,
        ...(pairedUniqueVisitorsTotal === 0
          ? ["Unique visitors total zero across complete pairs."]
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
      "Page views trend",
      "visitors",
    ),
    uniqueVisitorsTrend: buildSeries(
      temporal,
      "uniqueVisitors",
      "visitors.uniqueVisitorsTrend",
      "Unique visitors trend",
      "visitors",
    ),
    periodOverPeriodChange: metricFromValues({
      metricId: "visitors.periodChange",
      label: "Page views period-over-period change",
      values: lastTwo.map((record) => record.pageViews),
      value: periodChange,
      unit: "percentage",
      formula: "(latest pageViews − prior pageViews) ÷ prior pageViews",
      period: periodChangePeriod,
      records: lastTwo,
      fields: ["date", "pageViews"],
      sourceModules: ["visitors"],
      minReliableSample: 2,
      extraReasons:
        lastTwo.length < 2
          ? ["At least two comparable periods are required."]
          : !periodChangeComparable
            ? ["The latest two valid periods are not comparably spaced by day, week, or month."]
          : lastTwo[0].pageViews === 0
            ? ["Prior-period page views are zero."]
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
    `${record.source.sheetName} row ${record.source.rowNumber}`
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
          ? [`The group has only ${group.length} items, below the ${MIN_GROUP_SAMPLE}-item rule.`]
          : ["Group sample size meets the current rule."];

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
            formula: "SUM(impressions) within the group",
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
              "Within the group, for records with both values: SUM(clicks) ÷ SUM(impressions)",
            period: periodForRecords(clickThroughPairs),
            records: clickThroughPairs,
            fields: ["clicks", "impressions"],
            sourceModules: ["content"],
            minReliableSample: MIN_GROUP_SAMPLE,
            extraReasons: [
              ...reasons,
              ...(clickThroughPairs.length < group.length
                ? [
                    `Only ${clickThroughPairs.length}/${group.length} group items contain both clicks and impressions.`,
                  ]
                : []),
              ...(pairedImpressions === 0
                ? ["Impressions total zero across complete pairs."]
                : []),
            ],
          }),
          metricFromValues({
            metricId: `${prefix}.${key}.medianEngagement`,
            label: "Median engagement rate",
            values: group.map(contentPerformance),
            value: median(engagementValues),
            unit: "percentage",
            formula: "MEDIAN(per-item engagement rate)",
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
          `Only ${engagementPairs.length}/${records.length} items contain impressions, clicks, reactions, comments, and reposts.`,
        ]
      : [];
  const clickThroughCoverageReasons =
    clickThroughPairs.length < records.length
      ? [
          `Only ${clickThroughPairs.length}/${records.length} items contain both clicks and impressions.`,
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
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
  ];

  return {
    publishedCount: metricFromValues({
      metricId: "content.publishedCount",
      label: "Published content count",
      values: records.map((record) =>
        record.publishedAt === null ? null : 1,
      ),
      value:
        records.filter((record) => record.publishedAt !== null).length || null,
      unit: "count",
      formula: "COUNT(unique post-level records with publishedAt)",
      period,
      records,
      fields: ["publishedAt", "contentId", "title"],
      sourceModules: ["content"],
      extraReasons: [selection.reason],
    }),
    impressionsTotal: sumMetric({
      metricId: "content.impressions",
      label: "Total impressions",
      records,
      field: "impressions",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    clicksTotal: sumMetric({
      metricId: "content.clicks",
      label: "Total clicks",
      records,
      field: "clicks",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    reactionsTotal: sumMetric({
      metricId: "content.reactions",
      label: "Total reactions",
      records,
      field: "reactions",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    commentsTotal: sumMetric({
      metricId: "content.comments",
      label: "Total comments",
      records,
      field: "comments",
      sourceModule: "content",
      period,
      extraReasons: [selection.reason],
    }),
    repostsTotal: sumMetric({
      metricId: "content.reposts",
      label: "Total reposts",
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
        "For records with both values: SUM(clicks) ÷ SUM(impressions)",
      period: periodForRecords(clickThroughPairs),
      records: clickThroughPairs,
      fields: ["clicks", "impressions"],
      sourceModules: ["content"],
      extraReasons: [
        selection.reason,
        ...clickThroughCoverageReasons,
        ...(pairedClickImpressions === 0
          ? ["Impressions total zero across complete pairs."]
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
        "For records with all five fields: SUM(clicks + reactions + comments + reposts) ÷ SUM(impressions)",
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
          ? ["Impressions total zero across complete pairs."]
          : []),
      ],
    }),
    medianEngagementRate: metricFromValues({
      metricId: "content.medianEngagementRate",
      label: "Median content engagement rate",
      values: records.map(contentPerformance),
      value: median(engagementValues),
      unit: "percentage",
      formula: "MEDIAN(per-item engagement rate)",
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
      label: "Content performance ranking",
      formula:
        "Rank by (clicks + reactions + comments + reposts) ÷ impressions; use exported engagementRate when components are missing",
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
      label: "Concurrent visitor and follower trend correlation",
      values: pairCoverageValues,
      value: trendCorrelation,
      unit: "score",
      formula:
        "Pearson correlation(concurrent uniqueVisitors, concurrent newFollowers) across at least three shared periods",
      period: commonPeriod,
      records: trendPairs.flatMap(({ follower, visitor }) => [
        follower,
        visitor,
      ]),
      fields: ["date", "uniqueVisitors", "newFollowers"],
      sourceModules: ["visitors", "followers"],
      minReliableSample: 3,
      extraReasons: [
        "Correlation describes concurrent movement, not causation.",
        ...(!sameGranularity
          ? ["Follower and visitor granularity differs or is irregular."]
          : []),
        ...(trendPairs.length < 3
          ? [`Only ${trendPairs.length} shared periods are available.`]
          : []),
      ],
      caveat: "Correlation does not mean visitors cause follower growth or vice versa.",
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
        "For same-date periods with both values: SUM(newFollowers) ÷ SUM(uniqueVisitors)",
      period: commonPeriod,
      records: pairedAudienceRecords,
      fields: ["date", "newFollowers", "uniqueVisitors"],
      sourceModules: ["followers", "visitors"],
      extraReasons: [
        "This aggregate proxy ratio is not a user-level conversion rate.",
        ...(!sameGranularity
          ? ["Follower and visitor granularity differs or is irregular."]
          : []),
        ...(trendPairs.length === 0
          ? ["No same-date periods contain both newFollowers and uniqueVisitors."]
          : []),
        ...(pairedUniqueVisitors === 0
          ? ["Unique visitors total zero across same-date pairs."]
          : []),
      ],
      caveat:
        "This metric cannot identify whether a visitor became a follower and is not a conversion rate.",
    }),
    publishingWindowCorrelation: metricFromValues({
      metricId: "cross.publishingWindowCorrelation",
      label: "Publishing window and audience change correlation",
      values: pairCoverageValues,
      value: publishingCorrelation,
      unit: "score",
      formula:
        "Pearson correlation(concurrent publishing count, concurrent newFollowers + uniqueVisitors) across at least three shared periods",
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
        "This measures concurrent correlation and does not show publishing caused audience change.",
        ...(!sameGranularity
          ? ["Module granularity differs or is irregular."]
          : []),
        ...(publishingPairs.length < 3
          ? [`Only ${publishingPairs.length} comparable publishing periods are available.`]
          : []),
      ],
      caveat: "Do not describe this temporal correlation as publishing-driven growth.",
    }),
  };
}
