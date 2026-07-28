import assert from "node:assert/strict";
import test from "node:test";

import { parseSpreadsheetBytes } from "@/server/parsing/spreadsheet-parser";
import { csvBytes, workbookBytes } from "@/tests/fixtures";

test("normalizes thousands separators and percentage representations", () => {
  const bytes = csvBytes(
    [
      "Post title,Created date,Impressions,Clicks,Engagement rate,Click through rate (CTR)",
      'Synthetic post,2026-01-12,"12,345",321,4.8%,3.2',
    ].join("\n"),
  );
  const result = parseSpreadsheetBytes({
    bytes,
    fileName: "synthetic_content.csv",
    mimeType: "text/csv",
    format: "csv",
    expectedModule: "content",
  });
  const record = result.workbook.sheets[0].records[0];

  assert.equal(record.module, "content");
  if (record.module === "content") {
    assert.equal(record.impressions, 12_345);
    assert.equal(record.engagementRate, 0.048);
    assert.equal(record.clickThroughRate, 0.032);
  }
  assert.equal(
    result.issues.some(
      (issue) => issue.code === "PERCENTAGE_SCALE_INFERRED",
    ),
    true,
  );
});

test("normalizes mixed supported dates and flags ambiguous dates", () => {
  const bytes = csvBytes(
    [
      "Post title,Created date,Impressions",
      "Synthetic A,2026-01-02,100",
      "Synthetic B,01/03/2026,120",
      "Synthetic C,14/02/2026,140",
    ].join("\n"),
  );
  const result = parseSpreadsheetBytes({
    bytes,
    fileName: "synthetic_content.csv",
    mimeType: "text/csv",
    format: "csv",
    expectedModule: "content",
  });
  const records = result.workbook.sheets[0].records;

  assert.equal(records.length, 3);
  assert.equal(
    result.issues.some((issue) => issue.code === "AMBIGUOUS_DATE"),
    true,
  );
  assert.equal(
    records.every(
      (record) => record.module === "content" && record.publishedAt !== null,
    ),
    true,
  );
});

test("records missing critical fields without inventing values", () => {
  const bytes = csvBytes(
    "Post title,Created date\nSynthetic post,2026-01-02",
  );
  const result = parseSpreadsheetBytes({
    bytes,
    fileName: "synthetic_content.csv",
    mimeType: "text/csv",
    format: "csv",
    expectedModule: "content",
  });
  const sheet = result.workbook.sheets[0];

  assert.equal(sheet.canProceed, false);
  assert.equal(sheet.missingCriticalFields.includes("impressions"), true);
  assert.equal(
    sheet.issues.some((issue) => issue.code === "MISSING_CRITICAL_FIELD"),
    true,
  );
});

test("marks duplicate rows while retaining every record", () => {
  const bytes = csvBytes(
    [
      "Date,New followers",
      "2026-01-01,10",
      "2026-01-01,10",
      "2026-01-02,12",
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

  assert.equal(sheet.records.length, 3);
  assert.equal(sheet.duplicateRows, 1);
  assert.equal(sheet.records[0].isDuplicate, true);
  assert.equal(sheet.records[1].isDuplicate, true);
});

test("never evaluates workbook formulas or formula-like text", () => {
  const bytes = workbookBytes([
    {
      name: "All posts",
      rows: [
        [
          "Post title",
          "Created date",
          "Content Type",
          "Impressions",
          "Clicks",
        ],
        ["placeholder", "2026-01-02", "Document", 100, 5],
      ],
      mutate: (sheet) => {
        sheet.A2 = {
          t: "s",
          v: "=HYPERLINK(\"https://invalid.example\",\"Synthetic\")",
        };
        sheet.D2 = { t: "n", v: 999, f: "SUM(900,99)" };
      },
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

  assert.equal(record.module, "content");
  if (record.module === "content") {
    assert.equal(record.impressions, null);
    assert.equal(
      record.title,
      '=HYPERLINK("https://invalid.example","Synthetic")',
    );
  }
  assert.equal(
    result.issues.some((issue) => issue.code === "FORMULA_CELL_IGNORED"),
    true,
  );
  assert.equal(
    result.issues.some((issue) => issue.code === "FORMULA_LIKE_TEXT"),
    true,
  );
});
