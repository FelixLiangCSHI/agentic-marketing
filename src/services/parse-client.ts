import type {
  FileParseResult,
  LinkedInModule,
  MappingOverrides,
  ParseApiResponse,
  ParseError,
} from "@/domain/linkedin";

export interface ParseFileOptions {
  expectedModule: LinkedInModule;
  moduleOverride?: LinkedInModule;
  mappingOverrides?: MappingOverrides;
  signal?: AbortSignal;
}

export class ParseClientError extends Error {
  readonly details: ParseError;

  constructor(details: ParseError) {
    super(details.message);
    this.name = "ParseClientError";
    this.details = details;
  }
}

function isParseApiResponse(value: unknown): value is ParseApiResponse {
  if (typeof value !== "object" || value === null || !("success" in value)) {
    return false;
  }

  if (value.success === false) {
    return "error" in value;
  }

  return (
    value.success === true &&
    "file" in value &&
    "workbook" in value &&
    "detectedModules" in value
  );
}

export async function parseLinkedInFile(
  file: File,
  options: ParseFileOptions,
): Promise<FileParseResult> {
  const formData = new FormData();
  formData.set("file", file);
  formData.set("expectedModule", options.expectedModule);

  if (options.moduleOverride) {
    formData.set("moduleOverride", options.moduleOverride);
  }

  if (options.mappingOverrides) {
    formData.set(
      "mappingOverrides",
      JSON.stringify(options.mappingOverrides),
    );
  }

  const response = await fetch("/api/parse", {
    method: "POST",
    body: formData,
    cache: "no-store",
    signal: options.signal,
  });
  const payload: unknown = await response.json();

  if (!isParseApiResponse(payload)) {
    throw new ParseClientError({
      code: "PARSE_FAILED",
      message: "解析服务返回了无法识别的响应。",
      retryable: true,
    });
  }

  if (!payload.success) {
    throw new ParseClientError(payload.error);
  }

  return payload;
}
