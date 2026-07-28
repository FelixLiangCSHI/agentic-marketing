import type {
  AnalysisPeriod,
  Metric,
  MetricReliability,
  MetricUnit,
  SourceReference,
  TimeGranularity,
} from "@/domain/analysis";
import type {
  LinkedInModule,
  NormalizedLinkedInRecord,
  StandardField,
} from "@/domain/linkedin";

const DAY_MS = 86_400_000;

export function recordDate(
  record: NormalizedLinkedInRecord,
): string | null {
  return record.module === "content" ? record.publishedAt : record.date;
}

export function dateKey(value: string): string {
  return value.slice(0, 10);
}

export function utcDay(value: string): number {
  return Math.floor(new Date(dateKey(value)).getTime() / DAY_MS);
}

export function sortedUniqueDates(
  records: readonly NormalizedLinkedInRecord[],
): string[] {
  return [
    ...new Set(
      records.flatMap((record) => {
        const date = recordDate(record);
        return date ? [dateKey(date)] : [];
      }),
    ),
  ].sort();
}

export function inferGranularity(
  dates: readonly string[],
): TimeGranularity {
  if (dates.length < 2) {
    return "irregular";
  }

  const sorted = [...dates].sort();
  const differences = sorted.slice(1).map((date, index) => {
    return utcDay(date) - utcDay(sorted[index]);
  });
  const medianDifference = median(differences);

  if (medianDifference === null) {
    return "irregular";
  }
  if (medianDifference >= 1 && medianDifference <= 2) {
    return "daily";
  }
  if (medianDifference >= 6 && medianDifference <= 8) {
    return "weekly";
  }
  if (medianDifference >= 27 && medianDifference <= 32) {
    return "monthly";
  }
  return "irregular";
}

export function periodForRecords(
  records: readonly NormalizedLinkedInRecord[],
): AnalysisPeriod | null {
  const dates = sortedUniqueDates(records);
  if (dates.length === 0) {
    return null;
  }

  return {
    start: dates[0],
    end: dates.at(-1) as string,
    granularity: inferGranularity(dates),
    sampleSize: records.length,
  };
}

export function overlapPeriods(
  periods: readonly (AnalysisPeriod | null)[],
): AnalysisPeriod | null {
  const available = periods.filter(
    (period): period is AnalysisPeriod => period !== null,
  );
  if (available.length === 0) {
    return null;
  }

  const start = available.map((period) => period.start).sort().at(-1);
  const end = available.map((period) => period.end).sort()[0];
  if (!start || !end || start > end) {
    return null;
  }

  const granularities = new Set(
    available.map((period) => period.granularity),
  );
  return {
    start,
    end,
    granularity:
      granularities.size === 1
        ? available[0].granularity
        : "irregular",
    sampleSize: available.reduce(
      (smallest, period) => Math.min(smallest, period.sampleSize),
      Number.POSITIVE_INFINITY,
    ),
  };
}

export function median(values: readonly number[]): number | null {
  if (values.length === 0) {
    return null;
  }
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle];
}

export function sumAvailable(
  values: readonly (number | null)[],
): number | null {
  const available = values.filter(
    (value): value is number => value !== null,
  );
  return available.length === 0
    ? null
    : available.reduce((sum, value) => sum + value, 0);
}

export function safeDivide(
  numerator: number | null,
  denominator: number | null,
): number | null {
  if (
    numerator === null ||
    denominator === null ||
    denominator === 0
  ) {
    return null;
  }
  return numerator / denominator;
}

export function referencesForRecords(
  records: readonly NormalizedLinkedInRecord[],
  fields: readonly StandardField[],
): SourceReference[] {
  const groups = new Map<
    string,
    {
      module: LinkedInModule;
      fileName: string;
      sheetName: string;
      rows: number[];
    }
  >();

  for (const record of records) {
    const key = `${record.module}\u0000${record.source.fileName}\u0000${record.source.sheetName}`;
    const group = groups.get(key) ?? {
      module: record.module,
      fileName: record.source.fileName,
      sheetName: record.source.sheetName,
      rows: [],
    };
    group.rows.push(record.source.rowNumber);
    groups.set(key, group);
  }

  return [...groups.values()]
    .flatMap((group) => {
      const rows = [...new Set(group.rows)].sort((left, right) => left - right);
      const ranges: { start: number; end: number }[] = [];
      for (const row of rows) {
        const current = ranges.at(-1);
        if (current && row === current.end + 1) {
          current.end = row;
        } else {
          ranges.push({ start: row, end: row });
        }
      }
      return ranges.map((range) => ({
        module: group.module,
        fileName: group.fileName,
        sheetName: group.sheetName,
        rowStart: range.start,
        rowEnd: range.end,
        fields: [...fields],
      }));
    })
    .sort(
      (left, right) =>
        left.module.localeCompare(right.module) ||
        left.fileName.localeCompare(right.fileName) ||
        left.sheetName.localeCompare(right.sheetName) ||
        left.rowStart - right.rowStart,
    );
}

export function formatMetricValue(
  value: number | string | null,
  unit: MetricUnit,
): string {
  if (value === null) {
    return "unavailable";
  }
  if (typeof value === "string") {
    return value;
  }
  if (unit === "percentage") {
    return new Intl.NumberFormat("zh-CN", {
      style: "percent",
      maximumFractionDigits: 1,
    }).format(value);
  }
  if (unit === "ratio") {
    return new Intl.NumberFormat("zh-CN", {
      maximumFractionDigits: 2,
    }).format(value);
  }
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
  }).format(value);
}

export function reliabilityForCoverage(
  availableCount: number,
  totalCount: number,
  options: {
    minReliableSample?: number;
    blocked?: boolean;
    extraReasons?: string[];
  } = {},
): { reliability: MetricReliability; reasons: string[] } {
  const reasons = [...(options.extraReasons ?? [])];
  if (options.blocked || totalCount === 0 || availableCount === 0) {
    reasons.push(
      totalCount === 0 ? "没有可用记录。" : "计算所需字段没有有效值。",
    );
    return { reliability: "unavailable", reasons };
  }

  const coverage = availableCount / totalCount;
  const minReliableSample = options.minReliableSample ?? 3;
  if (coverage < 0.8 || availableCount < minReliableSample) {
    if (coverage < 0.8) {
      reasons.push(`字段完整率为 ${(coverage * 100).toFixed(0)}%。`);
    }
    if (availableCount < minReliableSample) {
      reasons.push(`有效样本仅 ${availableCount} 条。`);
    }
    return { reliability: "directional", reasons };
  }

  reasons.push("字段完整率与样本量满足当前规则。");
  return { reliability: "reliable", reasons };
}

export function createMetric(input: {
  metricId: string;
  label: string;
  value: number | string | null;
  unit: MetricUnit;
  formula: string;
  period: AnalysisPeriod | null;
  sourceModules: LinkedInModule[];
  sourceReferences: SourceReference[];
  reliability: MetricReliability;
  reliabilityReasons: string[];
  caveat?: string;
}): Metric {
  return {
    ...input,
    formattedValue: formatMetricValue(input.value, input.unit),
  };
}

export function unavailableMetric(input: {
  metricId: string;
  label: string;
  unit: MetricUnit;
  formula: string;
  sourceModules: LinkedInModule[];
  reliabilityReasons: string[];
  period?: AnalysisPeriod | null;
  caveat?: string;
}): Metric {
  return createMetric({
    ...input,
    value: null,
    period: input.period ?? null,
    sourceReferences: [],
    reliability: "unavailable",
  });
}

export function fieldValue(
  record: NormalizedLinkedInRecord,
  field: StandardField,
): number | string | null {
  const value = Object.entries(record).find(([key]) => key === field)?.[1];
  return typeof value === "number" || typeof value === "string"
    ? value
    : null;
}

export function numberField(
  record: NormalizedLinkedInRecord,
  field: StandardField,
): number | null {
  const value = fieldValue(record, field);
  return typeof value === "number" ? value : null;
}

export function inPeriod(
  record: NormalizedLinkedInRecord,
  period: AnalysisPeriod,
): boolean {
  const date = recordDate(record);
  return Boolean(date && dateKey(date) >= period.start && dateKey(date) <= period.end);
}
