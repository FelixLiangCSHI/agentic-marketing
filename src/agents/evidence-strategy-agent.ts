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
    "snapshotId" | "approvalStatus" | "confidence" | "evidence"
  > & {
    metrics: Metric[];
  },
): EvidenceInsight {
  return {
    insightId: input.insightId,
    snapshotId: snapshot.snapshotId,
    category: input.category,
    title: input.title,
    statement: input.statement,
    possibleMeaning: input.possibleMeaning,
    suggestedValidation: input.suggestedValidation,
    evidence: input.metrics.map(evidence),
    confidence: confidence(input.metrics),
    limitations: input.limitations,
    approvalStatus: "draft",
  };
}

function strategy(
  snapshot: AnalysisSnapshot,
  input: Omit<
    StrategyRecommendation,
    "snapshotId" | "approvalStatus" | "editedByUser"
  >,
): StrategyRecommendation {
  return {
    ...input,
    snapshotId: snapshot.snapshotId,
    approvalStatus: "draft",
    editedByUser: false,
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
        title: "关注者变化基线",
        statement: `数据显示，${primary.label}为 ${primary.formattedValue}。`,
        possibleMeaning:
          "这可能意味着当前关注者获取存在可观察的方向，但不能据此识别具体关注者或个人意向。",
        suggestedValidation:
          "建议在下一次导入中使用相同口径复核趋势，并与内容发布窗口分开验证。",
        metrics: followerMetrics,
        limitations: [
          "数据为聚合口径，不能识别具体关注者。",
          "增长变化不能直接归因于单条内容。",
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
        title: "主页访问基线",
        statement: `数据显示，${primary.label}为 ${primary.formattedValue}。`,
        possibleMeaning:
          "这可能意味着主页正在获得一定聚合访问，但无法判断匿名访客身份或其购买意向。",
        suggestedValidation:
          "建议持续采集 Page Views、Unique Visitors 与 CTA 点击，并按相同周期比较。",
        metrics: visitorMetrics,
        limitations: [
          "Visitors 是匿名聚合数据。",
          "Page Views 与关注者变化之间不存在用户级归因。",
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
        title: "内容表现基线",
        statement: `数据显示，${primary.label}为 ${primary.formattedValue}。`,
        possibleMeaning:
          "这可能意味着现有内容形成了可用于实验比较的基线，而不是未来表现承诺。",
        suggestedValidation:
          "建议使用内容类型、主题和 CTA 的单变量实验，并在下一次导入后复盘。",
        metrics: contentMetrics,
        limitations: [
          "历史表现不保证未来结果。",
          "样本较少的内容分组仅适合方向性判断。",
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
        title: "建立可复盘的内容实验节奏",
        objective: "用稳定发布节奏验证内容形式、主题和 CTA 的相对表现。",
        rationale:
          "该策略仅使用已计算的内容基线设计实验，不承诺具体增长幅度。",
        actions: [
          "保持每周可执行的发布数量。",
          "每轮只改变一个主要变量。",
          "在下一次导入后按相同指标复盘。",
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
        title: "统一受众信息与主页 CTA 路径",
        objective: "围绕重点受众建立从内容到主页 CTA 的可观测路径。",
        rationale:
          "Followers 与 Visitors 均为聚合数据，因此策略重点是可收集指标，而非个人级转化归因。",
        actions: [
          "在内容中保持单一、明确的 CTA。",
          "记录发布窗口与主页聚合指标。",
          "避免将代理比率称为真实转化率。",
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
