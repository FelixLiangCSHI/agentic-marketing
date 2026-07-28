"use client";

import { useState, type ReactNode } from "react";

import { StrategyPlanningWorkspace } from "@/components/analysis/strategy-planning-workspace";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import { MODULE_CONFIG } from "@/domain/module-config";
import type {
  AnalysisSnapshot,
  GroupMetric,
  Metric,
  MetricReliability,
  MetricSeries,
  RankedMetric,
  SourceReference,
} from "@/domain/analysis";

interface AnalysisSnapshotViewProps {
  snapshot: AnalysisSnapshot;
  warningsAcknowledged: boolean;
  onAcknowledgeWarnings: () => void;
  onBack: () => void;
  onDownload: () => void;
}

const RELIABILITY_LABELS: Record<MetricReliability, string> = {
  reliable: "Reliable",
  directional: "Directional",
  unavailable: "Unavailable",
};

function periodLabel(metric: Metric): string {
  if (!metric.period) {
    return "No date range available";
  }
  return `${metric.period.start} — ${metric.period.end} · ${metric.period.granularity}`;
}

function SourceList({
  references,
}: {
  references: readonly SourceReference[];
}) {
  if (references.length === 0) {
    return <p className="metric-empty-note">No source rows are available for calculation.</p>;
  }
  return (
    <ul className="source-reference-list">
      {references.map((reference) => (
        <li
          key={`${reference.module}-${reference.fileName}-${reference.sheetName}-${reference.rowStart}-${reference.rowEnd}`}
        >
          <strong>{MODULE_CONFIG[reference.module].label}</strong>
          <span title={reference.fileName}>{reference.fileName}</span>
          <span>
            {reference.sheetName} · Row {reference.rowStart}
            {reference.rowEnd === reference.rowStart
              ? ""
              : `–${reference.rowEnd}`}
          </span>
          <small>{reference.fields.join(", ") || "Record-level source"}</small>
        </li>
      ))}
    </ul>
  );
}

function MetricCard({ metric }: { metric: Metric }) {
  return (
    <article
      className={`metric-card metric-card--${metric.reliability}`}
      aria-label={`${metric.label}：${metric.formattedValue}`}
    >
      <header>
        <span>{metric.label}</span>
        <span
          className={`reliability-badge reliability-badge--${metric.reliability}`}
        >
          {RELIABILITY_LABELS[metric.reliability]}
        </span>
      </header>
      <strong className="metric-card__value">{metric.formattedValue}</strong>
      <span className="metric-card__period">{periodLabel(metric)}</span>
      {metric.caveat && (
        <p className="metric-card__caveat">
          <Icon name="alert" size={14} />
          {metric.caveat}
        </p>
      )}
      <details className="metric-details">
        <summary>How this value is calculated</summary>
        <div>
          <strong>Formula</strong>
          <code>{metric.formula}</code>
          <strong>Reliability basis</strong>
          <ul>
            {metric.reliabilityReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <strong>Data sources</strong>
          <SourceList references={metric.sourceReferences} />
        </div>
      </details>
    </article>
  );
}

function SeriesCard({ series }: { series: MetricSeries }) {
  const values = series.points.flatMap((point) =>
    point.value === null ? [] : [point.value],
  );
  const maximum = values.length > 0 ? Math.max(...values) : 0;

  return (
    <article className="series-card">
      <header>
        <div>
          <span className="section-label">TREND</span>
          <h4>{series.label}</h4>
        </div>
        <span
          className={`reliability-badge reliability-badge--${series.reliability}`}
        >
          {RELIABILITY_LABELS[series.reliability]}
        </span>
      </header>
      {series.points.length === 0 ? (
        <EmptyState
          icon="table"
          title="Trend unavailable"
          description={series.reliabilityReasons.join(" ")}
        />
      ) : (
        <div className="snapshot-bars" role="img" aria-label={`${series.label} bar trend`}>
          {series.points.map((point) => (
            <div key={`${series.seriesId}-${point.period}`}>
              <span className="snapshot-bars__value">
                {point.formattedValue}
              </span>
              <span className="snapshot-bars__track">
                <span
                  style={{
                    height: `${
                      maximum > 0 && point.value !== null
                        ? Math.max(4, (point.value / maximum) * 100)
                        : 0
                    }%`,
                  }}
                />
              </span>
              <small>{point.period.slice(5)}</small>
            </div>
          ))}
        </div>
      )}
    </article>
  );
}

function RankingCard({ ranking }: { ranking: RankedMetric }) {
  return (
    <article className="ranking-card">
      <header>
        <div>
          <span className="section-label">RANKING</span>
          <h4>{ranking.label}</h4>
        </div>
        <span
          className={`reliability-badge reliability-badge--${ranking.reliability}`}
        >
          {RELIABILITY_LABELS[ranking.reliability]}
        </span>
      </header>
      {ranking.items.length === 0 ? (
        <EmptyState
          icon="table"
          title="Ranking unavailable"
          description={ranking.reliabilityReasons.join(" ")}
        />
      ) : (
        <ol className="snapshot-ranking">
          {ranking.items.slice(0, 5).map((item) => (
            <li key={item.key}>
              <span>#{item.rank}</span>
              <div>
                <strong>{item.label}</strong>
                <small>
                  {item.tied ? "Tied · " : ""}
                  {RELIABILITY_LABELS[item.reliability]}
                </small>
              </div>
              <strong>{item.formattedValue}</strong>
            </li>
          ))}
        </ol>
      )}
      <details className="metric-details">
        <summary>Review ranking formula and reliability</summary>
        <div>
          <code>{ranking.formula}</code>
          <ul>
            {ranking.reliabilityReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      </details>
    </article>
  );
}

function GroupTable({
  title,
  groups,
}: {
  title: string;
  groups: readonly GroupMetric[];
}) {
  if (groups.length === 0) {
    return (
      <article className="group-card">
        <EmptyState
          icon="table"
          title={`${title} unavailable`}
          description="Required grouping fields are missing."
        />
      </article>
    );
  }

  return (
    <article className="group-card">
      <div className="section-heading">
        <div>
          <span className="section-label">GROUP ANALYSIS</span>
          <h3>{title}</h3>
        </div>
      </div>
      <div className="snapshot-table-wrap">
        <table className="snapshot-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Sample</th>
              <th>Impressions</th>
              <th>CTR</th>
              <th>Median engagement rate</th>
              <th>Reliability</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => (
              <tr key={group.key}>
                <td>
                  <strong>{group.label}</strong>
                </td>
                <td>{group.sampleSize}</td>
                {group.metrics.map((metric) => (
                  <td key={metric.metricId}>{metric.formattedValue}</td>
                ))}
                <td>
                  <span
                    className={`reliability-badge reliability-badge--${group.reliability}`}
                  >
                    {RELIABILITY_LABELS[group.reliability]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

function MetricSection({
  eyebrow,
  title,
  description,
  metrics,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  metrics: readonly Metric[];
  children?: ReactNode;
}) {
  return (
    <section className="snapshot-section">
      <div className="section-heading section-heading--large">
        <div>
          <span className="section-label">{eyebrow}</span>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
      <div className="metric-grid">
        {metrics.map((metric) => (
          <MetricCard key={metric.metricId} metric={metric} />
        ))}
      </div>
      {children}
    </section>
  );
}

export function AnalysisSnapshotView({
  snapshot,
  warningsAcknowledged,
  onAcknowledgeWarnings,
  onBack,
  onDownload,
}: AnalysisSnapshotViewProps) {
  const [planningOpen, setPlanningOpen] = useState(false);
  const nonBlockingWarnings = snapshot.quality.issues.filter(
    (issue) => issue.severity === "warning" && !issue.blocksAnalysis,
  );
  const insightsAllowed =
    snapshot.canEnterInsights &&
    (!snapshot.quality.requiresWarningAcknowledgement ||
      warningsAcknowledged);

  if (planningOpen) {
    return (
      <StrategyPlanningWorkspace
        snapshot={snapshot}
        onBack={() => setPlanningOpen(false)}
      />
    );
  }

  return (
    <div className="snapshot-workspace">
      <section className="snapshot-hero">
        <div>
          <span className="hero__eyebrow">
            <Icon name="table" size={15} />
            ANALYSIS SNAPSHOT · V{snapshot.snapshotVersion}
          </span>
          <h2>Deterministic metrics and data quality snapshot</h2>
          <p>
            Every value is calculated from the standardized model. The snapshot records formulas, periods, sources, and reliability for governed interpretation.
          </p>
        </div>
        <div className="snapshot-hero__actions">
          <button className="secondary-button" type="button" onClick={onBack}>
            Back to field confirmation
          </button>
          <button className="secondary-button" type="button" onClick={onDownload}>
            <Icon name="download" size={16} />
            Download snapshot JSON
          </button>
        </div>
      </section>

      <section className="quality-panel">
        <header className="quality-panel__header">
          <div>
            <span className="section-label">DATA QUALITY</span>
            <h2>Data quality summary</h2>
            <p>
              {snapshot.analysisPeriod
                ? `${snapshot.analysisPeriod.start} — ${snapshot.analysisPeriod.end}`
                : "No common date range across all three modules"}
            </p>
          </div>
          <div className="quality-scorecards">
            <div className="quality-score quality-score--error">
              <strong>{snapshot.quality.blockingIssueCount}</strong>
              <span>Blocking issues</span>
            </div>
            <div className="quality-score quality-score--warning">
              <strong>{snapshot.quality.warningCount}</strong>
              <span>Warnings</span>
            </div>
            <div className="quality-score">
              <strong>
                {Object.values(snapshot.quality.moduleSummaries).reduce(
                  (sum, summary) => sum + summary.totalRecords,
                  0,
                )}
              </strong>
              <span>Standard records</span>
            </div>
          </div>
        </header>

        <div className="quality-module-grid">
          {Object.values(snapshot.quality.moduleSummaries).map((summary) => (
            <article key={summary.module}>
              <span
                className={`module-icon module-icon--${summary.module}`}
              >
                <Icon
                  name={
                    summary.module === "followers"
                      ? "followers"
                      : summary.module === "visitors"
                        ? "visitors"
                        : "content"
                  }
                  size={18}
                />
              </span>
              <div>
                <strong>{MODULE_CONFIG[summary.module].label}</strong>
                <span>
                  {summary.totalRecords} records ·{" "}
                  {summary.period?.granularity ?? "No date granularity"}
                </span>
              </div>
              <small>
                {summary.issueCount.error} error ·{" "}
                {summary.issueCount.warning} warning
              </small>
            </article>
          ))}
        </div>

        {snapshot.quality.issues.length === 0 ? (
          <div className="quality-clear quality-clear--large">
            <Icon name="check" size={20} />
            <span>No quality issues found. Recommendation review is available.</span>
          </div>
        ) : (
          <ul className="snapshot-issue-list">
            {snapshot.quality.issues.map((issue, index) => (
              <li
                key={`${issue.code}-${issue.module}-${index}`}
                className={`snapshot-issue snapshot-issue--${issue.severity}`}
              >
                <span className="snapshot-issue__icon">
                  <Icon
                    name={issue.blocksAnalysis ? "alert" : "shield"}
                    size={18}
                  />
                </span>
                <div>
                  <span>
                    {issue.code} · {issue.module}
                    {issue.field ? ` · ${issue.field}` : ""}
                  </span>
                  <strong>{issue.message}</strong>
                  <p>{issue.suggestedAction}</p>
                  <details>
                    <summary>
                      Review affected sources ({issue.affectedRows.length} groups)
                    </summary>
                    <SourceList references={issue.affectedRows} />
                  </details>
                </div>
                <span
                  className={
                    issue.blocksAnalysis
                      ? "blocking-badge"
                      : "nonblocking-badge"
                  }
                >
                  {issue.blocksAnalysis ? "Blocking" : "Non-blocking"}
                </span>
              </li>
            ))}
          </ul>
        )}

        {!snapshot.quality.hasBlockingIssues &&
          nonBlockingWarnings.length > 0 && (
            <div className="warning-acknowledgement">
              <div>
                <Icon name="alert" size={19} />
                <div>
                  <strong>{nonBlockingWarnings.length} non-blocking warnings</strong>
                  <p>You may continue, but retain these reliability limitations in later reviews.</p>
                </div>
              </div>
              <button
                className="secondary-button"
                type="button"
                disabled={warningsAcknowledged}
                onClick={onAcknowledgeWarnings}
              >
                <Icon name={warningsAcknowledged ? "check" : "shield"} size={16} />
                {warningsAcknowledged ? "Warnings acknowledged" : "Acknowledge and continue"}
              </button>
            </div>
          )}
      </section>

      <MetricSection
        eyebrow="FOLLOWERS METRICS"
        title="Followers"
        description="Totals, growth, and source mix; new followers never estimate total followers."
        metrics={[
          snapshot.metrics.followers.startFollowers,
          snapshot.metrics.followers.endFollowers,
          snapshot.metrics.followers.netGrowth,
          snapshot.metrics.followers.growthRate,
          snapshot.metrics.followers.newFollowersTotal,
          snapshot.metrics.followers.organicShare,
          snapshot.metrics.followers.sponsoredShare,
          snapshot.metrics.followers.demographicTrend,
        ]}
      >
        <div className="snapshot-secondary-grid">
          <SeriesCard series={snapshot.metrics.followers.newFollowersTrend} />
          {snapshot.metrics.followers.demographicTopN.length > 0 ? (
            snapshot.metrics.followers.demographicTopN
              .slice(0, 1)
              .map((ranking) => (
                <RankingCard key={ranking.metricId} ranking={ranking} />
              ))
          ) : (
            <article className="ranking-card">
              <EmptyState
                icon="followers"
                title="Top audience segments unavailable"
                description="Audience dimensions, values, counts, or percentages are missing."
              />
            </article>
          )}
        </div>
      </MetricSection>

      <MetricSection
        eyebrow="VISITORS METRICS"
        title="Visitors"
        description="Aggregate page view and unique visitor metrics using total-based ratios."
        metrics={[
          snapshot.metrics.visitors.pageViewsTotal,
          snapshot.metrics.visitors.uniqueVisitorsTotal,
          snapshot.metrics.visitors.pageViewsPerVisitor,
          snapshot.metrics.visitors.customButtonClicksTotal,
          snapshot.metrics.visitors.periodOverPeriodChange,
        ]}
      >
        <div className="snapshot-secondary-grid">
          <SeriesCard series={snapshot.metrics.visitors.pageViewsTrend} />
          <SeriesCard
            series={snapshot.metrics.visitors.uniqueVisitorsTrend}
          />
        </div>
      </MetricSection>

      <MetricSection
        eyebrow="CONTENT METRICS"
        title="Content"
        description="Prioritizes post-level data and evaluates performance with medians and deterministic engagement inputs."
        metrics={[
          snapshot.metrics.content.publishedCount,
          snapshot.metrics.content.impressionsTotal,
          snapshot.metrics.content.clicksTotal,
          snapshot.metrics.content.reactionsTotal,
          snapshot.metrics.content.commentsTotal,
          snapshot.metrics.content.repostsTotal,
          snapshot.metrics.content.clickThroughRate,
          snapshot.metrics.content.engagementRate,
          snapshot.metrics.content.medianEngagementRate,
        ]}
      >
        <RankingCard ranking={snapshot.metrics.content.contentRanking} />
        <div className="snapshot-secondary-grid">
          <GroupTable
            title="By content type"
            groups={snapshot.metrics.content.byContentType}
          />
          <GroupTable
            title="By publication weekday"
            groups={snapshot.metrics.content.byWeekday}
          />
        </div>
      </MetricSection>

      <MetricSection
        eyebrow="CROSS-MODULE METRICS"
        title="Cross-module observations"
        description="Calculated only for comparable periods and granularity; correlations and proxies are not causation or user conversion."
        metrics={[
          snapshot.metrics.crossModule.visitorFollowerTrendComparison,
          snapshot.metrics.crossModule.visitorToFollowerProxyRatio,
          snapshot.metrics.crossModule.publishingWindowCorrelation,
        ]}
      />

      <section className="insight-gate">
        <div>
          <span
            className={
              insightsAllowed
                ? "insight-gate__icon insight-gate__icon--ready"
                : "insight-gate__icon"
            }
          >
            <Icon name={insightsAllowed ? "check" : "lock"} size={21} />
          </span>
          <div>
            <strong>
              {insightsAllowed
                ? "Snapshot is ready for governed review"
                : snapshot.quality.hasBlockingIssues
                  ? "Blocking issues prevent recommendation review"
                  : "Acknowledge non-blocking warnings first"}
            </strong>
            <p>
              {insightsAllowed
                ? "Later recommendations may interpret only these calculated metrics and may not invent unavailable values."
                : "Resolve data issues or acknowledge warnings before continuing."}
            </p>
          </div>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={!insightsAllowed}
          onClick={() => setPlanningOpen(true)}
        >
          <Icon name="arrow" size={16} />
          Review strategy and 30-day plan
        </button>
      </section>
    </div>
  );
}
