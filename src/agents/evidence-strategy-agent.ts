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
        title: "Healthcare Professional Reach Baseline",
        statement: `${primary.label} is ${primary.formattedValue} for the available analysis period.`,
        possibleMeaning:
          "The aggregate result establishes a direction for healthcare professional and KOL reach; it does not verify stakeholder role or procurement intent.",
        suggestedValidation:
          "Repeat the analysis with the same definitions and compare clinical-evidence, regulatory, and economic-value publishing windows.",
        metrics: followerMetrics,
        limitations: [],
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
        title: "Hospital Stakeholder Page Visit Baseline",
        statement: `${primary.label} is ${primary.formattedValue} for the available analysis period.`,
        possibleMeaning:
          "The result quantifies aggregate page traffic without identifying healthcare professionals, hospital procurement teams, or evaluation intent.",
        suggestedValidation:
          "Track Page Views, Unique Visitors, and clinical-evidence CTA clicks over equivalent periods.",
        metrics: visitorMetrics,
        limitations: [],
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
        title: "Clinical Evidence Content Baseline",
        statement: `${primary.label} is ${primary.formattedValue} for the available analysis period.`,
        possibleMeaning:
          "Current content performance provides an experiment baseline, not a forecast of future results.",
        suggestedValidation:
          "Run single-variable tests across product area, evidence type, and healthcare-professional CTA, then review the next comparable import.",
        metrics: contentMetrics,
        limitations: [],
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
        title: "Establish a Clinical Evidence Publishing Cadence",
        objective: "Use a consistent publishing cadence to compare clinical evidence, regulatory, patient-outcome, and economic-value topics.",
        rationale:
          "The strategy uses the calculated content baseline to evaluate evidence themes without forecasting adoption or patient outcomes.",
        actions: [
          "Maintain a reviewable cadence across ultrasound, patient monitoring, endoscopy, IVD, MRI, CT, digital health, and surgical robotics.",
          "Validate clinical and regulatory statements, including FDA or CE status, before publication.",
          "Compare engagement with clinical workflow, patient outcomes, and economic value evidence after the next import.",
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
        title: "Align Medical Device Evidence with the Procurement Pathway",
        objective: "Create an observable path from product evidence to resources for healthcare professionals and hospital procurement stakeholders.",
        rationale:
          "Follower and visitor data is aggregated; measurement should focus on evidence engagement rather than individual procurement attribution.",
        actions: [
          "Use one clear CTA to an approved clinical evidence, regulatory, or health-economic resource.",
          "Record product area and intended clinical workflow alongside aggregate page metrics.",
          "Separate engagement proxies from verified KOL activity or hospital procurement milestones.",
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
