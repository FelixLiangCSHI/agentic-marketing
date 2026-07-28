import * as XLSX from "@e965/xlsx";

import {
  FIELD_LABELS,
  getDemographicDimension,
} from "@/data-processing/field-aliases";
import {
  buildFieldMappings,
  getMissingCriticalFields,
  locateHeaderRow,
} from "@/data-processing/module-detection";
import {
  isBlankValue,
  normalizeDate,
  normalizeNumber,
  normalizePercentage,
  normalizeText,
  toSerializableRawValue,
  type NormalizationProblem,
} from "@/data-processing/normalizers";
import type {
  ContentRecord,
  FieldMapping,
  FileParseResult,
  FollowersRecord,
  LinkedInModule,
  MappingOverrides,
  ModuleDetection,
  NormalizedLinkedInRecord,
  ParseError,
  RawCellValue,
  RecordIssueReference,
  SheetParseResult,
  SourceProvenance,
  SpreadsheetFormat,
  StandardField,
  ValidationIssue,
  VisitorsRecord,
} from "@/domain/linkedin";

export const MAX_SHEETS_PER_WORKBOOK = 30;
export const MAX_ROWS_PER_SHEET = 50_000;
export const MAX_HEADER_SCAN_ROWS = 40;
export const PREVIEW_ROW_COUNT = 5;

interface ParseSpreadsheetInput {
  bytes: Uint8Array;
  fileName: string;
  mimeType: string;
  format: SpreadsheetFormat;
  expectedModule?: LinkedInModule;
  moduleOverride?: LinkedInModule;
  mappingOverrides?: MappingOverrides;
}

interface CellReadResult {
  rawValue: RawCellValue;
  numberFormat?: string;
  isFormula: boolean;
}

interface NormalizedCell {
  value: string | number | null;
  problems: NormalizationProblem[];
}

interface ParsedRow {
  record: NormalizedLinkedInRecord;
  issues: ValidationIssue[];
  valid: boolean;
}

export class SpreadsheetParseException extends Error {
  readonly parseError: ParseError;

  constructor(parseError: ParseError) {
    super(parseError.message);
    this.name = "SpreadsheetParseException";
    this.parseError = parseError;
  }
}

function parseError(
  code: ParseError["code"],
  message: string,
  retryable = true,
): SpreadsheetParseException {
  return new SpreadsheetParseException({ code, message, retryable });
}

export function getSafeParseError(reason: unknown): ParseError {
  if (reason instanceof SpreadsheetParseException) {
    return reason.parseError;
  }

  const technicalMessage =
    reason instanceof Error ? reason.message.toLocaleLowerCase("en-US") : "";

  if (
    /encrypt|password|cryptoapi|password-protected/.test(technicalMessage)
  ) {
    return {
      code: "ENCRYPTED_WORKBOOK",
      message: "The workbook is encrypted or password protected. Remove protection before uploading.",
      retryable: true,
    };
  }

  if (
    /corrupt|invalid|unsupported|bad (zip|file)|cannot find/.test(
      technicalMessage,
    )
  ) {
    return {
      code: "CORRUPT_FILE",
      message: "The file is damaged or is not a valid spreadsheet. Export it again and retry.",
      retryable: true,
    };
  }

  return {
    code: "PARSE_FAILED",
    message: "Parsing failed and source content was not retained. Check the file and retry.",
    retryable: true,
  };
}

function emptyDetection(reason: string): ModuleDetection {
  return {
    detectedModule: null,
    confidence: "low",
    requiresConfirmation: true,
    candidates: [],
    reasons: [reason],
  };
}

function emptySheetResult(
  sheetName: string,
  code: "EMPTY_SHEET" | "NO_HEADER_FOUND",
  message: string,
): SheetParseResult {
  const issue: ValidationIssue = {
    code,
    severity: code === "EMPTY_SHEET" ? "warning" : "error",
    scope: "sheet",
    sheetName,
    message,
  };

  return {
    sheetName,
    headerRow: null,
    detection: emptyDetection(message),
    mappings: [],
    unmappedFields: [],
    conflictFields: [],
    missingCriticalFields: [],
    totalRows: 0,
    validRows: 0,
    duplicateRows: 0,
    dateRange: null,
    records: [],
    preview: [],
    issues: [issue],
    canProceed: false,
  };
}

function worksheetRows(sheet: XLSX.WorkSheet): {
  rows: unknown[][];
  startRow: number;
} {
  const reference = sheet["!ref"];

  if (typeof reference !== "string") {
    return { rows: [], startRow: 0 };
  }

  const range = XLSX.utils.decode_range(reference);
  const rows = XLSX.utils.sheet_to_json<unknown[]>(sheet, {
    header: 1,
    raw: true,
    defval: null,
    blankrows: true,
    skipHidden: false,
    UTC: true,
  });

  return { rows, startRow: range.s.r };
}

function readCell(
  sheet: XLSX.WorkSheet,
  absoluteRowIndex: number,
  columnIndex: number,
  fallback: unknown,
): CellReadResult {
  const address = XLSX.utils.encode_cell({
    r: absoluteRowIndex,
    c: columnIndex,
  });
  const cell = sheet[address] as XLSX.CellObject | undefined;

  if (cell?.f) {
    return {
      rawValue: null,
      numberFormat:
        cell.z === undefined || cell.z === null ? undefined : String(cell.z),
      isFormula: true,
    };
  }

  return {
    rawValue: toSerializableRawValue(cell?.v ?? fallback),
    numberFormat:
      cell?.z === undefined || cell.z === null ? undefined : String(cell.z),
    isFormula: false,
  };
}

const NUMERIC_FIELDS = new Set<StandardField>([
  "totalFollowers",
  "newFollowers",
  "organicFollowers",
  "sponsoredFollowers",
  "demographicCount",
  "pageViews",
  "uniqueVisitors",
  "customButtonClicks",
  "impressions",
  "uniqueImpressions",
  "clicks",
  "reactions",
  "comments",
  "reposts",
]);

const PERCENTAGE_FIELDS = new Set<StandardField>([
  "demographicPercentage",
  "engagementRate",
  "clickThroughRate",
]);

function normalizeCell(
  field: StandardField,
  rawValue: RawCellValue,
  numberFormat?: string,
): NormalizedCell {
  if (field === "date" || field === "publishedAt") {
    return normalizeDate(rawValue, field);
  }

  if (NUMERIC_FIELDS.has(field)) {
    return normalizeNumber(rawValue);
  }

  if (PERCENTAGE_FIELDS.has(field)) {
    return normalizePercentage(rawValue, numberFormat);
  }

  return normalizeText(rawValue);
}

function issueFromProblem(
  problem: NormalizationProblem,
  source: SourceProvenance,
  field: StandardField,
  rawValue: RawCellValue,
): ValidationIssue {
  return {
    code: problem.code,
    severity: problem.severity,
    scope: "field",
    message: problem.message,
    sheetName: source.sheetName,
    rowNumber: source.rowNumber,
    field,
    rawValue,
  };
}

function stringValue(
  values: Partial<Record<StandardField, string | number | null>>,
  field: StandardField,
): string | null {
  const value = values[field];
  return typeof value === "string" ? value : null;
}

function numberValue(
  values: Partial<Record<StandardField, string | number | null>>,
  field: StandardField,
): number | null {
  const value = values[field];
  return typeof value === "number" ? value : null;
}

function recordIssueReferences(
  issues: readonly ValidationIssue[],
): RecordIssueReference[] {
  return issues.map(({ code, field }) => ({ code, field }));
}

function createNormalizedRecord(
  module: LinkedInModule,
  source: SourceProvenance,
  values: Partial<Record<StandardField, string | number | null>>,
  rawValues: Partial<Record<StandardField, RawCellValue>>,
  issues: readonly ValidationIssue[],
): NormalizedLinkedInRecord {
  const common = {
    module,
    source,
    rawValues,
    isDuplicate: false,
    issueReferences: recordIssueReferences(issues),
  };

  if (module === "followers") {
    const record: FollowersRecord = {
      ...common,
      module,
      date: stringValue(values, "date"),
      totalFollowers: numberValue(values, "totalFollowers"),
      newFollowers: numberValue(values, "newFollowers"),
      organicFollowers: numberValue(values, "organicFollowers"),
      sponsoredFollowers: numberValue(values, "sponsoredFollowers"),
      demographicDimension: stringValue(values, "demographicDimension"),
      demographicValue: stringValue(values, "demographicValue"),
      demographicCount: numberValue(values, "demographicCount"),
      demographicPercentage: numberValue(
        values,
        "demographicPercentage",
      ),
    };
    return record;
  }

  if (module === "visitors") {
    const record: VisitorsRecord = {
      ...common,
      module,
      date: stringValue(values, "date"),
      pageViews: numberValue(values, "pageViews"),
      uniqueVisitors: numberValue(values, "uniqueVisitors"),
      customButtonClicks: numberValue(values, "customButtonClicks"),
      demographicDimension: stringValue(values, "demographicDimension"),
      demographicValue: stringValue(values, "demographicValue"),
      demographicCount: numberValue(values, "demographicCount"),
      demographicPercentage: numberValue(
        values,
        "demographicPercentage",
      ),
    };
    return record;
  }

  const record: ContentRecord = {
    ...common,
    module,
    contentId: stringValue(values, "contentId"),
    title: stringValue(values, "title"),
    publishedAt: stringValue(values, "publishedAt"),
    contentType: stringValue(values, "contentType"),
    impressions: numberValue(values, "impressions"),
    uniqueImpressions: numberValue(values, "uniqueImpressions"),
    clicks: numberValue(values, "clicks"),
    reactions: numberValue(values, "reactions"),
    comments: numberValue(values, "comments"),
    reposts: numberValue(values, "reposts"),
    engagementRate: numberValue(values, "engagementRate"),
    clickThroughRate: numberValue(values, "clickThroughRate"),
  };
  return record;
}

function hasAnyNumber(values: readonly (number | null)[]): boolean {
  return values.some((value) => value !== null);
}

function hasRequiredRecordValues(
  record: NormalizedLinkedInRecord,
  sheetName: string,
): boolean {
  const demographicSheet = Boolean(getDemographicDimension(sheetName));

  if (record.module === "followers") {
    if (demographicSheet || record.demographicValue) {
      return Boolean(record.demographicValue) &&
        (record.demographicCount !== null ||
          record.demographicPercentage !== null);
    }

    return Boolean(record.date) &&
      hasAnyNumber([
        record.totalFollowers,
        record.newFollowers,
        record.organicFollowers,
        record.sponsoredFollowers,
      ]);
  }

  if (record.module === "visitors") {
    if (demographicSheet || record.demographicValue) {
      return Boolean(record.demographicValue) &&
        (record.demographicCount !== null ||
          record.demographicPercentage !== null);
    }

    return Boolean(record.date) &&
      hasAnyNumber([
        record.pageViews,
        record.uniqueVisitors,
        record.customButtonClicks,
      ]);
  }

  const hasIdentity =
    !sheetName.toLocaleLowerCase("en-US").includes("post") ||
    Boolean(record.contentId || record.title);

  return (
    hasIdentity &&
    Boolean(record.publishedAt) &&
    hasAnyNumber([
      record.impressions,
      record.uniqueImpressions,
      record.clicks,
      record.reactions,
      record.comments,
      record.reposts,
      record.engagementRate,
      record.clickThroughRate,
    ])
  );
}

function parseRow(
  module: LinkedInModule,
  fileName: string,
  sheetName: string,
  sheet: XLSX.WorkSheet,
  row: readonly unknown[],
  absoluteRowIndex: number,
  mappings: readonly FieldMapping[],
): ParsedRow {
  const source: SourceProvenance = {
    module,
    fileName,
    sheetName,
    rowNumber: absoluteRowIndex + 1,
  };
  const values: Partial<
    Record<StandardField, string | number | null>
  > = {};
  const rawValues: Partial<Record<StandardField, RawCellValue>> = {};
  const issues: ValidationIssue[] = [];

  for (const mapping of mappings) {
    if (mapping.status !== "mapped" || !mapping.standardField) {
      continue;
    }

    const cell = readCell(
      sheet,
      absoluteRowIndex,
      mapping.columnIndex,
      row[mapping.columnIndex],
    );
    const field = mapping.standardField;
    rawValues[field] = cell.rawValue;

    if (cell.isFormula) {
      issues.push({
        code: "FORMULA_CELL_IGNORED",
        severity: "warning",
        scope: "field",
        message: "Formula cells were ignored; the parser does not execute workbook formulas.",
        sheetName,
        rowNumber: source.rowNumber,
        field,
      });
      values[field] = null;
      continue;
    }

    const normalized = normalizeCell(
      field,
      cell.rawValue,
      cell.numberFormat,
    );
    values[field] = normalized.value;
    issues.push(
      ...normalized.problems.map((problem) =>
        issueFromProblem(problem, source, field, cell.rawValue),
      ),
    );
  }

  const demographicDimension = getDemographicDimension(sheetName);
  if (demographicDimension && !values.demographicDimension) {
    values.demographicDimension = demographicDimension;
  }

  const record = createNormalizedRecord(
    module,
    source,
    values,
    rawValues,
    issues,
  );
  const hasErrors = issues.some((issue) => issue.severity === "error");

  return {
    record,
    issues,
    valid: !hasErrors && hasRequiredRecordValues(record, sheetName),
  };
}

function recordKey(record: NormalizedLinkedInRecord): string {
  if (record.module === "followers") {
    return JSON.stringify([
      record.date,
      record.totalFollowers,
      record.newFollowers,
      record.organicFollowers,
      record.sponsoredFollowers,
      record.demographicDimension,
      record.demographicValue,
      record.demographicCount,
      record.demographicPercentage,
    ]);
  }

  if (record.module === "visitors") {
    return JSON.stringify([
      record.date,
      record.pageViews,
      record.uniqueVisitors,
      record.customButtonClicks,
      record.demographicDimension,
      record.demographicValue,
      record.demographicCount,
      record.demographicPercentage,
    ]);
  }

  return JSON.stringify([
    record.contentId,
    record.title,
    record.publishedAt,
    record.contentType,
    record.impressions,
    record.uniqueImpressions,
    record.clicks,
    record.reactions,
    record.comments,
    record.reposts,
    record.engagementRate,
    record.clickThroughRate,
  ]);
}

function markDuplicates(
  rows: ParsedRow[],
  sheetName: string,
): { duplicateRows: number; issues: ValidationIssue[] } {
  const seen = new Map<string, number>();
  const issues: ValidationIssue[] = [];
  let duplicateRows = 0;

  rows.forEach(({ record }, index) => {
    const key = recordKey(record);
    const firstIndex = seen.get(key);

    if (firstIndex === undefined) {
      seen.set(key, index);
      return;
    }

    record.isDuplicate = true;
    rows[firstIndex].record.isDuplicate = true;
    duplicateRows += 1;
    const issue: ValidationIssue = {
      code: "DUPLICATE_ROW",
      severity: "warning",
      scope: "row",
      message: `Duplicates row ${rows[firstIndex].record.source.rowNumber}; the record was retained.`,
      sheetName,
      rowNumber: record.source.rowNumber,
    };
    issues.push(issue);
    record.issueReferences.push({ code: issue.code });
  });

  return { duplicateRows, issues };
}

function dateRange(
  records: readonly NormalizedLinkedInRecord[],
): SheetParseResult["dateRange"] {
  const dates = records
    .flatMap((record) => {
      if (record.module === "content") {
        return record.publishedAt ? [record.publishedAt] : [];
      }
      return record.date ? [record.date] : [];
    })
    .sort();

  if (dates.length === 0) {
    return null;
  }

  return { start: dates[0], end: dates[dates.length - 1] };
}

function hasMoreRowsThanLimit(sheet: XLSX.WorkSheet): boolean {
  const fullReference = sheet["!fullref"];
  const reference =
    typeof fullReference === "string" ? fullReference : sheet["!ref"];

  if (typeof reference !== "string") {
    return false;
  }

  const range = XLSX.utils.decode_range(reference);
  return range.e.r - range.s.r + 1 > MAX_ROWS_PER_SHEET + MAX_HEADER_SCAN_ROWS;
}

function parseSheet(
  sheetName: string,
  sheet: XLSX.WorkSheet,
  input: Omit<ParseSpreadsheetInput, "bytes" | "format" | "mimeType">,
): SheetParseResult {
  const { rows, startRow } = worksheetRows(sheet);

  if (rows.length === 0) {
    return emptySheetResult(sheetName, "EMPTY_SHEET", "The sheet contains no parseable data.");
  }

  const located = locateHeaderRow(
    rows,
    sheetName,
    input.fileName,
    MAX_HEADER_SCAN_ROWS,
    input.moduleOverride,
  );

  if (!located) {
    return emptySheetResult(
      sheetName,
      "NO_HEADER_FOUND",
      "No reliable header was found. Select a module or check the export format.",
    );
  }

  const detection = located.detection;
  const detectedModule = detection.detectedModule;
  const issues: ValidationIssue[] = [];

  if (!detectedModule) {
    issues.push({
      code: "UNRECOGNIZED_MODULE",
      severity: "error",
      scope: "sheet",
      sheetName,
      message: "The sheet could not be classified as Followers, Visitors, or Content.",
    });
  } else if (
    input.expectedModule &&
    !input.moduleOverride &&
    detectedModule !== input.expectedModule
  ) {
    issues.push({
      code: "MODULE_MISMATCH",
      severity: "error",
      scope: "sheet",
      sheetName,
      message: `Recognized as ${detectedModule}, which differs from upload slot ${input.expectedModule}. Confirm the assignment.`,
    });
  } else if (detection.requiresConfirmation) {
    issues.push({
      code: "UNRECOGNIZED_MODULE",
      severity: "warning",
      scope: "sheet",
      sheetName,
      message: "Module recognition confidence is low and requires confirmation.",
    });
  }

  if (!detectedModule) {
    const dataRows = rows
      .slice(located.rowIndex + 1)
      .filter((row) => row.some((value) => !isBlankValue(value)));
    return {
      sheetName,
      headerRow: startRow + located.rowIndex + 1,
      detection,
      mappings: [],
      unmappedFields: located.headers.filter(Boolean),
      conflictFields: [],
      missingCriticalFields: [],
      totalRows: dataRows.length,
      validRows: 0,
      duplicateRows: 0,
      dateRange: null,
      records: [],
      preview: [],
      issues,
      canProceed: false,
    };
  }

  const mappings = buildFieldMappings(
    detectedModule,
    sheetName,
    located.headers,
    input.mappingOverrides,
  );
  const conflicts = mappings.filter((mapping) => mapping.status === "conflict");
  const unmapped = mappings.filter((mapping) => mapping.status === "unmapped");
  const missingCriticalFields = getMissingCriticalFields(
    detectedModule,
    sheetName,
    mappings,
  );

  issues.push(
    ...conflicts.map(
      (mapping): ValidationIssue => ({
        code: "CONFLICTING_FIELD_MAPPING",
        severity: "warning",
        scope: "field",
        sheetName,
        message: `Field "${mapping.rawHeader}" has a mapping conflict that requires confirmation.`,
      }),
    ),
  );

  if (unmapped.length > 0) {
    issues.push({
      code: "FIELD_NOT_MAPPED",
      severity: "info",
      scope: "sheet",
      sheetName,
      message: `${unmapped.length} fields are unmapped and retained in the recognition summary only.`,
    });
  }

  issues.push(
    ...missingCriticalFields.map(
      (field): ValidationIssue => ({
        code: "MISSING_CRITICAL_FIELD",
        severity: "error",
        scope: "field",
        sheetName,
        field,
        message: `Required field is missing: ${FIELD_LABELS[field]}.`,
      }),
    ),
  );

  if (hasMoreRowsThanLimit(sheet)) {
    issues.push({
      code: "ROW_LIMIT_REACHED",
      severity: "warning",
      scope: "sheet",
      sheetName,
      message: `Only the first ${MAX_ROWS_PER_SHEET.toLocaleString("en-US")} data rows were parsed.`,
    });
  }

  const parsedRows: ParsedRow[] = [];
  const firstDataRowIndex = located.rowIndex + 1;
  const lastDataRowIndex = Math.min(
    rows.length,
    firstDataRowIndex + MAX_ROWS_PER_SHEET,
  );

  for (
    let relativeRowIndex = firstDataRowIndex;
    relativeRowIndex < lastDataRowIndex;
    relativeRowIndex += 1
  ) {
    const row = rows[relativeRowIndex];

    if (!row || row.every(isBlankValue)) {
      continue;
    }

    const absoluteRowIndex = startRow + relativeRowIndex;
    const parsed = parseRow(
      detectedModule,
      input.fileName,
      sheetName,
      sheet,
      row,
      absoluteRowIndex,
      mappings,
    );
    parsedRows.push(parsed);
    issues.push(...parsed.issues);
  }

  const duplicates = markDuplicates(parsedRows, sheetName);
  issues.push(...duplicates.issues);
  const records = parsedRows.map(({ record }) => record);
  const hasStructuralErrors = issues.some(
    (issue) =>
      issue.severity === "error" &&
      (issue.scope === "sheet" || issue.rowNumber === undefined),
  );
  const validRows = parsedRows.filter(({ valid }) => valid).length;

  return {
    sheetName,
    headerRow: startRow + located.rowIndex + 1,
    detection,
    mappings,
    unmappedFields: unmapped.map(({ rawHeader }) => rawHeader),
    conflictFields: conflicts.map(({ rawHeader }) => rawHeader),
    missingCriticalFields,
    totalRows: parsedRows.length,
    validRows,
    duplicateRows: duplicates.duplicateRows,
    dateRange: dateRange(records),
    records,
    preview: records.slice(0, PREVIEW_ROW_COUNT),
    issues,
    canProceed:
      validRows > 0 &&
      !hasStructuralErrors &&
      !detection.requiresConfirmation,
  };
}

export function parseSpreadsheetBytes(
  input: ParseSpreadsheetInput,
): FileParseResult {
  if (input.bytes.byteLength === 0) {
    throw parseError("EMPTY_FILE", "The file is empty. Export it again and retry.");
  }

  let workbook: XLSX.WorkBook;

  try {
    workbook = XLSX.read(input.bytes, {
      type: "array",
      raw: true,
      cellDates: true,
      cellFormula: true,
      cellHTML: false,
      cellNF: true,
      cellText: false,
      cellStyles: false,
      bookVBA: false,
      bookDeps: false,
      bookFiles: false,
      sheetRows: MAX_ROWS_PER_SHEET + MAX_HEADER_SCAN_ROWS,
      UTC: true,
      WTF: false,
    });
  } catch (reason) {
    throw new SpreadsheetParseException(getSafeParseError(reason));
  }

  if (workbook.SheetNames.length > MAX_SHEETS_PER_WORKBOOK) {
    throw parseError(
      "TOO_MANY_SHEETS",
      `The workbook exceeds ${MAX_SHEETS_PER_WORKBOOK} sheets, so parsing stopped.`,
      false,
    );
  }

  const sheets = workbook.SheetNames.map((sheetName) => {
    const sheet = workbook.Sheets[sheetName];
    return sheet
      ? parseSheet(sheetName, sheet, {
          fileName: input.fileName,
          expectedModule: input.expectedModule,
          moduleOverride: input.moduleOverride,
          mappingOverrides: input.mappingOverrides,
        })
      : emptySheetResult(
          sheetName,
          "EMPTY_SHEET",
          "The sheet content could not be read.",
        );
  });
  const detectedModules = [
    ...new Set(
      sheets.flatMap(({ detection }) =>
        detection.detectedModule ? [detection.detectedModule] : [],
      ),
    ),
  ];
  const issues = sheets.flatMap((sheet) => sheet.issues);

  return {
    success: true,
    file: {
      name: input.fileName,
      size: input.bytes.byteLength,
      mimeType: input.mimeType,
      format: input.format,
    },
    workbook: {
      sheetCount: sheets.length,
      sheets,
    },
    detectedModules,
    totalRows: sheets.reduce((sum, sheet) => sum + sheet.totalRows, 0),
    validRows: sheets.reduce((sum, sheet) => sum + sheet.validRows, 0),
    issues,
    canProceed: sheets.some((sheet) => sheet.canProceed),
    parsedAt: new Date().toISOString(),
    parserMode: "server",
  };
}
