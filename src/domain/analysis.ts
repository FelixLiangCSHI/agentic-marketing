import type {
  ContentField,
  FollowersField,
  LinkedInModule,
  NormalizedLinkedInRecord,
  StandardField,
  VisitorsField,
} from "@/domain/linkedin";

export type MetricReliability =
  | "reliable"
  | "directional"
  | "unavailable";

export type TimeGranularity = "daily" | "weekly" | "monthly" | "irregular";

export type MetricUnit =
  | "count"
  | "percentage"
  | "ratio"
  | "score"
  | "text";

export type MetricValue = number | string | null;

export interface AnalysisPeriod {
  start: string;
  end: string;
  granularity: TimeGranularity;
  sampleSize: number;
}

export interface SourceReference {
  module: LinkedInModule;
  fileName: string;
  sheetName: string;
  rowStart: number;
  rowEnd: number;
  fields: StandardField[];
}

export interface Metric {
  metricId: string;
  label: string;
  value: MetricValue;
  formattedValue: string;
  unit: MetricUnit;
  formula: string;
  period: AnalysisPeriod | null;
  sourceModules: LinkedInModule[];
  sourceReferences: SourceReference[];
  reliability: MetricReliability;
  reliabilityReasons: string[];
  caveat?: string;
}

export interface SeriesPoint {
  period: string;
  value: number | null;
  formattedValue: string;
  sourceReferences: SourceReference[];
}

export interface MetricSeries {
  seriesId: string;
  label: string;
  unit: MetricUnit;
  period: AnalysisPeriod | null;
  points: SeriesPoint[];
  reliability: MetricReliability;
  reliabilityReasons: string[];
  sourceModules: LinkedInModule[];
}

export interface RankedItem {
  rank: number;
  tied: boolean;
  key: string;
  label: string;
  value: number;
  formattedValue: string;
  reliability: MetricReliability;
  reliabilityReasons: string[];
  sourceReferences: SourceReference[];
}

export interface RankedMetric {
  metricId: string;
  label: string;
  formula: string;
  period: AnalysisPeriod | null;
  sourceModules: LinkedInModule[];
  items: RankedItem[];
  reliability: MetricReliability;
  reliabilityReasons: string[];
}

export interface GroupMetric {
  key: string;
  label: string;
  sampleSize: number;
  metrics: Metric[];
  reliability: MetricReliability;
  reliabilityReasons: string[];
}

export type QualityIssueCode =
  | "CONTENT_DATE_OUTSIDE_RANGE"
  | "CONTENT_ENGAGEMENT_COMPONENTS_INVALID"
  | "DATE_GAP"
  | "DUPLICATE_RECORD"
  | "FOLLOWER_TOTAL_DECREASE"
  | "GRANULARITY_MISMATCH"
  | "INVALID_NUMERIC_VALUE"
  | "MISSING_MODULE"
  | "NEGATIVE_METRIC"
  | "NULL_RATE_HIGH"
  | "PERCENTAGE_OUT_OF_RANGE"
  | "SAMPLE_TOO_SMALL"
  | "TIME_RANGE_NO_OVERLAP"
  | "UNIQUE_VISITORS_EXCEED_PAGE_VIEWS";

export interface QualityIssue {
  code: QualityIssueCode;
  severity: "info" | "warning" | "error";
  module: LinkedInModule | "cross-module";
  field: StandardField | null;
  message: string;
  affectedRows: SourceReference[];
  suggestedAction: string;
  blocksAnalysis: boolean;
}

export interface ModuleQualitySummary {
  module: LinkedInModule;
  present: boolean;
  totalRecords: number;
  duplicateRecords: number;
  nullRates: Partial<Record<StandardField, number>>;
  period: AnalysisPeriod | null;
  issueCount: {
    info: number;
    warning: number;
    error: number;
  };
}

export interface DataQualitySnapshot {
  issues: QualityIssue[];
  moduleSummaries: Record<LinkedInModule, ModuleQualitySummary>;
  overlapPeriod: AnalysisPeriod | null;
  hasBlockingIssues: boolean;
  blockingIssueCount: number;
  warningCount: number;
  requiresWarningAcknowledgement: boolean;
}

export interface FollowersMetrics {
  startFollowers: Metric;
  endFollowers: Metric;
  netGrowth: Metric;
  growthRate: Metric;
  newFollowersTotal: Metric;
  organicShare: Metric;
  sponsoredShare: Metric;
  newFollowersTrend: MetricSeries;
  demographicTopN: RankedMetric[];
  demographicTrend: Metric;
}

export interface VisitorsMetrics {
  pageViewsTotal: Metric;
  uniqueVisitorsTotal: Metric;
  pageViewsPerVisitor: Metric;
  customButtonClicksTotal: Metric;
  pageViewsTrend: MetricSeries;
  uniqueVisitorsTrend: MetricSeries;
  periodOverPeriodChange: Metric;
  demographicTopN: RankedMetric[];
}

export interface ContentMetrics {
  publishedCount: Metric;
  impressionsTotal: Metric;
  clicksTotal: Metric;
  reactionsTotal: Metric;
  commentsTotal: Metric;
  repostsTotal: Metric;
  clickThroughRate: Metric;
  engagementRate: Metric;
  medianEngagementRate: Metric;
  contentRanking: RankedMetric;
  byContentType: GroupMetric[];
  byWeekday: GroupMetric[];
}

export interface CrossModuleMetrics {
  visitorFollowerTrendComparison: Metric;
  visitorToFollowerProxyRatio: Metric;
  publishingWindowCorrelation: Metric;
}

export interface AnalysisSnapshot {
  snapshotId: string;
  snapshotVersion: "1.0";
  generatedAt: string;
  inputMode: "uploaded" | "mock";
  quality: DataQualitySnapshot;
  metrics: {
    followers: FollowersMetrics;
    visitors: VisitorsMetrics;
    content: ContentMetrics;
    crossModule: CrossModuleMetrics;
  };
  analysisPeriod: AnalysisPeriod | null;
  sourceModules: LinkedInModule[];
  canEnterInsights: boolean;
  records: {
    followers: number;
    visitors: number;
    content: number;
  };
}

export interface AnalysisInput {
  inputMode: "uploaded" | "mock";
  records: {
    followers: Extract<
      NormalizedLinkedInRecord,
      { module: "followers" }
    >[];
    visitors: Extract<
      NormalizedLinkedInRecord,
      { module: "visitors" }
    >[];
    content: Extract<NormalizedLinkedInRecord, { module: "content" }>[];
  };
}

export const FOLLOWERS_METRIC_FIELDS: readonly FollowersField[] = [
  "totalFollowers",
  "newFollowers",
  "organicFollowers",
  "sponsoredFollowers",
  "demographicCount",
  "demographicPercentage",
];

export const VISITORS_METRIC_FIELDS: readonly VisitorsField[] = [
  "pageViews",
  "uniqueVisitors",
  "customButtonClicks",
  "demographicCount",
  "demographicPercentage",
];

export const CONTENT_METRIC_FIELDS: readonly ContentField[] = [
  "impressions",
  "uniqueImpressions",
  "clicks",
  "reactions",
  "comments",
  "reposts",
  "engagementRate",
  "clickThroughRate",
];
