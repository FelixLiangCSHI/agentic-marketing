import {
  MAX_REQUEST_SIZE_BYTES,
  sanitizeUploadFileName,
  validateFileEnvelope,
  validateServerFile,
} from "@/data-processing/file-validation";
import {
  isFieldForModule,
  isStandardField,
} from "@/data-processing/field-aliases";
import {
  LINKEDIN_MODULES,
  type LinkedInModule,
  type MappingOverrides,
  type ParseApiResponse,
  type ParseError,
} from "@/domain/linkedin";
import {
  getSafeParseError,
  parseSpreadsheetBytes,
} from "@/server/parsing/spreadsheet-parser";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_MAPPING_JSON_LENGTH = 100_000;
const MAX_MAPPING_OVERRIDES = 500;

function responseStatus(error: ParseError): number {
  if (error.code === "REQUEST_TOO_LARGE") {
    return 413;
  }

  if (
    error.code === "UNSUPPORTED_FILE_TYPE" ||
    error.code === "INVALID_MIME_TYPE" ||
    error.code === "FILE_SIGNATURE_MISMATCH"
  ) {
    return 415;
  }

  if (
    error.code === "MISSING_FILE" ||
    error.code === "EMPTY_FILE" ||
    error.code === "INVALID_MAPPING_OVERRIDE" ||
    error.code === "INVALID_MODULE_OVERRIDE"
  ) {
    return 400;
  }

  return 422;
}

function jsonResponse(payload: ParseApiResponse, status = 200): Response {
  return Response.json(payload, {
    status,
    headers: {
      "Cache-Control": "no-store, max-age=0",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function failure(error: ParseError): Response {
  return jsonResponse(
    {
      success: false,
      error,
    },
    responseStatus(error),
  );
}

function stableError(
  code: ParseError["code"],
  message: string,
  retryable = true,
): ParseError {
  return { code, message, retryable };
}

async function readBodyWithLimit(
  body: ReadableStream<Uint8Array> | null,
  limitBytes: number,
): Promise<Uint8Array> {
  if (body === null) {
    return new Uint8Array(0);
  }

  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let totalBytes = 0;

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      totalBytes += value.byteLength;
      if (totalBytes > limitBytes) {
        throw stableError(
          "REQUEST_TOO_LARGE",
          "The upload exceeds the size limit. Select a smaller file.",
        );
      }
      chunks.push(value);
    }
  } finally {
    await reader.cancel().catch(() => undefined);
  }

  const combined = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    combined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return combined;
}

function parseModule(
  value: FormDataEntryValue | null,
  fieldName: string,
): LinkedInModule | undefined {
  if (value === null || value === "") {
    return undefined;
  }

  if (
    typeof value !== "string" ||
    !LINKEDIN_MODULES.includes(value as LinkedInModule)
  ) {
    throw stableError(
      "INVALID_MODULE_OVERRIDE",
      `${fieldName} is not a valid data module.`,
      false,
    );
  }

  return value as LinkedInModule;
}

function parseMappingOverrides(
  value: FormDataEntryValue | null,
  targetModule?: LinkedInModule,
): MappingOverrides {
  if (value === null || value === "") {
    return {};
  }

  if (
    typeof value !== "string" ||
    value.length > MAX_MAPPING_JSON_LENGTH
  ) {
    throw stableError(
      "INVALID_MAPPING_OVERRIDE",
      "The field mapping configuration is invalid or too large.",
      false,
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw stableError(
      "INVALID_MAPPING_OVERRIDE",
      "The field mapping configuration is not valid JSON.",
      false,
    );
  }

  if (
    typeof parsed !== "object" ||
    parsed === null ||
    Array.isArray(parsed)
  ) {
    throw stableError(
      "INVALID_MAPPING_OVERRIDE",
      "The field mapping configuration must be an object.",
      false,
    );
  }

  const entries = Object.entries(parsed);
  if (entries.length > MAX_MAPPING_OVERRIDES) {
    throw stableError(
      "INVALID_MAPPING_OVERRIDE",
      "The number of field mappings exceeds the limit.",
      false,
    );
  }

  const safeEntries: [string, MappingOverrides[string]][] = [];

  for (const [key, field] of entries) {
    if (
      key.length > 500 ||
      key === "__proto__" ||
      key === "prototype" ||
      key === "constructor" ||
      (field !== null &&
        (!isStandardField(field) ||
          (targetModule && !isFieldForModule(targetModule, field))))
    ) {
      throw stableError(
        "INVALID_MAPPING_OVERRIDE",
        "The field mapping contains an invalid key or standard field.",
        false,
      );
    }

    safeEntries.push([key, field]);
  }

  return Object.fromEntries(safeEntries);
}

function isParseError(value: unknown): value is ParseError {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    "message" in value &&
    "retryable" in value
  );
}

export async function POST(request: Request): Promise<Response> {
  const contentLengthHeader = request.headers.get("content-length");

  if (contentLengthHeader !== null) {
    const contentLength = Number(contentLengthHeader);
    // 非法 Content-Length 一律 fail-closed，不进入缓冲。
    if (!Number.isFinite(contentLength) || contentLength < 0) {
      return failure(
        stableError(
          "REQUEST_TOO_LARGE",
          "The upload request size could not be determined. Select the file again.",
        ),
      );
    }
    if (contentLength > MAX_REQUEST_SIZE_BYTES) {
      return failure(
        stableError(
          "REQUEST_TOO_LARGE",
          "The upload exceeds the size limit. Select a smaller file.",
        ),
      );
    }
  }

  // Content-Length 缺失（multipart 常见）时不直接缓冲整个请求体：
  // 流式读取并施加字节上限，超限立即中止，避免超大请求 DoS。
  let bodyBytes: Uint8Array;
  try {
    bodyBytes = await readBodyWithLimit(request.body, MAX_REQUEST_SIZE_BYTES);
  } catch (reason) {
    if (isParseError(reason)) {
      return failure(reason);
    }
    return failure(
      stableError(
        "PARSE_FAILED",
        "The upload request could not be read. Select the file again.",
      ),
    );
  }

  let formData: FormData;
  try {
    formData = await new Request(request.url, {
      method: "POST",
      headers: { "content-type": request.headers.get("content-type") ?? "" },
      body: bodyBytes.buffer as ArrayBuffer,
    }).formData();
  } catch {
    return failure(
      stableError(
        "PARSE_FAILED",
        "The upload request could not be read. Select the file again.",
      ),
    );
  }

  const fileEntry = formData.get("file");
  if (!(fileEntry instanceof File)) {
    return failure(
      stableError("MISSING_FILE", "The request contains no parseable file."),
    );
  }

  const fileName = sanitizeUploadFileName(fileEntry.name);
  const envelopeValidation = validateFileEnvelope({
    name: fileName,
    size: fileEntry.size,
    type: fileEntry.type,
  });

  if (!envelopeValidation.ok) {
    return failure(envelopeValidation.error);
  }

  let expectedModule: LinkedInModule | undefined;
  let moduleOverride: LinkedInModule | undefined;
  let mappingOverrides: MappingOverrides;

  try {
    expectedModule = parseModule(
      formData.get("expectedModule"),
      "expectedModule",
    );
    moduleOverride = parseModule(
      formData.get("moduleOverride"),
      "moduleOverride",
    );
    mappingOverrides = parseMappingOverrides(
      formData.get("mappingOverrides"),
      moduleOverride ?? expectedModule,
    );
  } catch (reason) {
    return failure(
      isParseError(reason)
        ? reason
        : stableError(
            "INVALID_MAPPING_OVERRIDE",
            "The upload configuration is invalid.",
            false,
          ),
    );
  }

  let bytes: Uint8Array | null = null;

  try {
    bytes = new Uint8Array(await fileEntry.arrayBuffer());
    const serverValidation = validateServerFile(
      {
        name: fileName,
        size: fileEntry.size,
        type: fileEntry.type,
      },
      bytes,
    );

    if (!serverValidation.ok) {
      return failure(serverValidation.error);
    }

    const result = parseSpreadsheetBytes({
      bytes,
      fileName,
      mimeType: fileEntry.type,
      format: serverValidation.format,
      expectedModule,
      moduleOverride,
      mappingOverrides,
    });

    return jsonResponse(result);
  } catch (reason) {
    return failure(getSafeParseError(reason));
  } finally {
    bytes?.fill(0);
    bytes = null;
  }
}
