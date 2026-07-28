import assert from "node:assert/strict";
import test from "node:test";

import {
  calculateContentMetrics,
  calculateFollowersMetrics,
  calculateVisitorsMetrics,
} from "@/analysis/metrics-engine";
import { generateAnalysisSnapshot } from "@/analysis/snapshot-engine";
import {
  contentRecord,
  followerRecord,
  handVerifiedInput,
  visitorRecord,
} from "@/tests/analysis-fixtures";

test("computes hand-verifiable follower and visitor metrics", () => {
  const snapshot = generateAnalysisSnapshot(handVerifiedInput());

  assert.equal(snapshot.metrics.followers.startFollowers.value, 100);
  assert.equal(snapshot.metrics.followers.endFollowers.value, 125);
  assert.equal(snapshot.metrics.followers.netGrowth.value, 25);
  assert.equal(snapshot.metrics.followers.growthRate.value, 0.25);
  assert.equal(snapshot.metrics.followers.newFollowersTotal.value, 35);
  assert.equal(snapshot.metrics.followers.organicShare.value, 26 / 35);
  assert.equal(snapshot.metrics.followers.sponsoredShare.value, 9 / 35);
  assert.equal(snapshot.metrics.visitors.pageViewsTotal.value, 740);
  assert.equal(snapshot.metrics.visitors.uniqueVisitorsTotal.value, 370);
  assert.equal(snapshot.metrics.visitors.pageViewsPerVisitor.value, 2);
  assert.equal(snapshot.metrics.visitors.customButtonClicksTotal.value, 20);
  assert.equal(snapshot.metrics.visitors.periodOverPeriodChange.value, 0.25);
});

test("distinguishes zero from missing and protects zero division", () => {
  const zero = calculateVisitorsMetrics([
    visitorRecord(2, {
      date: "2026-01-01",
      pageViews: 0,
      uniqueVisitors: 0,
      customButtonClicks: 0,
    }),
  ]);
  const missing = calculateVisitorsMetrics([
    visitorRecord(2, {
      date: "2026-01-01",
      pageViews: null,
      uniqueVisitors: null,
      customButtonClicks: null,
    }),
  ]);

  assert.equal(zero.pageViewsTotal.value, 0);
  assert.equal(zero.customButtonClicksTotal.value, 0);
  assert.equal(zero.pageViewsPerVisitor.value, null);
  assert.equal(zero.pageViewsPerVisitor.formattedValue, "unavailable");
  assert.equal(missing.pageViewsTotal.value, null);
  assert.equal(missing.pageViewsTotal.reliability, "unavailable");
});

test("marks follower growth unavailable when the starting value is zero", () => {
  const metrics = calculateFollowersMetrics([
    followerRecord(2, {
      date: "2026-01-01",
      totalFollowers: 0,
    }),
    followerRecord(3, {
      date: "2026-01-02",
      totalFollowers: 10,
    }),
  ]);

  assert.equal(metrics.netGrowth.value, 10);
  assert.equal(metrics.growthRate.value, null);
  assert.equal(metrics.growthRate.formattedValue, "unavailable");
  assert.equal(metrics.growthRate.reliability, "unavailable");
});

test("uses median engagement and stable competition ranking for ties", () => {
  const metrics = calculateContentMetrics([
    contentRecord(2, {
      contentId: "a",
      title: "Ultrasound clinical workflow evidence",
      publishedAt: "2026-01-01T00:00:00.000Z",
      contentType: "Document",
      impressions: 100,
      clicks: 10,
      reactions: 0,
      comments: 0,
      reposts: 0,
    }),
    contentRecord(3, {
      contentId: "b",
      title: "IVD analytical performance review",
      publishedAt: "2026-01-02T00:00:00.000Z",
      contentType: "Document",
      impressions: 200,
      clicks: 20,
      reactions: 0,
      comments: 0,
      reposts: 0,
    }),
    contentRecord(4, {
      contentId: "c",
      title: "Surgical robotics patient outcomes briefing",
      publishedAt: "2026-01-03T00:00:00.000Z",
      contentType: "Video",
      impressions: 100,
      clicks: 90,
      reactions: 0,
      comments: 0,
      reposts: 0,
    }),
  ]);

  assert.equal(metrics.medianEngagementRate.value, 0.1);
  assert.equal(
    metrics.contentRanking.items[0].label,
    "Surgical robotics patient outcomes briefing",
  );
  assert.equal(metrics.contentRanking.items[0].rank, 1);
  assert.equal(metrics.contentRanking.items[1].rank, 2);
  assert.equal(metrics.contentRanking.items[2].rank, 2);
  assert.equal(metrics.contentRanking.items[2].tied, true);
});

test("marks small content groups as directional", () => {
  const metrics = calculateContentMetrics([
    contentRecord(2, {
      contentId: "a",
      publishedAt: "2026-01-01T00:00:00.000Z",
      contentType: "Video",
      impressions: 100,
      clicks: 10,
    }),
    contentRecord(3, {
      contentId: "b",
      publishedAt: "2026-01-02T00:00:00.000Z",
      contentType: "Document",
      impressions: 100,
      clicks: 20,
    }),
    contentRecord(4, {
      contentId: "c",
      publishedAt: "2026-01-03T00:00:00.000Z",
      contentType: "Document",
      impressions: 100,
      clicks: 30,
    }),
  ]);

  assert.equal(
    metrics.byContentType.find((group) => group.key === "Video")
      ?.reliability,
    "directional",
  );
  assert.equal(
    metrics.byContentType.find((group) => group.key === "Document")
      ?.reliability,
    "directional",
  );
});

test("excludes duplicate rows from deterministic totals", () => {
  const duplicate = visitorRecord(3, {
    date: "2026-01-02",
    pageViews: 999,
    uniqueVisitors: 999,
    isDuplicate: true,
  });
  const metrics = calculateVisitorsMetrics([
    visitorRecord(2, {
      date: "2026-01-01",
      pageViews: 100,
      uniqueVisitors: 50,
    }),
    duplicate,
  ]);

  assert.equal(metrics.pageViewsTotal.value, 100);
  assert.equal(metrics.uniqueVisitorsTotal.value, 50);
});

test("computes percentage fields without applying a second scale", () => {
  const metrics = calculateFollowersMetrics([
    followerRecord(2, {
      demographicDimension: "Industry",
      demographicValue: "Healthcare",
      demographicPercentage: 0.6,
    }),
    followerRecord(3, {
      demographicDimension: "Industry",
      demographicValue: "Technology",
      demographicPercentage: 0.4,
    }),
  ]);
  const industry = metrics.demographicTopN.find(
    (ranking) => ranking.label === "Industry Top 5",
  );

  assert.equal(industry?.items[0].value, 0.6);
  assert.equal(industry?.items[0].formattedValue, "60%");
});

test("calculates ratios only from records with complete paired fields", () => {
  const followers = calculateFollowersMetrics([
    followerRecord(2, {
      date: "2026-01-01",
      organicFollowers: 80,
      sponsoredFollowers: 20,
    }),
    followerRecord(3, {
      date: "2026-01-02",
      organicFollowers: 900,
      sponsoredFollowers: null,
    }),
    followerRecord(4, {
      date: "2026-01-03",
      organicFollowers: null,
      sponsoredFollowers: 900,
    }),
  ]);
  const visitors = calculateVisitorsMetrics([
    visitorRecord(2, {
      date: "2026-01-01",
      pageViews: 100,
      uniqueVisitors: 50,
    }),
    visitorRecord(3, {
      date: "2026-01-02",
      pageViews: 900,
      uniqueVisitors: null,
    }),
    visitorRecord(4, {
      date: "2026-01-03",
      pageViews: null,
      uniqueVisitors: 50,
    }),
  ]);
  const content = calculateContentMetrics([
    contentRecord(2, {
      contentId: "complete",
      publishedAt: "2026-01-01T00:00:00.000Z",
      contentType: "Document",
      impressions: 100,
      clicks: 20,
      reactions: 1,
      comments: 1,
      reposts: 1,
    }),
    contentRecord(3, {
      contentId: "missing-clicks",
      publishedAt: "2026-01-02T00:00:00.000Z",
      contentType: "Document",
      impressions: 900,
      clicks: null,
      reactions: 100,
      comments: 100,
      reposts: 100,
    }),
    contentRecord(4, {
      contentId: "missing-impressions",
      publishedAt: "2026-01-03T00:00:00.000Z",
      contentType: "Document",
      impressions: null,
      clicks: 90,
      reactions: 0,
      comments: 0,
      reposts: 0,
    }),
  ]);

  assert.equal(followers.organicShare.value, 0.8);
  assert.equal(followers.sponsoredShare.value, 0.2);
  assert.equal(followers.organicShare.reliability, "directional");
  assert.equal(visitors.pageViewsTotal.value, 1_000);
  assert.equal(visitors.uniqueVisitorsTotal.value, 100);
  assert.equal(visitors.pageViewsPerVisitor.value, 2);
  assert.equal(visitors.pageViewsPerVisitor.reliability, "directional");
  assert.equal(content.clickThroughRate.value, 0.2);
  assert.equal(content.engagementRate.value, 0.23);
  assert.equal(content.clickThroughRate.reliability, "directional");
  assert.equal(content.engagementRate.reliability, "directional");

  const groupedCtr = content.byContentType[0]?.metrics.find(
    (metric) => metric.metricId === "content.type.Document.ctr",
  );
  assert.equal(groupedCtr?.value, 0.2);
  assert.deepEqual(
    content.clickThroughRate.sourceReferences.map((reference) => [
      reference.rowStart,
      reference.rowEnd,
    ]),
    [[2, 2]],
  );
});

test("does not calculate period change across an irregular series", () => {
  const metrics = calculateVisitorsMetrics([
    visitorRecord(2, { date: "2026-01-01", pageViews: 100 }),
    visitorRecord(3, { date: "2026-01-02", pageViews: 110 }),
    visitorRecord(4, { date: "2026-01-10", pageViews: 220 }),
  ]);

  assert.equal(metrics.periodOverPeriodChange.value, null);
  assert.equal(metrics.periodOverPeriodChange.reliability, "unavailable");
  assert.equal(
    metrics.periodOverPeriodChange.reliabilityReasons.some((reason) =>
      reason.includes("间隔不符合"),
    ),
    true,
  );
});
