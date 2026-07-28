import {
  confirmActionPlan,
  generateActionPlan,
  normalizeActionPlan,
  reviseActionPlanSchedule,
  reviseCalendarItem,
  type ActionPlanAgentError,
} from "@/agents/action-plan-agent";
import { answerProjectQuestion } from "@/agents/evidence-chat-agent";
import { generateEvidenceStrategyBundle } from "@/agents/evidence-strategy-agent";
import {
  analysisInputFromParseResults,
  generateAnalysisSnapshot,
} from "@/analysis/snapshot-engine";
import {
  sanitizeUploadFileName,
  validateFileEnvelope,
  validateServerFile,
} from "@/data-processing/file-validation";
import type {
  ActionPlan,
  ActionPlanPreferences,
} from "@/domain/action-plan";
import type { AnalysisSnapshot } from "@/domain/analysis";
import {
  BUFFER_SUPPORTED_CHANNELS,
  type BufferDateRange,
  type BufferExportRecord,
  type BufferHandoffOptions,
  type BufferSupportedChannel,
} from "@/domain/buffer-handoff";
import type {
  FileParseResult,
  LinkedInModule,
  ParseError,
  ValidationIssue,
} from "@/domain/linkedin";
import { LINKEDIN_MODULES } from "@/domain/linkedin";
import type {
  BusinessGoal,
  EvidenceStrategyBundle,
} from "@/domain/strategy";
import {
  BufferExportError,
  createBufferHandoffExport,
  validateBufferHandoff,
} from "@/exports/buffer-export";
import {
  createReportExportArtifacts,
  type ReportExportInput,
} from "@/exports/report-exports";
import { createSyntheticParseResults } from "@/server/parsing/synthetic-results";
import {
  getSafeParseError,
  parseSpreadsheetBytes,
} from "@/server/parsing/spreadsheet-parser";

export const BRIDGE_PROTOCOL_VERSION = "1.0";
export const MAX_BRIDGE_REQUEST_BYTES = 43 * 1024 * 1024;

export type BridgeOperation =
  | "health"
  | "analyze_synthetic"
  | "analyze_uploads"
  | "create_plan"
  | "answer_question"
  | "revise_calendar_item"
  | "revise_schedule"
  | "confirm_plan"
  | "preview_buffer_handoff"
  | "export_buffer_handoff"
  | "export_project";

export type BridgeErrorCode =
  | ParseError["code"]
  | "AI_RATE_LIMIT"
  | "AI_TIMEOUT"
  | "BLOCKING_DATA_QUALITY"
  | "BUFFER_EXPORT_VALIDATION_FAILED"
  | "BUFFER_NO_EXPORTABLE_CONTENT"
  | "BUFFER_WARNING_CONFIRMATION_REQUIRED"
  | "BRIDGE_UNAVAILABLE"
  | "DUPLICATE_MODULE"
  | "DUPLICATE_REQUEST"
  | "EXPORT_FAILED"
  | "GENERATION_CANCELLED"
  | "INTERNAL_ERROR"
  | "INVALID_MODEL_OUTPUT"
  | "INVALID_REQUEST"
  | "MODULE_MISMATCH"
  | "NETWORK_ERROR"
  | "PLAN_VALIDATION_FAILED"
  | "STRATEGY_APPROVAL_REQUIRED"
  | "UNSUPPORTED_OPERATION";

export interface BridgeError {
  code: BridgeErrorCode;
  message: string;
  retryable: boolean;
  preserveProjectData: boolean;
  nextAction: string;
}

export type BridgeResponse =
  | {
      protocolVersion: typeof BRIDGE_PROTOCOL_VERSION;
      requestId: string;
      success: true;
      data: unknown;
    }
  | {
      protocolVersion: typeof BRIDGE_PROTOCOL_VERSION;
      requestId: string;
      success: false;
      error: BridgeError;
    };

interface BridgeRequest {
  requestId: string;
  operation: BridgeOperation;
  payload: Record<string, unknown>;
}

interface UploadedFilePayload {
  slot: LinkedInModule;
  name: string;
  mimeType: string;
  size: number;
  base64: string;
}

class BridgeOperationError extends Error {
  constructor(public readonly details: BridgeError) {
    super(details.message);
    this.name = "BridgeOperationError";
  }
}

function operationError(
  code: BridgeErrorCode,
  message: string,
  options: Partial<Omit<BridgeError, "code" | "message">> = {},
): BridgeOperationError {
  return new BridgeOperationError({
    code,
    message,
    retryable: options.retryable ?? true,
    preserveProjectData: options.preserveProjectData ?? true,
    nextAction: options.nextAction ?? "Correct the input and retry this stage.",
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredRecord(
  value: unknown,
  fieldName: string,
): Record<string, unknown> {
  if (!isRecord(value)) {
    throw operationError("INVALID_REQUEST", `${fieldName} is missing or invalid.`, {
      retryable: false,
    });
  }
  return value;
}

function requiredString(
  value: unknown,
  fieldName: string,
  maxLength = 2_000,
): string {
  if (
    typeof value !== "string" ||
    !value.trim() ||
    value.length > maxLength
  ) {
    throw operationError("INVALID_REQUEST", `${fieldName} is missing or has an invalid length.`, {
      retryable: false,
    });
  }
  return value;
}

function isLinkedInModule(value: unknown): value is LinkedInModule {
  return (
    typeof value === "string" &&
    LINKEDIN_MODULES.includes(value as LinkedInModule)
  );
}

function parseRequest(value: unknown): BridgeRequest {
  const request = requiredRecord(value, "request");
  const requestId = requiredString(request.requestId, "requestId", 100);
  const operation = requiredString(request.operation, "operation", 50);
  const allowed: readonly string[] = [
    "health",
    "analyze_synthetic",
    "analyze_uploads",
    "create_plan",
    "answer_question",
    "revise_calendar_item",
    "revise_schedule",
    "confirm_plan",
    "preview_buffer_handoff",
    "export_buffer_handoff",
    "export_project",
  ];
  if (!allowed.includes(operation)) {
    throw operationError(
      "UNSUPPORTED_OPERATION",
      "The bridge does not support this operation.",
      { retryable: false },
    );
  }

  return {
    requestId,
    operation: operation as BridgeOperation,
    payload: isRecord(request.payload) ? request.payload : {},
  };
}

function parseUploadedFile(value: unknown): UploadedFilePayload {
  const file = requiredRecord(value, "files[]");
  if (!isLinkedInModule(file.slot)) {
    throw operationError("INVALID_REQUEST", "The upload module slot is invalid.", {
      retryable: false,
    });
  }
  const size = file.size;
  if (!Number.isInteger(size) || (size as number) < 0) {
    throw operationError("INVALID_REQUEST", "The upload size is invalid.", {
      retryable: false,
    });
  }

  return {
    slot: file.slot,
    name: requiredString(file.name, "file.name", 300),
    mimeType:
      typeof file.mimeType === "string" ? file.mimeType.slice(0, 200) : "",
    size: size as number,
    base64: requiredString(file.base64, "file.base64", 14_100_000),
  };
}

function decodeBase64(value: string, declaredSize: number): Uint8Array {
  const compact = value.replace(/\s/g, "");
  if (
    compact.length % 4 !== 0 ||
    !/^[A-Za-z0-9+/]*={0,2}$/.test(compact)
  ) {
    throw operationError("INVALID_REQUEST", "The upload encoding is invalid.", {
      retryable: false,
    });
  }
  const bytes = new Uint8Array(Buffer.from(compact, "base64"));
  if (bytes.length !== declaredSize) {
    bytes.fill(0);
    throw operationError(
      "INVALID_REQUEST",
      "The upload size does not match its content, so processing stopped.",
      { retryable: false },
    );
  }
  return bytes;
}

function issueSummary(issue: ValidationIssue) {
  return {
    code: issue.code,
    severity: issue.severity,
    scope: issue.scope,
    message: issue.message,
    sheetName: issue.sheetName,
    rowNumber: issue.rowNumber,
    field: issue.field,
  };
}

function previewRecord(record: FileParseResult["workbook"]["sheets"][number]["preview"][number]) {
  const fields = Object.fromEntries(
    Object.entries(record).filter(
      ([key]) =>
        key !== "rawValues" && key !== "issueReferences" && key !== "source",
    ),
  );
  return {
    ...fields,
    source: {
      module: record.source.module,
      sheetName: record.source.sheetName,
      rowNumber: record.source.rowNumber,
    },
  };
}

function summarizeParseResult(slot: LinkedInModule, result: FileParseResult) {
  return {
    slot,
    file: result.file,
    detectedModules: result.detectedModules,
    totalRows: result.totalRows,
    validRows: result.validRows,
    issues: result.issues.map(issueSummary),
    canProceed: result.canProceed,
    parserMode: result.parserMode,
    sheets: result.workbook.sheets.map((sheet) => ({
      sheetName: sheet.sheetName,
      headerRow: sheet.headerRow,
      detection: sheet.detection,
      mappings: sheet.mappings,
      unmappedFields: sheet.unmappedFields,
      conflictFields: sheet.conflictFields,
      missingCriticalFields: sheet.missingCriticalFields,
      totalRows: sheet.totalRows,
      validRows: sheet.validRows,
      duplicateRows: sheet.duplicateRows,
      dateRange: sheet.dateRange,
      issues: sheet.issues.map(issueSummary),
      canProceed: sheet.canProceed,
      standardizedPreview: sheet.preview.slice(0, 5).map(previewRecord),
    })),
  };
}

function emptyStrategyBundle(
  snapshot: AnalysisSnapshot,
  generatedAt: Date,
): EvidenceStrategyBundle {
  return {
    promptVersion: "evidence-strategy-v1.0",
    snapshotId: snapshot.snapshotId,
    generatedAt: generatedAt.toISOString(),
    insights: [],
    strategies: [],
  };
}

function buildAnalysisProject(
  results: Partial<Record<LinkedInModule, FileParseResult>>,
  inputMode: "uploaded" | "mock",
  now: Date,
) {
  const snapshot = generateAnalysisSnapshot(
    analysisInputFromParseResults(results, inputMode),
  );
  const strategyBundle = snapshot.canEnterInsights
    ? generateEvidenceStrategyBundle(snapshot, now)
    : emptyStrategyBundle(snapshot, now);

  return {
    mode: inputMode,
    analysisStatus: snapshot.canEnterInsights ? "ready" : "blocked",
    generatedAt: now.toISOString(),
    parseSummaries: LINKEDIN_MODULES.flatMap((slot) => {
      const result = results[slot];
      return result ? [summarizeParseResult(slot, result)] : [];
    }),
    snapshot,
    strategyBundle,
    privacy: {
      originalFilesPersisted: false,
      bridgeProcessLifetime: "single-request",
      rawCellsReturned: false,
    },
  };
}

function parseUploadedResults(
  filesValue: unknown,
): Partial<Record<LinkedInModule, FileParseResult>> {
  if (!Array.isArray(filesValue) || filesValue.length === 0) {
    throw operationError("MISSING_FILE", "No uploaded files are available for analysis.", {
      nextAction: "Select at least one Followers, Visitors, or Content file.",
    });
  }
  if (filesValue.length > LINKEDIN_MODULES.length) {
    throw operationError("INVALID_REQUEST", "A maximum of three module files can be uploaded.", {
      retryable: false,
    });
  }

  const files = filesValue.map(parseUploadedFile);
  if (new Set(files.map((file) => file.slot)).size !== files.length) {
    throw operationError(
      "DUPLICATE_MODULE",
      "The same module was uploaded more than once. Retain one file and retry.",
      { nextAction: "Remove duplicate module files, then retry intake." },
    );
  }

  const results: Partial<Record<LinkedInModule, FileParseResult>> = {};
  const detectedOwners = new Map<LinkedInModule, LinkedInModule>();

  for (const file of files) {
    const fileName = sanitizeUploadFileName(file.name);
    const envelope = validateFileEnvelope({
      name: fileName,
      size: file.size,
      type: file.mimeType,
    });
    if (!envelope.ok) {
      throw operationError(
        envelope.error.code,
        envelope.error.message,
        envelope.error,
      );
    }

    let bytes: Uint8Array | null = decodeBase64(file.base64, file.size);
    try {
      const validation = validateServerFile(
        {
          name: fileName,
          size: file.size,
          type: file.mimeType,
        },
        bytes,
      );
      if (!validation.ok) {
        throw operationError(
          validation.error.code,
          validation.error.message,
          validation.error,
        );
      }
      const result = parseSpreadsheetBytes({
        bytes,
        fileName,
        mimeType: file.mimeType,
        format: validation.format,
        expectedModule: file.slot,
      });

      for (const detectedModule of result.detectedModules) {
        const existingSlot = detectedOwners.get(detectedModule);
        if (existingSlot && existingSlot !== file.slot) {
          throw operationError(
            "DUPLICATE_MODULE",
            `${detectedModule} appears in multiple uploaded files.`,
            { nextAction: "Check file content and module selection, remove duplicates, and retry." },
          );
        }
        detectedOwners.set(detectedModule, file.slot);
      }
      results[file.slot] = result;
    } catch (reason) {
      if (reason instanceof BridgeOperationError) {
        throw reason;
      }
      const error = getSafeParseError(reason);
      throw operationError(error.code, error.message, error);
    } finally {
      bytes?.fill(0);
      bytes = null;
    }
  }

  return results;
}

function dateFromPayload(value: unknown): Date {
  if (typeof value !== "string") {
    return new Date();
  }
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    throw operationError("INVALID_REQUEST", "now is not a valid time.", {
      retryable: false,
    });
  }
  return date;
}

function snapshotFromPayload(value: unknown): AnalysisSnapshot {
  const snapshot = requiredRecord(value, "snapshot");
  requiredString(snapshot.snapshotId, "snapshot.snapshotId", 200);
  if (snapshot.snapshotVersion !== "1.0" || !isRecord(snapshot.metrics)) {
    throw operationError("INVALID_REQUEST", "The snapshot structure is invalid.", {
      retryable: false,
    });
  }
  return snapshot as unknown as AnalysisSnapshot;
}

function bundleFromPayload(
  value: unknown,
  snapshot: AnalysisSnapshot,
): EvidenceStrategyBundle {
  const bundle = requiredRecord(value, "strategyBundle");
  if (
    bundle.snapshotId !== snapshot.snapshotId ||
    !Array.isArray(bundle.insights) ||
    !Array.isArray(bundle.strategies)
  ) {
    throw operationError("INVALID_REQUEST", "Insight and snapshot references are inconsistent.", {
      retryable: false,
    });
  }
  return bundle as unknown as EvidenceStrategyBundle;
}

function planFromPayload(value: unknown): ActionPlan;
function planFromPayload(value: unknown, allowNull: true): ActionPlan | null;
function planFromPayload(
  value: unknown,
  allowNull = false,
): ActionPlan | null {
  if (value === null && allowNull) {
    return null;
  }
  const plan = normalizeActionPlan(value);
  if (!plan) {
    throw operationError("INVALID_REQUEST", "The action plan structure is invalid.", {
      retryable: false,
    });
  }
  return plan;
}

function boundedString(
  value: unknown,
  fieldName: string,
  maxLength: number,
  allowEmpty = false,
): string {
  if (
    typeof value !== "string" ||
    value.length > maxLength ||
    (!allowEmpty && !value.trim())
  ) {
    throw operationError("INVALID_REQUEST", `${fieldName} has an invalid format or length.`, {
      retryable: false,
    });
  }
  return value;
}

function nullableString(
  value: unknown,
  fieldName: string,
  maxLength: number,
): string | null {
  if (value === null) {
    return null;
  }
  return boundedString(value, fieldName, maxLength, true);
}

function stringArray(
  value: unknown,
  fieldName: string,
  maxItems: number,
  maxItemLength: number,
): string[] {
  if (
    !Array.isArray(value) ||
    value.length > maxItems ||
    !value.every(
      (item) => typeof item === "string" && item.length <= maxItemLength,
    )
  ) {
    throw operationError("INVALID_REQUEST", `${fieldName} has an invalid format or count.`, {
      retryable: false,
    });
  }
  return [...new Set(value)];
}

function isBufferChannel(value: string): value is BufferSupportedChannel {
  return BUFFER_SUPPORTED_CHANNELS.includes(value as BufferSupportedChannel);
}

function channelArray(value: unknown, fieldName: string): BufferSupportedChannel[] {
  const channels = stringArray(
    value,
    fieldName,
    BUFFER_SUPPORTED_CHANNELS.length,
    100,
  );
  if (!channels.every(isBufferChannel)) {
    throw operationError("INVALID_REQUEST", `${fieldName} contains an unsupported channel.`, {
      retryable: false,
    });
  }
  return channels;
}

function dateRangeFromPayload(value: unknown, fieldName: string): BufferDateRange {
  const range = requiredRecord(value, fieldName);
  return {
    start: boundedString(range.start, `${fieldName}.start`, 10),
    end: boundedString(range.end, `${fieldName}.end`, 10),
  };
}

function bufferExportRecordFromPayload(value: unknown): BufferExportRecord {
  const record = requiredRecord(value, "previousExports[]");
  if (
    record.status !== "completed" &&
    record.status !== "partial" &&
    record.status !== "failed"
  ) {
    throw operationError("INVALID_REQUEST", "The export record status is invalid.", {
      retryable: false,
    });
  }
  return {
    exportId: boundedString(record.exportId, "exportId", 300),
    generatedAt: boundedString(record.generatedAt, "generatedAt", 100),
    dateRange: dateRangeFromPayload(record.dateRange, "dateRange"),
    timeZone: boundedString(record.timeZone, "timeZone", 100),
    channels: channelArray(record.channels, "channels"),
    exportedItemIds: stringArray(
      record.exportedItemIds,
      "exportedItemIds",
      500,
      300,
    ),
    skippedItemIds: stringArray(
      record.skippedItemIds,
      "skippedItemIds",
      500,
      300,
    ),
    fileNames: stringArray(record.fileNames, "fileNames", 20, 300),
    status: record.status,
  };
}

function bufferOptionsFromPayload(value: unknown): BufferHandoffOptions {
  const options = requiredRecord(value, "handoff");
  if (
    !Array.isArray(options.previousExports) ||
    options.previousExports.length > 100
  ) {
    throw operationError("INVALID_REQUEST", "previousExports has an invalid format or count.", {
      retryable: false,
    });
  }
  return {
    dateRange: dateRangeFromPayload(options.dateRange, "handoff.dateRange"),
    timeZone: boundedString(options.timeZone, "handoff.timeZone", 100),
    channels: channelArray(options.channels, "handoff.channels"),
    selectedItemIds: stringArray(
      options.selectedItemIds,
      "handoff.selectedItemIds",
      500,
      300,
    ),
    warningsAcknowledged: options.warningsAcknowledged === true,
    previousExports: options.previousExports.map(bufferExportRecordFromPayload),
  };
}

function preferencesFromPayload(value: unknown): ActionPlanPreferences {
  const preferences = requiredRecord(value, "preferences");
  return preferences as unknown as ActionPlanPreferences;
}

function goalFromPayload(value: unknown): BusinessGoal {
  const goal = requiredRecord(value, "businessGoal");
  requiredString(goal.goalId, "businessGoal.goalId", 200);
  requiredString(goal.statement, "businessGoal.statement", 1_000);
  if (goal.confirmed !== true) {
    throw operationError(
      "PLAN_VALIDATION_FAILED",
      "Confirm the business goal first.",
      { nextAction: "Confirm the business goal, then retry plan preparation." },
    );
  }
  return goal as unknown as BusinessGoal;
}

function actionPlanError(reason: ActionPlanAgentError): BridgeOperationError {
  if (reason.code === "GENERATION_CANCELLED") {
    return operationError("GENERATION_CANCELLED", "Plan preparation was cancelled.", {
      nextAction: "Current uploads and the snapshot are retained; retry plan preparation.",
    });
  }

  const approvalIssue = reason.issues.some((issue) =>
    [
      "INSIGHT_NOT_APPROVED",
      "STRATEGY_NOT_APPROVED",
      "STRATEGY_INSIGHT_NOT_APPROVED",
    ].includes(issue.code),
  );
  return operationError(
    approvalIssue ? "STRATEGY_APPROVAL_REQUIRED" : "PLAN_VALIDATION_FAILED",
    reason.issues[0]?.message ?? "Action plan structure validation failed.",
    {
      nextAction: approvalIssue
        ? "Approve at least one evidence-backed insight and related strategy, then retry."
        : "Correct plan settings and retry without uploading files again.",
    },
  );
}

function codeFromUnknown(reason: unknown): string | number | undefined {
  if (!isRecord(reason)) {
    return undefined;
  }
  return typeof reason.code === "string" || typeof reason.code === "number"
    ? reason.code
    : typeof reason.status === "number"
      ? reason.status
      : undefined;
}

export function bridgeErrorFromUnknown(reason: unknown): BridgeError {
  if (reason instanceof BridgeOperationError) {
    return reason.details;
  }
  if (
    reason instanceof Error &&
    reason.name === "ActionPlanAgentError" &&
    "code" in reason &&
    "issues" in reason
  ) {
    return actionPlanError(reason as ActionPlanAgentError).details;
  }
  if (reason instanceof BufferExportError) {
    const code: BridgeErrorCode =
      reason.code === "WARNING_ACKNOWLEDGEMENT_REQUIRED"
        ? "BUFFER_WARNING_CONFIRMATION_REQUIRED"
        : reason.code === "NO_EXPORTABLE_CONTENT"
          ? "BUFFER_NO_EXPORTABLE_CONTENT"
          : "BUFFER_EXPORT_VALIDATION_FAILED";
    return operationError(code, reason.message, {
      nextAction:
        reason.code === "WARNING_ACKNOWLEDGEMENT_REQUIRED"
          ? "Review and acknowledge warnings, then retry; the current plan is retained."
          : "Correct the relevant content or range and retry without reanalysis or upload.",
    }).details;
  }

  const code = codeFromUnknown(reason);
  if (code === "REQUEST_TOO_LARGE") {
    return operationError(
      "REQUEST_TOO_LARGE",
      "The bridge request exceeds the size limit, so processing stopped.",
      { nextAction: "Reduce the file count or select smaller files, then retry." },
    ).details;
  }
  if (code === "INVALID_REQUEST") {
    return operationError("INVALID_REQUEST", "The bridge request format is invalid.", {
      retryable: false,
      nextAction: "Refresh and retry; existing uploads are not written to disk.",
    }).details;
  }
  if (code === 429 || code === "RATE_LIMITED") {
    return operationError(
      "AI_RATE_LIMIT",
      "The recommendation service is temporarily rate limited.",
      { nextAction: "Current data is retained; retry this stage later." },
    ).details;
  }
  if (
    code === "ETIMEDOUT" ||
    code === "TIMEOUT" ||
    (reason instanceof Error && reason.name === "TimeoutError")
  ) {
    return operationError("AI_TIMEOUT", "The recommendation service timed out.", {
      nextAction: "Current data is retained; retry without uploading again.",
    }).details;
  }
  if (code === "INVALID_MODEL_OUTPUT") {
    return operationError(
      "INVALID_MODEL_OUTPUT",
      "The prepared output failed structure and reference validation.",
      { nextAction: "Retain the current snapshot and retry this stage or use demo mode." },
    ).details;
  }
  if (
    code === "ECONNRESET" ||
    code === "ENETUNREACH" ||
    code === "NETWORK_ERROR"
  ) {
    return operationError("NETWORK_ERROR", "The network connection was interrupted.", {
      nextAction: "Check the network and retry; existing data will not be cleared.",
    }).details;
  }

  return {
    code: "INTERNAL_ERROR",
    message: "Local demo processing failed; source file content was not recorded.",
    retryable: true,
    preserveProjectData: true,
    nextAction: "Retry this stage; if it still fails, check the local service.",
  };
}

function success(requestId: string, data: unknown): BridgeResponse {
  return {
    protocolVersion: BRIDGE_PROTOCOL_VERSION,
    requestId,
    success: true,
    data,
  };
}

function approvedPlanInput(
  snapshot: AnalysisSnapshot,
  strategyBundle: EvidenceStrategyBundle,
  businessGoal: BusinessGoal,
  preferences: ActionPlanPreferences,
) {
  return {
    snapshot,
    businessGoal,
    approvedInsights: strategyBundle.insights.filter(
      (insight) => insight.approvalStatus === "approved",
    ),
    approvedStrategies: strategyBundle.strategies.filter(
      (strategy) => strategy.approvalStatus === "approved",
    ),
    preferences,
  };
}

async function runOperation(request: BridgeRequest): Promise<unknown> {
  const now = dateFromPayload(request.payload.now);

  if (request.operation === "health") {
    return {
      status: "ok",
      protocolVersion: BRIDGE_PROTOCOL_VERSION,
      runtime: "short-lived-node-process",
      rawFilePersistence: false,
    };
  }

  if (request.operation === "analyze_synthetic") {
    return buildAnalysisProject(createSyntheticParseResults(), "mock", now);
  }

  if (request.operation === "analyze_uploads") {
    return buildAnalysisProject(
      parseUploadedResults(request.payload.files),
      "uploaded",
      now,
    );
  }

  const snapshot = snapshotFromPayload(request.payload.snapshot);
  const strategyBundle = bundleFromPayload(
    request.payload.strategyBundle,
    snapshot,
  );

  if (request.operation === "create_plan") {
    if (!snapshot.canEnterInsights) {
      throw operationError(
        "BLOCKING_DATA_QUALITY",
        "Blocking snapshot quality issues prevent plan preparation.",
        { nextAction: "Return to data quality, resolve blocking issues, and analyze again." },
      );
    }
    const businessGoal = goalFromPayload(request.payload.businessGoal);
    const preferences = preferencesFromPayload(request.payload.preferences);
    return generateActionPlan(
      approvedPlanInput(
        snapshot,
        strategyBundle,
        businessGoal,
        preferences,
      ),
      now,
    );
  }

  if (request.operation === "answer_question") {
    const plan = planFromPayload(request.payload.plan, true);
    const question = requiredString(request.payload.question, "question", 2_000);
    return answerProjectQuestion(
      {
        snapshot,
        insights: strategyBundle.insights,
        strategies: strategyBundle.strategies,
        plan,
      },
      question,
      now,
    );
  }

  if (request.operation === "revise_calendar_item") {
    const plan = planFromPayload(request.payload.plan);
    const itemId = requiredString(request.payload.itemId, "itemId", 300);
    const patchValue = requiredRecord(request.payload.patch, "patch");
    const patch: Parameters<typeof reviseCalendarItem>[2] = {};
    for (const field of [
      "topic",
      "contentFormat",
      "targetAudience",
      "date",
      "scheduledTime",
      "timeZone",
      "callToAction",
    ] as const) {
      if (field in patchValue) {
        patch[field] = boundedString(
          patchValue[field],
          `patch.${field}`,
          field === "contentFormat" ? 100 : 500,
        );
      }
    }
    if ("postText" in patchValue) {
      patch.postText = boundedString(
        patchValue.postText,
        "patch.postText",
        10_000,
        true,
      );
    }
    if ("channel" in patchValue) {
      const channel = boundedString(patchValue.channel, "patch.channel", 100);
      if (!isBufferChannel(channel)) {
        throw operationError("INVALID_REQUEST", "The content channel is invalid.", {
          retryable: false,
        });
      }
      patch.channel = channel;
    }
    if ("mediaUrls" in patchValue) {
      patch.mediaUrls = stringArray(
        patchValue.mediaUrls,
        "patch.mediaUrls",
        20,
        2_000,
      );
    }
    if ("linkUrl" in patchValue) {
      patch.linkUrl = nullableString(patchValue.linkUrl, "patch.linkUrl", 2_000);
    }
    if ("campaignTag" in patchValue) {
      patch.campaignTag = nullableString(
        patchValue.campaignTag,
        "patch.campaignTag",
        200,
      );
    }
    if ("status" in patchValue) {
      if (
        patchValue.status !== "ai_draft" &&
        patchValue.status !== "confirmed" &&
        patchValue.status !== "rejected"
      ) {
        throw operationError("INVALID_REQUEST", "The content item status is invalid.", {
          retryable: false,
        });
      }
      patch.status = patchValue.status;
    }
    return reviseCalendarItem(plan, itemId, patch, now);
  }

  if (request.operation === "revise_schedule") {
    const plan = planFromPayload(request.payload.plan);
    const preferences = preferencesFromPayload(request.payload.preferences);
    return reviseActionPlanSchedule(
      plan,
      approvedPlanInput(
        snapshot,
        strategyBundle,
        plan.businessGoal,
        plan.preferences,
      ),
      preferences,
      now,
    );
  }

  if (request.operation === "confirm_plan") {
    return confirmActionPlan(planFromPayload(request.payload.plan), now);
  }

  if (request.operation === "preview_buffer_handoff") {
    return validateBufferHandoff(
      planFromPayload(request.payload.plan),
      bufferOptionsFromPayload(request.payload.handoff),
      now,
    );
  }

  if (request.operation === "export_buffer_handoff") {
    return createBufferHandoffExport(
      planFromPayload(request.payload.plan),
      requiredString(request.payload.projectId, "projectId", 100),
      bufferOptionsFromPayload(request.payload.handoff),
      now,
    );
  }

  if (request.operation === "export_project") {
    const plan = planFromPayload(request.payload.plan, true);
    const exportInput: ReportExportInput = {
      projectId: requiredString(
        request.payload.projectId,
        "projectId",
        100,
      ),
      snapshot,
      strategyBundle,
      plan,
    };
    return createReportExportArtifacts(exportInput, now);
  }

  throw operationError(
    "UNSUPPORTED_OPERATION",
    "The bridge does not support this operation.",
    { retryable: false },
  );
}

export async function handleBridgeRequest(value: unknown): Promise<BridgeResponse> {
  let requestId = "unknown";
  try {
    const request = parseRequest(value);
    requestId = request.requestId;
    return success(requestId, await runOperation(request));
  } catch (reason) {
    return {
      protocolVersion: BRIDGE_PROTOCOL_VERSION,
      requestId,
      success: false,
      error: bridgeErrorFromUnknown(reason),
    };
  }
}
