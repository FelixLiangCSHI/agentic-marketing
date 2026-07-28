import type {
  RawCellValue,
  StandardField,
  ValidationIssueCode,
} from "@/domain/linkedin";

export interface NormalizationProblem {
  code: ValidationIssueCode;
  message: string;
  severity: "warning" | "error";
}

export interface NormalizationResult<T> {
  value: T | null;
  problems: NormalizationProblem[];
}

const EMPTY_MARKERS = new Set([
  "",
  "-",
  "--",
  "n/a",
  "na",
  "null",
  "not available",
]);

function rawToString(raw: RawCellValue): string {
  return typeof raw === "string" ? raw.trim() : String(raw);
}

export function toSerializableRawValue(value: unknown): RawCellValue {
  if (value === null || value === undefined) {
    return null;
  }

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value.toISOString();
  }

  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }

  return String(value);
}

export function isBlankValue(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    (typeof value === "string" && value.trim() === "")
  );
}

export function isFormulaLikeText(value: string): boolean {
  return /^[=+@]/.test(value.trim());
}

export function normalizeText(raw: RawCellValue): NormalizationResult<string> {
  if (raw === null) {
    return { value: null, problems: [] };
  }

  const value = rawToString(raw);

  if (EMPTY_MARKERS.has(value.toLocaleLowerCase("en-US"))) {
    return { value: null, problems: [] };
  }

  if (isFormulaLikeText(value)) {
    return {
      value,
      problems: [
        {
          code: "FORMULA_LIKE_TEXT",
          severity: "warning",
          message: "检测到类似公式的文本；已按普通文本保留，未执行。",
        },
      ],
    };
  }

  return { value, problems: [] };
}

function normalizeNumericString(value: string): string {
  const compact = value.replace(/[\s\u00A0]/g, "");
  const isParenthesized = /^\(.*\)$/.test(compact);
  const unsigned = isParenthesized ? compact.slice(1, -1) : compact;
  let normalized = unsigned;

  if (unsigned.includes(",") && unsigned.includes(".")) {
    normalized =
      unsigned.lastIndexOf(",") > unsigned.lastIndexOf(".")
        ? unsigned.replace(/\./g, "").replace(",", ".")
        : unsigned.replace(/,/g, "");
  } else if (unsigned.includes(",")) {
    const commaParts = unsigned.split(",");
    normalized =
      commaParts.length === 2 && commaParts[1].length <= 2
        ? unsigned.replace(",", ".")
        : unsigned.replace(/,/g, "");
  }

  return isParenthesized ? `-${normalized}` : normalized;
}

export function normalizeNumber(
  raw: RawCellValue,
): NormalizationResult<number> {
  if (raw === null) {
    return { value: null, problems: [] };
  }

  if (typeof raw === "boolean") {
    return {
      value: null,
      problems: [
        {
          code: "INVALID_NUMBER",
          severity: "error",
          message: "布尔值不能作为数值使用。",
        },
      ],
    };
  }

  if (typeof raw === "string") {
    const trimmed = raw.trim();

    if (EMPTY_MARKERS.has(trimmed.toLocaleLowerCase("en-US"))) {
      return { value: null, problems: [] };
    }

    if (isFormulaLikeText(trimmed)) {
      return {
        value: null,
        problems: [
          {
            code: "FORMULA_LIKE_TEXT",
            severity: "error",
            message: "类似公式的文本不会被当作数值计算。",
          },
        ],
      };
    }
  }

  const normalized =
    typeof raw === "number"
      ? raw
      : Number(normalizeNumericString(rawToString(raw)));

  if (!Number.isFinite(normalized)) {
    return {
      value: null,
      problems: [
        {
          code: "INVALID_NUMBER",
          severity: "error",
          message: "无法将该值识别为有效数字。",
        },
      ],
    };
  }

  const problems: NormalizationProblem[] = [];

  if (normalized < 0) {
    problems.push({
      code: "NEGATIVE_VALUE",
      severity: "warning",
      message: "检测到负数，请确认导出数据含义。",
    });
  }

  return { value: normalized, problems };
}

export function normalizePercentage(
  raw: RawCellValue,
  cellFormat?: string,
): NormalizationResult<number> {
  if (raw === null) {
    return { value: null, problems: [] };
  }

  const stringValue = rawToString(raw);
  const hasPercentSign = stringValue.endsWith("%");
  const numeric = normalizeNumber(
    hasPercentSign ? stringValue.slice(0, -1) : raw,
  );

  if (numeric.value === null) {
    return numeric;
  }

  const isExcelPercentage =
    typeof raw === "number" && Boolean(cellFormat?.includes("%"));
  let value = numeric.value;
  const problems = [...numeric.problems];

  if (hasPercentSign) {
    value /= 100;
  } else if (!isExcelPercentage && Math.abs(value) > 1 && Math.abs(value) <= 100) {
    value /= 100;
    problems.push({
      code: "PERCENTAGE_SCALE_INFERRED",
      severity: "warning",
      message: "数值缺少百分号，已按百分数缩放并标记供确认。",
    });
  }

  if (value < 0 || value > 1) {
    problems.push({
      code: "PERCENTAGE_OUT_OF_RANGE",
      severity: "warning",
      message: "百分比超出 0%–100% 范围，请确认数据。",
    });
  }

  return { value, problems };
}

const MONTHS: Record<string, number> = {
  jan: 0,
  january: 0,
  feb: 1,
  february: 1,
  mar: 2,
  march: 2,
  apr: 3,
  april: 3,
  may: 4,
  jun: 5,
  june: 5,
  jul: 6,
  july: 6,
  aug: 7,
  august: 7,
  sep: 8,
  sept: 8,
  september: 8,
  oct: 9,
  october: 9,
  nov: 10,
  november: 10,
  dec: 11,
  december: 11,
};

function validUtcDate(year: number, month: number, day: number): Date | null {
  const value = new Date(Date.UTC(year, month, day));

  if (
    value.getUTCFullYear() !== year ||
    value.getUTCMonth() !== month ||
    value.getUTCDate() !== day
  ) {
    return null;
  }

  return value;
}

function parseDateString(value: string): {
  date: Date | null;
  ambiguous: boolean;
} {
  if (/^\d{4}-\d{2}-\d{2}T/.test(value)) {
    const date = new Date(value);
    return {
      date: Number.isNaN(date.getTime()) ? null : date,
      ambiguous: false,
    };
  }

  const iso = value.match(
    /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[T\s].*)?$/,
  );
  if (iso) {
    return {
      date: validUtcDate(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3])),
      ambiguous: false,
    };
  }

  const slash = value.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
  if (slash) {
    const first = Number(slash[1]);
    const second = Number(slash[2]);
    const year = Number(slash[3]);
    const dayFirst = first > 12;
    const month = dayFirst ? second : first;
    const day = dayFirst ? first : second;

    return {
      date: validUtcDate(year, month - 1, day),
      ambiguous: first <= 12 && second <= 12,
    };
  }

  const namedMonth = value
    .replace(/,/g, "")
    .match(/^([a-z]+)\s+(\d{1,2})\s+(\d{4})$/i);
  if (namedMonth) {
    const month = MONTHS[namedMonth[1].toLocaleLowerCase("en-US")];
    return {
      date:
        month === undefined
          ? null
          : validUtcDate(Number(namedMonth[3]), month, Number(namedMonth[2])),
      ambiguous: false,
    };
  }

  const dayNamedMonth = value.match(
    /^(\d{1,2})[-\s]([a-z]+)[-\s](\d{4})$/i,
  );
  if (dayNamedMonth) {
    const month = MONTHS[dayNamedMonth[2].toLocaleLowerCase("en-US")];
    return {
      date:
        month === undefined
          ? null
          : validUtcDate(
              Number(dayNamedMonth[3]),
              month,
              Number(dayNamedMonth[1]),
            ),
      ambiguous: false,
    };
  }

  return { date: null, ambiguous: false };
}

export function normalizeDate(
  raw: RawCellValue,
  field: Extract<StandardField, "date" | "publishedAt">,
): NormalizationResult<string> {
  if (raw === null) {
    return { value: null, problems: [] };
  }

  let parsed: Date | null = null;
  let ambiguous = false;

  if (typeof raw === "number" && Number.isFinite(raw)) {
    const excelEpoch = Date.UTC(1899, 11, 30);
    parsed = new Date(excelEpoch + raw * 86_400_000);
  } else if (typeof raw === "string") {
    const normalized = parseDateString(raw.trim());
    parsed = normalized.date;
    ambiguous = normalized.ambiguous;
  }

  if (!parsed || Number.isNaN(parsed.getTime())) {
    return {
      value: null,
      problems: [
        {
          code: "INVALID_DATE",
          severity: "error",
          message: "无法识别日期格式，已保留原始值供确认。",
        },
      ],
    };
  }

  const problems: NormalizationProblem[] = [];
  const currentYear = new Date().getUTCFullYear();

  if (ambiguous) {
    problems.push({
      code: "AMBIGUOUS_DATE",
      severity: "warning",
      message: "日期的月/日顺序存在歧义，当前按月/日/年解释。",
    });
  }

  if (parsed.getUTCFullYear() < 2003 || parsed.getUTCFullYear() > currentYear + 1) {
    problems.push({
      code: "UNREASONABLE_DATE",
      severity: "warning",
      message: "日期超出合理范围，请确认导出内容。",
    });
  }

  return {
    value:
      field === "publishedAt"
        ? parsed.toISOString()
        : parsed.toISOString().slice(0, 10),
    problems,
  };
}
