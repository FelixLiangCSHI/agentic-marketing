export const LINKEDIN_MODULES = ["followers", "visitors", "content"] as const;

export type LinkedInModule = (typeof LINKEDIN_MODULES)[number];

export type SpreadsheetFormat = "csv" | "xls" | "xlsx";

export type ConfidenceLevel = "high" | "medium" | "low";

export type IssueSeverity = "info" | "warning" | "error";

export type IssueScope = "file" | "sheet" | "row" | "field";

export type RawCellValue = string | number | boolean | null;

export type FollowersField =
  | "date"
  | "totalFollowers"
  | "newFollowers"
  | "organicFollowers"
  | "sponsoredFollowers"
  | "demographicDimension"
  | "demographicValue"
  | "demographicCount"
  | "demographicPercentage";

export type VisitorsField =
  | "date"
  | "pageViews"
  | "uniqueVisitors"
  | "customButtonClicks"
  | "demographicDimension"
  | "demographicValue"
  | "demographicCount"
  | "demographicPercentage";

export type ContentField =
  | "contentId"
  | "title"
  | "publishedAt"
  | "contentType"
  | "impressions"
  | "uniqueImpressions"
  | "clicks"
  | "reactions"
  | "comments"
  | "reposts"
  | "engagementRate"
  | "clickThroughRate";

export type StandardField = FollowersField | VisitorsField | ContentField;

export interface SourceProvenance {
  module: LinkedInModule;
  fileName: string;
  sheetName: string;
  rowNumber: number;
}

export interface RecordIssueReference {
  code: ValidationIssueCode;
  field?: StandardField;
}

interface NormalizedRecordBase<
  TModule extends LinkedInModule,
  TField extends StandardField,
> {
  module: TModule;
  source: SourceProvenance;
  rawValues: Partial<Record<TField, RawCellValue>>;
  isDuplicate: boolean;
  issueReferences: RecordIssueReference[];
}

export interface FollowersRecord
  extends NormalizedRecordBase<"followers", FollowersField> {
  date: string | null;
  totalFollowers: number | null;
  newFollowers: number | null;
  organicFollowers: number | null;
  sponsoredFollowers: number | null;
  demographicDimension: string | null;
  demographicValue: string | null;
  demographicCount: number | null;
  demographicPercentage: number | null;
}

export interface VisitorsRecord
  extends NormalizedRecordBase<"visitors", VisitorsField> {
  date: string | null;
  pageViews: number | null;
  uniqueVisitors: number | null;
  customButtonClicks: number | null;
  demographicDimension: string | null;
  demographicValue: string | null;
  demographicCount: number | null;
  demographicPercentage: number | null;
}

export interface ContentRecord
  extends NormalizedRecordBase<"content", ContentField> {
  contentId: string | null;
  title: string | null;
  publishedAt: string | null;
  contentType: string | null;
  impressions: number | null;
  uniqueImpressions: number | null;
  clicks: number | null;
  reactions: number | null;
  comments: number | null;
  reposts: number | null;
  engagementRate: number | null;
  clickThroughRate: number | null;
}

export type NormalizedLinkedInRecord =
  | FollowersRecord
  | VisitorsRecord
  | ContentRecord;

export type ValidationIssueCode =
  | "AMBIGUOUS_DATE"
  | "CONFLICTING_FIELD_MAPPING"
  | "DUPLICATE_MODULE"
  | "DUPLICATE_ROW"
  | "EMPTY_SHEET"
  | "FIELD_NOT_MAPPED"
  | "FORMULA_CELL_IGNORED"
  | "FORMULA_LIKE_TEXT"
  | "INVALID_DATE"
  | "INVALID_NUMBER"
  | "MISSING_CRITICAL_FIELD"
  | "MODULE_MISMATCH"
  | "NEGATIVE_VALUE"
  | "NO_HEADER_FOUND"
  | "PERCENTAGE_OUT_OF_RANGE"
  | "PERCENTAGE_SCALE_INFERRED"
  | "ROW_LIMIT_REACHED"
  | "UNREASONABLE_DATE"
  | "UNRECOGNIZED_MODULE";

export interface ValidationIssue {
  code: ValidationIssueCode;
  severity: IssueSeverity;
  scope: IssueScope;
  message: string;
  sheetName?: string;
  rowNumber?: number;
  field?: StandardField;
  rawValue?: RawCellValue;
}

export interface FieldMapping {
  rawHeader: string;
  columnIndex: number;
  standardField: StandardField | null;
  status: "mapped" | "unmapped" | "conflict";
  confidence: ConfidenceLevel;
  reason: string;
  alternatives: StandardField[];
}

export interface ModuleCandidate {
  module: LinkedInModule;
  score: number;
  matchedFields: StandardField[];
  reasons: string[];
}

export interface ModuleDetection {
  detectedModule: LinkedInModule | null;
  confidence: ConfidenceLevel;
  requiresConfirmation: boolean;
  candidates: ModuleCandidate[];
  reasons: string[];
}

export interface SheetParseResult {
  sheetName: string;
  headerRow: number | null;
  detection: ModuleDetection;
  mappings: FieldMapping[];
  unmappedFields: string[];
  conflictFields: string[];
  missingCriticalFields: StandardField[];
  totalRows: number;
  validRows: number;
  duplicateRows: number;
  dateRange: {
    start: string;
    end: string;
  } | null;
  records: NormalizedLinkedInRecord[];
  preview: NormalizedLinkedInRecord[];
  issues: ValidationIssue[];
  canProceed: boolean;
}

export interface FileParseResult {
  success: true;
  file: {
    name: string;
    size: number;
    mimeType: string;
    format: SpreadsheetFormat;
  };
  workbook: {
    sheetCount: number;
    sheets: SheetParseResult[];
  };
  detectedModules: LinkedInModule[];
  totalRows: number;
  validRows: number;
  issues: ValidationIssue[];
  canProceed: boolean;
  parsedAt: string;
  parserMode: "server" | "synthetic-mock";
}

export type ParseErrorCode =
  | "CORRUPT_FILE"
  | "EMPTY_FILE"
  | "ENCRYPTED_WORKBOOK"
  | "FILE_SIGNATURE_MISMATCH"
  | "INVALID_MODULE_OVERRIDE"
  | "INVALID_MAPPING_OVERRIDE"
  | "INVALID_MIME_TYPE"
  | "MISSING_FILE"
  | "PARSE_FAILED"
  | "REQUEST_TOO_LARGE"
  | "TOO_MANY_SHEETS"
  | "UNSUPPORTED_FILE_TYPE";

export interface ParseError {
  code: ParseErrorCode;
  message: string;
  retryable: boolean;
}

export interface ParseFailureResult {
  success: false;
  error: ParseError;
}

export type ParseApiResponse = FileParseResult | ParseFailureResult;

export type MappingOverrides = Record<string, StandardField | null>;

export interface ModuleAssignment {
  slot: LinkedInModule;
  detectedModule: LinkedInModule | null;
  confirmed: boolean;
}
