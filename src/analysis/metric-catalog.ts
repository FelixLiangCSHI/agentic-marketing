import type { AnalysisSnapshot, Metric } from "@/domain/analysis";

export function listSnapshotMetrics(snapshot: AnalysisSnapshot): Metric[] {
  const followers = snapshot.metrics.followers;
  const visitors = snapshot.metrics.visitors;
  const content = snapshot.metrics.content;
  const cross = snapshot.metrics.crossModule;

  return [
    followers.startFollowers,
    followers.endFollowers,
    followers.netGrowth,
    followers.growthRate,
    followers.newFollowersTotal,
    followers.organicShare,
    followers.sponsoredShare,
    followers.demographicTrend,
    visitors.pageViewsTotal,
    visitors.uniqueVisitorsTotal,
    visitors.pageViewsPerVisitor,
    visitors.customButtonClicksTotal,
    visitors.periodOverPeriodChange,
    content.publishedCount,
    content.impressionsTotal,
    content.clicksTotal,
    content.reactionsTotal,
    content.commentsTotal,
    content.repostsTotal,
    content.clickThroughRate,
    content.engagementRate,
    content.medianEngagementRate,
    cross.visitorFollowerTrendComparison,
    cross.visitorToFollowerProxyRatio,
    cross.publishingWindowCorrelation,
    ...content.byContentType.flatMap((group) => group.metrics),
    ...content.byWeekday.flatMap((group) => group.metrics),
  ];
}

export function metricCatalog(
  snapshot: AnalysisSnapshot,
): ReadonlyMap<string, Metric> {
  return new Map(
    listSnapshotMetrics(snapshot).map((metric) => [metric.metricId, metric]),
  );
}

export function availableMetricCatalog(
  snapshot: AnalysisSnapshot,
): ReadonlyMap<string, Metric> {
  return new Map(
    listSnapshotMetrics(snapshot)
      .filter(
        (metric) =>
          metric.reliability !== "unavailable" && metric.value !== null,
      )
      .map((metric) => [metric.metricId, metric]),
  );
}
