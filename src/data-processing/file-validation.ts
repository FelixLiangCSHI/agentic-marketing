import type {
  ParseError,
  SpreadsheetFormat,
} from "@/domain/linkedin";

export const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024;
export const MAX_REQUEST_SIZE_BYTES = MAX_UPLOAD_SIZE_BYTES + 1024 * 1024;
export const SUPPORTED_FILE_EXTENSIONS = [".xlsx", ".xls", ".csv"] as const;
export const ACCEPTED_FILE_TYPES = SUPPORTED_FILE_EXTENSIONS.join(",");

const MIME_TYPES: Record<SpreadsheetFormat, readonly string[]> = {
  csv: [
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
  ],
  xls: ["application/vnd.ms-excel"],
  xlsx: [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
  ],
};

const GENERIC_MIME_TYPES = ["", "application/octet-stream"];

interface FileEnvelope {
  name: string;
  size: number;
  type: string;
}

export function sanitizeUploadFileName(fileName: string): string {
  const baseName = fileName.split(/[\\/]/).at(-1) ?? "upload";
  return baseName.replace(/[\u0000-\u001F\u007F]/g, "").slice(0, 240);
}

export type FileEnvelopeValidation =
  | {
      ok: true;
      extensionFormat: SpreadsheetFormat;
      mimeWarning: string | null;
    }
  | {
      ok: false;
      error: ParseError;
    };

export type ServerFileValidation =
  | {
      ok: true;
      format: SpreadsheetFormat;
      mimeWarning: string | null;
    }
  | {
      ok: false;
      error: ParseError;
    };

function error(
  code: ParseError["code"],
  message: string,
  retryable = true,
): ParseError {
  return { code, message, retryable };
}

export function getSpreadsheetExtension(
  fileName: string,
): SpreadsheetFormat | null {
  const match = fileName.toLocaleLowerCase("en-US").match(/\.([a-z0-9]+)$/);
  const extension = match?.[1];

  if (extension === "csv" || extension === "xls" || extension === "xlsx") {
    return extension;
  }

  return null;
}

export function validateFileEnvelope(
  file: FileEnvelope,
): FileEnvelopeValidation {
  const extensionFormat = getSpreadsheetExtension(file.name);

  if (!extensionFormat) {
    return {
      ok: false,
      error: error(
        "UNSUPPORTED_FILE_TYPE",
        "Only XLSX, XLS, and CSV files are supported.",
      ),
    };
  }

  if (file.size === 0) {
    return {
      ok: false,
      error: error("EMPTY_FILE", "The file is empty. Export it again and retry."),
    };
  }

  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    return {
      ok: false,
      error: error(
        "REQUEST_TOO_LARGE",
        `The file exceeds the ${formatFileSize(MAX_UPLOAD_SIZE_BYTES)} limit.`,
      ),
    };
  }

  const normalizedMime = file.type.toLocaleLowerCase("en-US").trim();

  if (GENERIC_MIME_TYPES.includes(normalizedMime)) {
    return {
      ok: true,
      extensionFormat,
      mimeWarning: "The browser did not provide a reliable MIME type; the server will validate the file signature.",
    };
  }

  if (!MIME_TYPES[extensionFormat].includes(normalizedMime)) {
    return {
      ok: false,
      error: error(
        "INVALID_MIME_TYPE",
        "The MIME type does not match the extension. Confirm the file was not renamed incorrectly.",
      ),
    };
  }

  return { ok: true, extensionFormat, mimeWarning: null };
}

function startsWith(bytes: Uint8Array, signature: readonly number[]): boolean {
  return signature.every((value, index) => bytes[index] === value);
}

function containsByteSequence(
  bytes: Uint8Array,
  sequence: readonly number[],
): boolean {
  if (sequence.length === 0 || sequence.length > bytes.length) {
    return false;
  }

  for (let index = 0; index <= bytes.length - sequence.length; index += 1) {
    if (bytes[index] !== sequence[0]) {
      continue;
    }

    let matches = true;
    for (let offset = 1; offset < sequence.length; offset += 1) {
      if (bytes[index + offset] !== sequence[offset]) {
        matches = false;
        break;
      }
    }

    if (matches) {
      return true;
    }
  }

  return false;
}

function looksLikeEncryptedOfficeContainer(bytes: Uint8Array): boolean {
  const markers = ["EncryptedPackage", "EncryptionInfo"];

  return markers.some((marker) => {
    const ascii = [...marker].map((character) => character.charCodeAt(0));
    const utf16LittleEndian = ascii.flatMap((value) => [value, 0]);
    return (
      containsByteSequence(bytes, ascii) ||
      containsByteSequence(bytes, utf16LittleEndian)
    );
  });
}

function looksLikeText(bytes: Uint8Array): boolean {
  if (
    startsWith(bytes, [0xef, 0xbb, 0xbf]) ||
    startsWith(bytes, [0xff, 0xfe]) ||
    startsWith(bytes, [0xfe, 0xff])
  ) {
    return true;
  }

  const sample = bytes.subarray(0, Math.min(bytes.length, 4096));
  return !sample.some((value) => value === 0);
}

function looksLikeSpreadsheetXml(bytes: Uint8Array): boolean {
  if (!looksLikeText(bytes)) {
    return false;
  }

  const sample = new TextDecoder("utf-8", { fatal: false })
    .decode(bytes.subarray(0, Math.min(bytes.length, 4096)))
    .toLocaleLowerCase("en-US");

  return sample.includes("<workbook") || sample.includes("spreadsheetml");
}

export function detectSpreadsheetFormat(
  bytes: Uint8Array,
): SpreadsheetFormat | null {
  if (startsWith(bytes, [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1])) {
    return "xls";
  }

  if (startsWith(bytes, [0x50, 0x4b, 0x03, 0x04])) {
    return "xlsx";
  }

  if (looksLikeSpreadsheetXml(bytes)) {
    return "xls";
  }

  if (looksLikeText(bytes)) {
    return "csv";
  }

  return null;
}

export function validateServerFile(
  file: FileEnvelope,
  bytes: Uint8Array,
): ServerFileValidation {
  const envelope = validateFileEnvelope(file);

  if (!envelope.ok) {
    return envelope;
  }

  const detectedFormat = detectSpreadsheetFormat(bytes);

  if (
    envelope.extensionFormat === "xlsx" &&
    detectedFormat === "xls" &&
    looksLikeEncryptedOfficeContainer(bytes)
  ) {
    return {
      ok: false,
      error: error(
        "ENCRYPTED_WORKBOOK",
        "The workbook is encrypted or password protected. Remove protection before uploading.",
      ),
    };
  }

  if (!detectedFormat || detectedFormat !== envelope.extensionFormat) {
    return {
      ok: false,
      error: error(
        "FILE_SIGNATURE_MISMATCH",
        "File content does not match the extension, so parsing stopped.",
        false,
      ),
    };
  }

  return {
    ok: true,
    format: detectedFormat,
    mimeWarning: envelope.mimeWarning,
  };
}

export function formatFileSize(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}
