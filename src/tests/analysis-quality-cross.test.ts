import assert from "node:assert/strict";
import test from "node:test";

import { calculateCrossModuleMetrics } from "@/analysis/metrics-engine";
import { generateAnalysisSnapshot } from "@/analysis/snapshot-engine";
import type { AnalysisInput } from "@/domain/analysis";
import {
  contentRecord,
  followerRecord,
  handVerifiedInput,
  visitorRecord,
} from "@/tests/analysis-fixtures";

test("blocks cross-module analysis when time ranges do not overlap", () => {
  const input = handVerifiedInput();
  input.records.visitors = input.records.visitors.map((record, index) =>
    visitorRecord(index + 2, {
      ...record,
      date: `2026-02-0${index + 1}`,
    }),
  );
  const snapshot = generateAnalysisSnapshot(input);

  assert.equal(
    snapshot.quality.issues.some(
      (issue) =>
        issue.code === "TIME_RANGE_NO_OVERLAP" && issue.blocksAnalysis,
    ),
    true,
  );
  assert.equal(snapshot.canEnterInsights, false);
  assert.equal(
    snapshot.metrics.crossModule.visitorToFollowerProxyRatio.value,
    null,
  );
});

test("blocks direct comparison for daily versus monthly granularity", () => {
  const input = handVerifiedInput();
  input.records.visitors = [
    visitorRecord(2, {
      date: "2026-01-01",
      pageViews: 100,
      uniqueVisitors: 50,
    }),
    visitorRecord(3, {
      date: "2026-02-01",
      pageViews: 120,
      uniqueVisitors: 60,
    }),
    visitorRecord(4, {
      date: "2026-03-01",
      pageViews: 140,
      uniqueVisitors: 70,
    }),
  ];
  const snapshot = generateAnalysisSnapshot(input);

  assert.equal(
    snapshot.quality.issues.some(
      (issue) =>
        issue.code === "GRANULARITY_MISMATCH" && issue.blocksAnalysis,
    ),
    true,
  );
  assert.equal(
    snapshot.metrics.crossModule.visitorFollowerTrendComparison.value,
    null,
  );
});

test("reports duplicate, follower decrease, visitor inconsistency and outside content", () => {
  const input = handVerifiedInput();
  input.records.followers[1].totalFollowers = 90;
  input.records.followers[2].isDuplicate = true;
  input.records.visitors[0].uniqueVisitors = 250;
  input.records.content.push(
    contentRecord(10, {
      contentId: "outside",
      publishedAt: "2026-04-01T00:00:00.000Z",
      impressions: 100,
      clicks: 10,
    }),
  );
  const snapshot = generateAnalysisSnapshot(input);
  const codes = new Set(snapshot.quality.issues.map((issue) => issue.code));

  assert.equal(codes.has("DUPLICATE_RECORD"), true);
  assert.equal(codes.has("FOLLOWER_TOTAL_DECREASE"), true);
  assert.equal(codes.has("UNIQUE_VISITORS_EXCEED_PAGE_VIEWS"), true);
  assert.equal(codes.has("CONTENT_DATE_OUTSIDE_RANGE"), true);
  assert.equal(snapshot.canEnterInsights, false);
});

test("computes the proxy ratio and labels it as non-conversion proxy", () => {
  const snapshot = generateAnalysisSnapshot(handVerifiedInput());
  const proxy = snapshot.metrics.crossModule.visitorToFollowerProxyRatio;

  assert.equal(proxy.value, 35 / 370);
  assert.match(proxy.label, /Proxy/);
  assert.match(proxy.caveat ?? "", /不能.*真实转化率/);
  assert.equal(
    proxy.reliabilityReasons.some((reason) => reason.includes("不是用户级")),
    true,
  );
});

test("cross-module proxy uses only same-date complete periods", () => {
  const input = handVerifiedInput();
  input.records.followers = [
    followerRecord(2, { date: "2026-01-01", newFollowers: 10 }),
    followerRecord(3, { date: "2026-01-02", newFollowers: 1_000 }),
    followerRecord(4, { date: "2026-01-03", newFollowers: 20 }),
  ];
  input.records.visitors = [
    visitorRecord(2, { date: "2026-01-01", uniqueVisitors: 100 }),
    visitorRecord(4, { date: "2026-01-03", uniqueVisitors: 100 }),
    visitorRecord(5, { date: "2026-01-04", uniqueVisitors: 100 }),
  ];
  input.records.content = [];

  const proxy =
    calculateCrossModuleMetrics(input).visitorToFollowerProxyRatio;

  assert.equal(proxy.value, 0.15);
  assert.equal(proxy.period?.start, "2026-01-01");
  assert.equal(proxy.period?.end, "2026-01-03");
  assert.equal(proxy.period?.sampleSize, 2);
  assert.equal(proxy.reliability, "directional");
  assert.deepEqual(
    proxy.sourceReferences
      .filter((reference) => reference.module === "followers")
      .map((reference) => [reference.rowStart, reference.rowEnd]),
    [
      [2, 2],
      [4, 4],
    ],
  );
});

test("metric evidence traces to file, sheet and row range", () => {
  const snapshot = generateAnalysisSnapshot(handVerifiedInput());
  const metric = snapshot.metrics.visitors.pageViewsTotal;

  assert.equal(metric.sourceReferences.length, 1);
  assert.deepEqual(metric.sourceReferences[0], {
    module: "visitors",
    fileName: "synthetic_visitors.csv",
    sheetName: "Synthetic",
    rowStart: 2,
    rowEnd: 4,
    fields: ["pageViews"],
  });
});

test("calculation results do not depend on input row order", () => {
  const forward = handVerifiedInput();
  const reversed: AnalysisInput = {
    inputMode: forward.inputMode,
    records: {
      followers: [...forward.records.followers].reverse(),
      visitors: [...forward.records.visitors].reverse(),
      content: [...forward.records.content].reverse(),
    },
  };
  const first = generateAnalysisSnapshot(forward);
  const second = generateAnalysisSnapshot(reversed);

  assert.deepEqual(first.metrics, second.metrics);
  assert.deepEqual(first.quality, second.quality);
  assert.equal(first.snapshotId, second.snapshotId);
});

test("snapshot ID changes when a normalized metric value changes", () => {
  const firstInput = handVerifiedInput();
  const secondInput = handVerifiedInput();
  secondInput.records.visitors[0] = {
    ...secondInput.records.visitors[0],
    pageViews: 201,
  };

  assert.notEqual(
    generateAnalysisSnapshot(firstInput).snapshotId,
    generateAnalysisSnapshot(secondInput).snapshotId,
  );
});
