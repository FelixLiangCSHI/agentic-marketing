import assert from "node:assert/strict";
import test from "node:test";

import { getMappingOverrideKey } from "@/data-processing/field-aliases";
import {
  SpreadsheetParseException,
  parseSpreadsheetBytes,
} from "@/server/parsing/spreadsheet-parser";
import { csvBytes, workbookBytes } from "@/tests/fixtures";

test("parses a normal CSV with a header after an instruction row", () => {
  const bytes = csvBytes(
    [
      "Synthetic fixture - not production data",
      "Date,New followers,Organic followers,Sponsored followers",
      "2026-01-01,20,18,2",
      "2026-01-02,25,22,3",
    ].join("\n"),
  );
  const result = parseSpreadsheetBytes({
    bytes,
    fileName: "synthetic_followers.csv",
    mimeType: "text/csv",
    format: "csv",
    expectedModule: "followers",
  });
  const sheet = result.workbook.sheets[0];

  assert.deepEqual(result.detectedModules, ["followers"]);
  assert.equal(sheet.headerRow, 2);
  assert.equal(sheet.validRows, 2);
  assert.equal(sheet.records[0].module, "followers");
  if (sheet.records[0].module === "followers") {
    assert.equal(sheet.records[0].newFollowers, 20);
    assert.equal(sheet.records[0].source.rowNumber, 3);
  }
});

test("parses a normal XLSX Content sheet", () => {
  const bytes = workbookBytes([
    {
      name: "All posts",
      rows: [
        ["Synthetic fixture - not production data"],
        [
          "Post title",
          "Created date",
          "Content Type",
          "Impressions",
          "Clicks",
          "Engagement rate",
        ],
        ["Ultrasound clinical workflow guide", "2026-03-08", "Document", 1200, 72, "6%"],
      ],
    },
  ]);
  const result = parseSpreadsheetBytes({
    bytes,
    fileName: "synthetic_content.xlsx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    format: "xlsx",
    expectedModule: "content",
  });
  const record = result.workbook.sheets[0].records[0];

  assert.equal(result.canProceed, true);
  assert.equal(record.module, "content");
  if (record.module === "content") {
    assert.equal(record.impressions, 1200);
    assert.equal(record.engagementRate, 0.06);
  }
});

test("parses a legacy BIFF8 XLS Followers sheet", () => {
  const bytes = workbookBytes(
    [
      {
        name: "New followers",
        rows: [
          [
            "Date",
            "Sponsored followers",
            "Organic followers",
            "Total followers",
          ],
          ["2026-03-01", 4, 36, 40],
        ],
      },
    ],
    "biff8",
  );
  const result = parseSpreadsheetBytes({
    bytes,
    fileName: "synthetic_followers.xls",
    mimeType: "application/vnd.ms-excel",
    format: "xls",
    expectedModule: "followers",
  });
  const record = result.workbook.sheets[0].records[0];

  assert.equal(record.module, "followers");
  if (record.module === "followers") {
    assert.equal(record.newFollowers, 40);
    assert.equal(record.totalFollowers, null);
  }
});

test("recognizes and parses multiple related sheets separately", () => {
  const bytes = workbookBytes([
    {
      name: "New followers",
      rows: [
        ["Date", "Organic followers", "Total followers"],
        ["2026-02-01", 28, 30],
      ],
    },
    {
      name: "Industry",
      rows: [
        ["Industry", "Total followers"],
        ["Medical Devices", 120],
      ],
    },
  ]);
  const result = parseSpreadsheetBytes({
    bytes,
    fileName: "synthetic_followers.xlsx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    format: "xlsx",
    expectedModule: "followers",
  });

  assert.equal(result.workbook.sheetCount, 2);
  assert.deepEqual(
    result.workbook.sheets.map((sheet) => sheet.detection.detectedModule),
    ["followers", "followers"],
  );
  const demographic = result.workbook.sheets[1].records[0];
  assert.equal(demographic.module, "followers");
  if (demographic.module === "followers") {
    assert.equal(demographic.demographicDimension, "Industry");
    assert.equal(demographic.demographicValue, "Medical Devices");
    assert.equal(demographic.demographicCount, 120);
  }
});

test("supports manual module and field mapping overrides", () => {
  const bytes = csvBytes("When,Measure\n2026-02-01,42");
  const mappingOverrides = {
    [getMappingOverrideKey("Sheet1", 0, "When")]: "date" as const,
    [getMappingOverrideKey("Sheet1", 1, "Measure")]:
      "newFollowers" as const,
  };
  const result = parseSpreadsheetBytes({
    bytes,
    fileName: "synthetic_unknown.csv",
    mimeType: "text/csv",
    format: "csv",
    expectedModule: "followers",
    moduleOverride: "followers",
    mappingOverrides,
  });

  assert.equal(result.canProceed, true);
  const record = result.workbook.sheets[0].records[0];
  assert.equal(record.module, "followers");
  if (record.module === "followers") {
    assert.equal(record.date, "2026-02-01");
    assert.equal(record.newFollowers, 42);
  }
});

test("rejects an empty byte array with a stable error", () => {
  assert.throws(
    () =>
      parseSpreadsheetBytes({
        bytes: new Uint8Array(),
        fileName: "synthetic.csv",
        mimeType: "text/csv",
        format: "csv",
      }),
    (reason) =>
      reason instanceof SpreadsheetParseException &&
      reason.parseError.code === "EMPTY_FILE",
  );
});

test("returns a sanitized stable error for a damaged XLSX", () => {
  const damaged = new Uint8Array([
    0x50, 0x4b, 0x03, 0x04, 0x00, 0x00, 0x00, 0x00,
  ]);

  assert.throws(
    () =>
      parseSpreadsheetBytes({
        bytes: damaged,
        fileName: "synthetic_damaged.xlsx",
        mimeType:
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        format: "xlsx",
      }),
    (reason) =>
      reason instanceof SpreadsheetParseException &&
      ["CORRUPT_FILE", "PARSE_FAILED"].includes(reason.parseError.code) &&
      !reason.parseError.message.includes("PK"),
  );
});

test("returns no module for an unrecognizable table", () => {
  const result = parseSpreadsheetBytes({
    bytes: csvBytes("Foo,Bar\nAlpha,Beta"),
    fileName: "synthetic_unknown.csv",
    mimeType: "text/csv",
    format: "csv",
  });

  assert.deepEqual(result.detectedModules, []);
  assert.equal(result.canProceed, false);
  assert.equal(
    result.workbook.sheets[0].issues.some(
      (issue) => issue.code === "NO_HEADER_FOUND",
    ),
    true,
  );
});
