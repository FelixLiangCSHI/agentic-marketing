import { metricCatalog } from "@/analysis/metric-catalog";
import type { AnalysisSnapshot, Metric } from "@/domain/analysis";
import type {
  EvidenceInsight,
  EvidenceStrategyBundle,
  MetricEvidenceReference,
  StrategyRecommendation,
} from "@/domain/strategy";

function usable(metrics: readonly Metric[]): Metric[] {
  return metrics.filter(
    (metric) => metric.reliability !== "unavailable" && metric.value !== null,
  );
}

function evidence(metric: Metric): MetricEvidenceReference {
  return {
    metricId: metric.metricId,
    label: metric.label,
    formattedValue: metric.formattedValue,
    period: metric.period,
    sourceModules: metric.sourceModules,
    sourceReferences: metric.sourceReferences,
    reliability: metric.reliability,
    caveat: metric.caveat,
  };
}

function confidence(metrics: readonly Metric[]): EvidenceInsight["confidence"] {
  if (metrics.length > 0 && metrics.every((item) => item.reliability === "reliable")) {
    return "high";
  }
  return metrics.some((item) => item.reliability === "reliable")
    ? "medium"
    : "low";
}

function insight(
  snapshot: AnalysisSnapshot,
  input: Omit<
    EvidenceInsight,
    "snapshotId" | "approvalStatus" | "confidence" | "evidence" | "report"
  > & {
    metrics: Metric[];
  },
): EvidenceInsight {
  const insightConfidence = confidence(input.metrics);
  return {
    insightId: input.insightId,
    snapshotId: snapshot.snapshotId,
    category: input.category,
    title: input.title,
    statement: input.statement,
    possibleMeaning: input.possibleMeaning,
    suggestedValidation: input.suggestedValidation,
    evidence: input.metrics.map(evidence),
    confidence: insightConfidence,
    limitations: input.limitations,
    approvalStatus: "draft",
    report: {
      executiveSummary: input.statement,
      keyFindings: [input.statement],
      businessImplications: [input.possibleMeaning],
      recommendations: [input.suggestedValidation],
      confidenceLevel:
        insightConfidence === "high"
          ? "High"
          : insightConfidence === "medium"
            ? "Medium"
            : "Low",
      evidence: input.metrics.map(
        (metric) =>
          `${metric.label}: ${metric.formattedValue} (${metric.metricId})`,
      ),
      observedTrends: [
        "The available period establishes a directional baseline; additional comparable periods are required to confirm a trend.",
      ],
    },
  };
}

function strategy(
  snapshot: AnalysisSnapshot,
  input: Omit<
    StrategyRecommendation,
    "snapshotId" | "approvalStatus" | "editedByUser" | "report"
  >,
): StrategyRecommendation {
  return {
    ...input,
    snapshotId: snapshot.snapshotId,
    approvalStatus: "draft",
    editedByUser: false,
    report: {
      executiveSummary: input.objective,
      keyFindings: [input.rationale],
      businessImplications: [input.objective],
      recommendations: input.actions,
      confidenceLevel: "Medium",
      evidence: input.metricIds,
      observedTrends: [
        "Recommendations use the current aggregate baseline; outcome trends require future like-for-like measurement.",
      ],
    },
  };
}

export function generateEvidenceStrategyBundle(
  snapshot: AnalysisSnapshot,
  now: Date = new Date(),
): EvidenceStrategyBundle {
  const catalog = metricCatalog(snapshot);
  const insights: EvidenceInsight[] = [];

  const followerMetrics = usable(
    [
      catalog.get("followers.netGrowth"),
      catalog.get("followers.growthRate"),
      catalog.get("followers.newTotal"),
    ].filter((metric): metric is Metric => metric !== undefined),
  );
  if (followerMetrics.length > 0) {
    const primary = followerMetrics[0];
    insights.push(
      insight(snapshot, {
        insightId: "insight-audience-followers",
        category: "audience",
        title: "Follower Change Baseline",
        statement: `${primary.label} is ${primary.formattedValue} for the available analysis period.`,
        possibleMeaning:
          "The aggregate result establishes a direction for follower acquisition; it does not identify individual followers or intent.",
        suggestedValidation:
          "Repeat the analysis with the same definitions and evaluate publishing windows separately.",
        metrics: followerMetrics,
        limitations: [
          "Aggregate data cannot identify individual followers.",
          "Follower changes cannot be attributed directly to a single content item.",
        ],
      }),
    );
  }

  const visitorMetrics = usable(
    [
      catalog.get("visitors.pageViewsTotal"),
      catalog.get("visitors.uniqueVisitorsTotal"),
      catalog.get("visitors.pageViewsPerVisitor"),
    ].filter((metric): metric is Metric => metric !== undefined),
  );
  if (visitorMetrics.length > 0) {
    const primary = visitorMetrics[0];
    insights.push(
      insight(snapshot, {
        insightId: "insight-audience-visitors",
        category: "audience",
        title: "Page Visit Baseline",
        statement: `${primary.label} is ${primary.formattedValue} for the available analysis period.`,
        possibleMeaning:
          "The result quantifies aggregate page traffic without identifying anonymous visitors or purchase intent.",
        suggestedValidation:
          "Track Page Views, Unique Visitors, and CTA clicks over equivalent periods.",
        metrics: visitorMetrics,
        limitations: [
          "Visitor data is anonymous and aggregated.",
          "Page Views and follower changes do not support user-level attribution.",
        ],
      }),
    );
  }

  const contentMetrics = usable(
    [
      catalog.get("content.engagementRate"),
      catalog.get("content.ctr"),
      catalog.get("content.medianEngagementRate"),
      catalog.get("content.publishedCount"),
    ].filter((metric): metric is Metric => metric !== undefined),
  );
  if (contentMetrics.length > 0) {
    const primary = contentMetrics[0];
    insights.push(
      insight(snapshot, {
        insightId: "insight-content-performance",
        category: "content",
        title: "Content Performance Baseline",
        statement: `${primary.label} is ${primary.formattedValue} for the available analysis period.`,
        possibleMeaning:
          "Current content performance provides an experiment baseline, not a forecast of future results.",
        suggestedValidation:
          "Run single-variable tests across format, topic, and CTA, then review the next comparable import.",
        metrics: contentMetrics,
        limitations: [
          "Historical performance does not guarantee future results.",
          "Small content segments support directional analysis only.",
        ],
      }),
    );
  }

  const strategies: StrategyRecommendation[] = [];
  const contentInsight = insights.find(
    (item) => item.insightId === "insight-content-performance",
  );
  if (contentInsight) {
    strategies.push(
      strategy(snapshot, {
        strategyId: "strategy-content-experiment",
        title: "Establish a Measurable Content Experiment Cadence",
        objective: "Use a consistent publishing cadence to compare format, topic, and CTA performance.",
        rationale:
          "The strategy uses the calculated content baseline to design experiments without forecasting a specific growth rate.",
        actions: [
          "Maintain an operationally sustainable weekly publishing volume.",
          "Change one primary variable in each experiment.",
          "Review the same metrics after the next import.",
        ],
        insightIds: [contentInsight.insightId],
        metricIds: contentInsight.evidence.map((item) => item.metricId),
      }),
    );
  }

  const audienceInsights = insights.filter(
    (item) => item.category === "audience",
  );
  if (audienceInsights.length > 0) {
    strategies.push(
      strategy(snapshot, {
        strategyId: "strategy-audience-path",
        title: "Align Audience Messaging and the Page CTA Path",
        objective: "Create an observable path from content to the page CTA for the priority audience.",
        rationale:
          "Follower and visitor data is aggregated; measurement should focus on observable metrics rather than individual conversion attribution.",
        actions: [
          "Use one clear CTA in each content item.",
          "Record publishing windows alongside aggregate page metrics.",
          "Classify proxy ratios separately from verified conversion rates.",
        ],
        insightIds: audienceInsights.map((item) => item.insightId),
        metricIds: audienceInsights.flatMap((item) =>
          item.evidence.map((reference) => reference.metricId),
        ),
      }),
    );
  }

  return {
    promptVersion: "evidence-strategy-v1.0",
    snapshotId: snapshot.snapshotId,
    generatedAt: now.toISOString(),
    insights,
    strategies,
  };
}
