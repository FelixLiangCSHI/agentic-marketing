import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_UPLOAD_SIZE_BYTES,
  validateFileEnvelope,
  validateServerFile,
} from "@/data-processing/file-validation";
import { csvBytes } from "@/tests/fixtures";

test("accepts supported CSV envelope and signature", () => {
  const bytes = csvBytes("Date,New followers\n2026-01-01,10");
  const result = validateServerFile(
    {
      name: "synthetic_followers.csv",
      size: bytes.byteLength,
      type: "text/csv",
    },
    bytes,
  );

  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal(result.format, "csv");
  }
});

test("rejects unsupported extension immediately", () => {
  const result = validateFileEnvelope({
    name: "synthetic.exe",
    size: 20,
    type: "application/octet-stream",
  });

  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.equal(result.error.code, "UNSUPPORTED_FILE_TYPE");
  }
});

test("rejects empty and oversized files", () => {
  const empty = validateFileEnvelope({
    name: "synthetic.csv",
    size: 0,
    type: "text/csv",
  });
  const oversized = validateFileEnvelope({
    name: "synthetic.csv",
    size: MAX_UPLOAD_SIZE_BYTES + 1,
    type: "text/csv",
  });

  assert.equal(empty.ok, false);
  assert.equal(oversized.ok, false);
  if (!empty.ok && !oversized.ok) {
    assert.equal(empty.error.code, "EMPTY_FILE");
    assert.equal(oversized.error.code, "REQUEST_TOO_LARGE");
  }
});

test("rejects incompatible MIME and file signatures", () => {
  const invalidMime = validateFileEnvelope({
    name: "synthetic.xlsx",
    size: 20,
    type: "text/csv",
  });
  const csvWithXlsxName = validateServerFile(
    {
      name: "synthetic.xlsx",
      size: 20,
      type:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    csvBytes("Date,Value\n2026-01-01,1"),
  );

  assert.equal(invalidMime.ok, false);
  assert.equal(csvWithXlsxName.ok, false);
  if (!invalidMime.ok && !csvWithXlsxName.ok) {
    assert.equal(invalidMime.error.code, "INVALID_MIME_TYPE");
    assert.equal(csvWithXlsxName.error.code, "FILE_SIGNATURE_MISMATCH");
  }
});

test("identifies an encrypted OOXML container before parsing", () => {
  const marker = new TextEncoder().encode("EncryptionInfo");
  const bytes = new Uint8Array(8 + marker.length * 2);
  bytes.set([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]);
  marker.forEach((value, index) => {
    bytes[8 + index * 2] = value;
    bytes[8 + index * 2 + 1] = 0;
  });
  const result = validateServerFile(
    {
      name: "synthetic_encrypted.xlsx",
      size: bytes.byteLength,
      type:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    bytes,
  );

  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.equal(result.error.code, "ENCRYPTED_WORKBOOK");
  }
});
