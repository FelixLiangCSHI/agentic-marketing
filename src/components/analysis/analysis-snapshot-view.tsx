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
  reliable: "可靠",
  directional: "方向性",
  unavailable: "不可用",
};

function periodLabel(metric: Metric): string {
  if (!metric.period) {
    return "无可用时间范围";
  }
  return `${metric.period.start} — ${metric.period.end} · ${metric.period.granularity}`;
}

function SourceList({
  references,
}: {
  references: readonly SourceReference[];
}) {
  if (references.length === 0) {
    return <p className="metric-empty-note">没有可用于计算的来源行。</p>;
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
            {reference.sheetName} · 行 {reference.rowStart}
            {reference.rowEnd === reference.rowStart
              ? ""
              : `–${reference.rowEnd}`}
          </span>
          <small>{reference.fields.join(", ") || "记录级来源"}</small>
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
        <summary>这个数字如何计算</summary>
        <div>
          <strong>公式</strong>
          <code>{metric.formula}</code>
          <strong>可靠性依据</strong>
          <ul>
            {metric.reliabilityReasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <strong>数据来源</strong>
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
          title="趋势不可用"
          description={series.reliabilityReasons.join(" ")}
        />
      ) : (
        <div className="snapshot-bars" role="img" aria-label={`${series.label} 柱状趋势`}>
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
          title="排名不可用"
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
                  {item.tied ? "并列 · " : ""}
                  {RELIABILITY_LABELS[item.reliability]}
                </small>
              </div>
              <strong>{item.formattedValue}</strong>
            </li>
          ))}
        </ol>
      )}
      <details className="metric-details">
        <summary>查看排名公式与可靠性</summary>
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
          title={`${title}不可用`}
          description="缺少可用于分组的字段。"
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
              <th>分组</th>
              <th>样本</th>
              <th>Impressions</th>
              <th>CTR</th>
              <th>中位互动率</th>
              <th>可靠性</th>
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
          <h2>确定性指标与数据质量快照</h2>
          <p>
            所有数字由程序从统一模型计算。Snapshot 记录公式、时间范围、来源和可靠性，后续 Agent 只负责解释。
          </p>
        </div>
        <div className="snapshot-hero__actions">
          <button className="secondary-button" type="button" onClick={onBack}>
            返回字段确认
          </button>
          <button className="secondary-button" type="button" onClick={onDownload}>
            <Icon name="download" size={16} />
            下载 Snapshot JSON
          </button>
        </div>
      </section>

      <section className="quality-panel">
        <header className="quality-panel__header">
          <div>
            <span className="section-label">DATA QUALITY</span>
            <h2>数据质量摘要</h2>
            <p>
              {snapshot.analysisPeriod
                ? `${snapshot.analysisPeriod.start} — ${snapshot.analysisPeriod.end}`
                : "没有三个模块共同的可用时间范围"}
            </p>
          </div>
          <div className="quality-scorecards">
            <div className="quality-score quality-score--error">
              <strong>{snapshot.quality.blockingIssueCount}</strong>
              <span>阻断问题</span>
            </div>
            <div className="quality-score quality-score--warning">
              <strong>{snapshot.quality.warningCount}</strong>
              <span>警告</span>
            </div>
            <div className="quality-score">
              <strong>
                {Object.values(snapshot.quality.moduleSummaries).reduce(
                  (sum, summary) => sum + summary.totalRecords,
                  0,
                )}
              </strong>
              <span>标准记录</span>
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
                  {summary.totalRecords} 条 ·{" "}
                  {summary.period?.granularity ?? "无日期粒度"}
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
            <span>未发现质量问题，可以进入后续洞察。</span>
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
                      查看受影响来源（{issue.affectedRows.length} 组）
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
                  {issue.blocksAnalysis ? "阻断" : "非阻断"}
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
                  <strong>有 {nonBlockingWarnings.length} 项非阻断警告</strong>
                  <p>可以继续，但应在后续 Agent 解释中保留这些可靠性限制。</p>
                </div>
              </div>
              <button
                className="secondary-button"
                type="button"
                disabled={warningsAcknowledged}
                onClick={onAcknowledgeWarnings}
              >
                <Icon name={warningsAcknowledged ? "check" : "shield"} size={16} />
                {warningsAcknowledged ? "已确认警告" : "确认并继续"}
              </button>
            </div>
          )}
      </section>

      <MetricSection
        eyebrow="FOLLOWERS METRICS"
        title="Followers"
        description="总量、增长与来源结构；缺少 totalFollowers 时不会用新增量估算存量。"
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
                title="画像 Top N 不可用"
                description="缺少 demographicDimension、demographicValue 与计数或占比。"
              />
            </article>
          )}
        </div>
      </MetricSection>

      <MetricSection
        eyebrow="VISITORS METRICS"
        title="Visitors"
        description="浏览与独立访客聚合指标；Page Views per Visitor 使用总量比值。"
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
        description="优先使用逐帖数据，基于中位数与确定性互动组成项评估表现。"
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
            title="按内容类型"
            groups={snapshot.metrics.content.byContentType}
          />
          <GroupTable
            title="按发布时间（星期）"
            groups={snapshot.metrics.content.byWeekday}
          />
        </div>
      </MetricSection>

      <MetricSection
        eyebrow="CROSS-MODULE METRICS"
        title="跨模块观察"
        description="只在时间范围与粒度可比时计算；相关性和代理比率均不得解释为因果或真实用户转化。"
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
                ? "Snapshot 可安全交给后续 Agent"
                : snapshot.quality.hasBlockingIssues
                  ? "存在阻断问题，不能进入 AI 洞察"
                  : "请先确认非阻断警告"}
            </strong>
            <p>
              {insightsAllowed
                ? "Agent 只能解释这些已计算指标，不应重新计算或补造 unavailable 数值。"
                : "修复数据或完成警告确认后再继续。"}
            </p>
          </div>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={!insightsAllowed}
          onClick={() => setPlanningOpen(true)}
        >
          <Icon name="sparkles" size={16} />
          进入策略与 30 天计划
        </button>
      </section>
    </div>
  );
}
