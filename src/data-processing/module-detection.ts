import {
  getDemographicDimension,
  getHeaderCandidates,
  getMappingOverrideKey,
  isFieldForModule,
  normalizeHeader,
} from "@/data-processing/field-aliases";
import {
  LINKEDIN_MODULES,
  type ConfidenceLevel,
  type FieldMapping,
  type LinkedInModule,
  type MappingOverrides,
  type ModuleCandidate,
  type ModuleDetection,
  type StandardField,
} from "@/domain/linkedin";

const MODULE_KEYWORDS: Record<LinkedInModule, readonly string[]> = {
  followers: ["follower", "followers", "new followers"],
  visitors: ["visitor", "visitors", "page views"],
  content: ["content", "post", "posts", "update"],
};

const GENERIC_FIELDS = new Set<StandardField>([
  "date",
  "publishedAt",
  "demographicDimension",
  "demographicValue",
  "demographicPercentage",
]);

interface CandidateFieldMatch {
  field: StandardField;
  priority: number;
}

interface InternalMapping {
  mapping: FieldMapping;
  priority: number;
}

export interface LocatedHeader {
  rowIndex: number;
  headers: string[];
  detection: ModuleDetection;
}

function confidenceFromScore(
  score: number,
  margin: number,
): ConfidenceLevel {
  if (score >= 60 && margin >= 15) {
    return "high";
  }

  if (score >= 32 && margin >= 7) {
    return "medium";
  }

  return "low";
}

function keywordScore(
  module: LinkedInModule,
  sheetName: string,
  fileName: string,
): { score: number; reasons: string[] } {
  const sheet = normalizeHeader(sheetName);
  const file = normalizeHeader(fileName);
  const sheetMatch = MODULE_KEYWORDS[module].find((keyword) =>
    sheet.includes(keyword),
  );
  const fileMatch = MODULE_KEYWORDS[module].find((keyword) =>
    file.includes(keyword),
  );
  const reasons: string[] = [];
  let score = 0;

  if (sheetMatch) {
    score += 14;
    reasons.push(`Sheet 名包含“${sheetMatch}”`);
  }

  if (fileMatch) {
    score += 6;
    reasons.push(`文件名提供 ${module} 弱提示`);
  }

  return { score, reasons };
}

function moduleCandidate(
  module: LinkedInModule,
  headers: readonly string[],
  sheetName: string,
  fileName: string,
): ModuleCandidate {
  const matchedFields = new Set<StandardField>();

  for (const header of headers) {
    for (const candidate of getHeaderCandidates(module, header)) {
      matchedFields.add(candidate.field);
    }
  }

  const distinctiveCount = [...matchedFields].filter(
    (field) => !GENERIC_FIELDS.has(field),
  ).length;
  const keyword = keywordScore(module, sheetName, fileName);
  const score = Math.min(
    100,
    matchedFields.size * 12 + distinctiveCount * 8 + keyword.score,
  );
  const reasons = [
    `表头命中 ${matchedFields.size} 个标准字段`,
    ...keyword.reasons,
  ];

  return {
    module,
    score,
    matchedFields: [...matchedFields],
    reasons,
  };
}

export function detectModule(
  headers: readonly string[],
  sheetName: string,
  fileName: string,
  moduleOverride?: LinkedInModule,
): ModuleDetection {
  const candidates = LINKEDIN_MODULES.map((module) =>
    moduleCandidate(module, headers, sheetName, fileName),
  ).sort((left, right) => right.score - left.score);

  if (moduleOverride) {
    return {
      detectedModule: moduleOverride,
      confidence: "high",
      requiresConfirmation: false,
      candidates,
      reasons: ["用户已手动确认模块；字段仍按映射规则逐项校验。"],
    };
  }

  const top = candidates[0];
  const runnerUp = candidates[1];
  const margin = top.score - runnerUp.score;

  if (top.score < 20 || (margin < 3 && top.score < 45)) {
    return {
      detectedModule: null,
      confidence: "low",
      requiresConfirmation: true,
      candidates,
      reasons: ["表头、Sheet 名与文件名提供的证据不足，需手动选择模块。"],
    };
  }

  const confidence = confidenceFromScore(top.score, margin);

  return {
    detectedModule: top.module,
    confidence,
    requiresConfirmation: confidence === "low" || margin < 7,
    candidates,
    reasons: [
      ...top.reasons,
      `领先下一候选 ${margin} 分`,
      ...(confidence === "low" || margin < 7
        ? ["识别差异较小，需要用户确认。"]
        : []),
    ],
  };
}

function headerText(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  if (value instanceof Date) {
    return value.toISOString();
  }

  return String(value).trim();
}

export function locateHeaderRow(
  rows: readonly unknown[][],
  sheetName: string,
  fileName: string,
  maxRows: number,
  moduleOverride?: LinkedInModule,
): LocatedHeader | null {
  let best: LocatedHeader | null = null;
  let bestScore = -1;
  const scanRows = rows.slice(0, maxRows);

  scanRows.forEach((row, rowIndex) => {
    const headers = row.map(headerText);
    const nonBlankHeaders = headers.filter(Boolean);

    if (nonBlankHeaders.length < 2) {
      return;
    }

    const detection = detectModule(
      nonBlankHeaders,
      sheetName,
      fileName,
      moduleOverride,
    );
    const topScore = detection.candidates[0]?.score ?? 0;
    const score = topScore + Math.min(nonBlankHeaders.length, 12);

    if ((topScore >= 20 || moduleOverride) && score > bestScore) {
      best = { rowIndex, headers, detection };
      bestScore = score;
    }
  });

  return best;
}

function resolveContextCandidates(
  module: LinkedInModule,
  rawHeader: string,
  sheetName: string,
  candidates: CandidateFieldMatch[],
): CandidateFieldMatch[] {
  const normalizedHeader = normalizeHeader(rawHeader);
  const normalizedSheet = normalizeHeader(sheetName);
  const demographicDimension = getDemographicDimension(sheetName);

  if (module === "followers" && normalizedHeader === "total followers") {
    if (demographicDimension) {
      return [{ field: "demographicCount", priority: 120 }];
    }

    if (normalizedSheet.includes("new follower")) {
      return [{ field: "newFollowers", priority: 120 }];
    }

    return [{ field: "totalFollowers", priority: 110 }];
  }

  if (
    module === "visitors" &&
    demographicDimension &&
    (normalizedHeader === "total views" ||
      normalizedHeader === "total visitors")
  ) {
    return [{ field: "demographicCount", priority: 120 }];
  }

  return candidates;
}

function initialMapping(
  module: LinkedInModule,
  sheetName: string,
  rawHeader: string,
  columnIndex: number,
  overrides: MappingOverrides,
): InternalMapping {
  const overrideKey = getMappingOverrideKey(
    sheetName,
    columnIndex,
    rawHeader,
  );

  if (Object.hasOwn(overrides, overrideKey)) {
    const override = overrides[overrideKey];

    if (override === null) {
      return {
        priority: 200,
        mapping: {
          rawHeader,
          columnIndex,
          standardField: null,
          status: "unmapped",
          confidence: "high",
          reason: "用户明确选择忽略该字段。",
          alternatives: [],
        },
      };
    }

    if (isFieldForModule(module, override)) {
      return {
        priority: 200,
        mapping: {
          rawHeader,
          columnIndex,
          standardField: override,
          status: "mapped",
          confidence: "high",
          reason: "用户手动确认字段映射。",
          alternatives: [],
        },
      };
    }
  }

  const candidates = resolveContextCandidates(
    module,
    rawHeader,
    sheetName,
    getHeaderCandidates(module, rawHeader),
  ).sort((left, right) => right.priority - left.priority);

  if (candidates.length === 0) {
    return {
      priority: 0,
      mapping: {
        rawHeader,
        columnIndex,
        standardField: null,
        status: "unmapped",
        confidence: "low",
        reason: "未在当前模块的集中式别名表中找到匹配。",
        alternatives: [],
      },
    };
  }

  const first = candidates[0];
  const tied = candidates.filter(
    (candidate) => candidate.priority === first.priority,
  );

  if (tied.length > 1) {
    return {
      priority: first.priority,
      mapping: {
        rawHeader,
        columnIndex,
        standardField: null,
        status: "conflict",
        confidence: "low",
        reason: "一个原始字段同等匹配多个标准字段，需要用户选择。",
        alternatives: tied.map(({ field }) => field),
      },
    };
  }

  const usedContextRule = first.priority >= 110;

  return {
    priority: first.priority,
    mapping: {
      rawHeader,
      columnIndex,
      standardField: first.field,
      status: "mapped",
      confidence: usedContextRule || first.priority >= 100 ? "high" : "medium",
      reason: usedContextRule
        ? "根据 Sheet 语义和字段组合应用了可解释的上下文规则。"
        : "与集中式字段别名精确匹配。",
      alternatives: candidates.slice(1).map(({ field }) => field),
    },
  };
}

export function buildFieldMappings(
  module: LinkedInModule,
  sheetName: string,
  headers: readonly string[],
  overrides: MappingOverrides = {},
): FieldMapping[] {
  const internal = headers
    .map((rawHeader, columnIndex) => ({ rawHeader, columnIndex }))
    .filter(({ rawHeader }) => rawHeader.trim() !== "")
    .map(({ rawHeader, columnIndex }) =>
      initialMapping(module, sheetName, rawHeader, columnIndex, overrides),
    );

  const mappedFields = new Map<StandardField, InternalMapping[]>();

  for (const entry of internal) {
    if (entry.mapping.status !== "mapped" || !entry.mapping.standardField) {
      continue;
    }

    const entries = mappedFields.get(entry.mapping.standardField) ?? [];
    entries.push(entry);
    mappedFields.set(entry.mapping.standardField, entries);
  }

  for (const [field, entries] of mappedFields) {
    if (entries.length < 2) {
      continue;
    }

    const sorted = [...entries].sort(
      (left, right) => right.priority - left.priority,
    );
    const winner = sorted[0];
    const tiedWinners = sorted.filter(
      (entry) => entry.priority === winner.priority,
    );

    for (const entry of entries) {
      const isWinner = tiedWinners.length === 1 && entry === winner;

      if (!isWinner) {
        entry.mapping = {
          ...entry.mapping,
          standardField: null,
          status: "conflict",
          confidence: "low",
          reason:
            tiedWinners.length > 1
              ? `多个原始字段同等匹配 ${field}，未自动选择。`
              : `优先使用更明确的字段“${winner.mapping.rawHeader}”；该字段需人工确认。`,
          alternatives: [field],
        };
      }
    }
  }

  return internal.map(({ mapping }) => mapping);
}

function mappedFieldSet(mappings: readonly FieldMapping[]): Set<StandardField> {
  return new Set(
    mappings.flatMap((mapping) =>
      mapping.status === "mapped" && mapping.standardField
        ? [mapping.standardField]
        : [],
    ),
  );
}

function requireOneOf(
  fields: readonly StandardField[],
  mapped: Set<StandardField>,
): StandardField | null {
  return fields.some((field) => mapped.has(field)) ? null : fields[0];
}

export function getMissingCriticalFields(
  module: LinkedInModule,
  sheetName: string,
  mappings: readonly FieldMapping[],
): StandardField[] {
  const mapped = mappedFieldSet(mappings);
  const missing: StandardField[] = [];
  const isDemographic =
    Boolean(getDemographicDimension(sheetName)) ||
    mapped.has("demographicValue");

  if (module === "followers") {
    if (isDemographic) {
      if (!mapped.has("demographicValue")) {
        missing.push("demographicValue");
      }
      const countOrPercentage = requireOneOf(
        ["demographicCount", "demographicPercentage"],
        mapped,
      );
      if (countOrPercentage) {
        missing.push(countOrPercentage);
      }
    } else {
      if (!mapped.has("date")) {
        missing.push("date");
      }
      const metric = requireOneOf(
        [
          "newFollowers",
          "totalFollowers",
          "organicFollowers",
          "sponsoredFollowers",
        ],
        mapped,
      );
      if (metric) {
        missing.push(metric);
      }
    }
  }

  if (module === "visitors") {
    if (isDemographic) {
      if (!mapped.has("demographicValue")) {
        missing.push("demographicValue");
      }
      const countOrPercentage = requireOneOf(
        ["demographicCount", "demographicPercentage"],
        mapped,
      );
      if (countOrPercentage) {
        missing.push(countOrPercentage);
      }
    } else {
      if (!mapped.has("date")) {
        missing.push("date");
      }
      const metric = requireOneOf(
        ["pageViews", "uniqueVisitors", "customButtonClicks"],
        mapped,
      );
      if (metric) {
        missing.push(metric);
      }
    }
  }

  if (module === "content") {
    if (!mapped.has("publishedAt")) {
      missing.push("publishedAt");
    }

    if (
      normalizeHeader(sheetName).includes("post") &&
      !mapped.has("title") &&
      !mapped.has("contentId")
    ) {
      missing.push("title");
    }

    const metric = requireOneOf(
      [
        "impressions",
        "uniqueImpressions",
        "clicks",
        "reactions",
        "comments",
        "reposts",
        "engagementRate",
        "clickThroughRate",
      ],
      mapped,
    );
    if (metric) {
      missing.push(metric);
    }
  }

  return missing;
}
