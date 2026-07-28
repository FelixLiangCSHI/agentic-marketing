"use client";

import { useState } from "react";

import { Icon } from "@/components/ui/icon";
import type {
  ActionPlan,
  ContentCalendarItem,
} from "@/domain/action-plan";
import type {
  EvidenceInsight,
  StrategyRecommendation,
} from "@/domain/strategy";

const CHANNEL_LABELS = {
  linkedin_page: "LinkedIn Page",
  linkedin_profile: "LinkedIn Profile",
} as const;

interface ActionPlanReportProps {
  plan: ActionPlan;
  approvedInsights: EvidenceInsight[];
  approvedStrategies: StrategyRecommendation[];
  canUndo: boolean;
  onUndo: () => void;
  onUpdateItem: (
    itemId: string,
    patch: Partial<
      Pick<
        ContentCalendarItem,
        "topic" | "targetAudience" | "callToAction" | "status"
      >
    >,
  ) => void;
  onConfirmPlan: () => void;
  onDownload: () => void;
}

function PlanItemCard({
  item,
  strategy,
  onUpdate,
}: {
  item: ContentCalendarItem;
  strategy: StrategyRecommendation | undefined;
  onUpdate: ActionPlanReportProps["onUpdateItem"];
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    topic: item.topic,
    targetAudience: item.targetAudience,
    callToAction: item.callToAction,
  });

  function startEditing() {
    setDraft({
      topic: item.topic,
      targetAudience: item.targetAudience,
      callToAction: item.callToAction,
    });
    setEditing(true);
  }

  return (
    <article className={`plan-item plan-item--${item.status}`}>
      <header>
        <div>
          <span>
            {item.date} {item.scheduledTime}（{item.timeZone}）
          </span>
          <strong>{item.topic}</strong>
        </div>
        <span className={`plan-status plan-status--${item.status}`}>
          {item.status === "ai_draft"
            ? "AI 初稿"
            : item.status === "confirmed"
              ? "用户已确认"
              : "已拒绝"}
        </span>
      </header>
      {editing ? (
        <div className="plan-item__editor">
          <label>
            主题
            <input
              value={draft.topic}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  topic: event.target.value,
                }))
              }
            />
          </label>
          <label>
            目标受众
            <input
              value={draft.targetAudience}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  targetAudience: event.target.value,
                }))
              }
            />
          </label>
          <label>
            CTA
            <input
              value={draft.callToAction}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  callToAction: event.target.value,
                }))
              }
            />
          </label>
          <div>
            <button
              className="secondary-button secondary-button--small"
              type="button"
              onClick={() => setEditing(false)}
            >
              取消
            </button>
            <button
              className="primary-button"
              type="button"
              disabled={
                !draft.topic.trim() ||
                !draft.targetAudience.trim() ||
                !draft.callToAction.trim()
              }
              onClick={() => {
                onUpdate(item.itemId, { ...draft, status: "ai_draft" });
                setEditing(false);
              }}
            >
              保存修改
            </button>
          </div>
        </div>
      ) : (
        <>
          <dl className="plan-item__details">
            <div>
              <dt>Post objective</dt>
              <dd>{strategy?.objective ?? "Build qualified audience engagement"}</dd>
            </div>
            <div>
              <dt>Content angle</dt>
              <dd>{item.coreMessage}</dd>
            </div>
            <div>
              <dt>Channel</dt>
              <dd>{CHANNEL_LABELS[item.channel]}</dd>
            </div>
            <div>
              <dt>Target audience</dt>
              <dd>{item.targetAudience}</dd>
            </div>
            <div>
              <dt>CTA</dt>
              <dd>{item.callToAction}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{item.status === "confirmed" ? "Approved" : item.status === "rejected" ? "Rejected" : "Human approval required"}</dd>
            </div>
          </dl>
          {item.isExperiment && item.experiment && (
            <div className="experiment-card">
              <span>
                <Icon name="sparkles" size={14} />
                实验
              </span>
              <strong>{item.experiment.hypothesis}</strong>
              <p>{item.experiment.successCriteria}</p>
              <small>复盘：{item.experiment.reviewDate}</small>
            </div>
          )}
          <details className="plan-evidence">
            <summary>查看策略与衡量证据</summary>
            <div>
              <strong>
                {strategy?.title ?? `策略 ${item.strategyId}`}
              </strong>
              <span>{strategy?.rationale}</span>
              <code>{item.measurementMetricIds.join(", ")}</code>
              <small>负责人：{item.ownerPlaceholder}</small>
            </div>
          </details>
          <div className="plan-item__actions">
            <button
              className="secondary-button secondary-button--small"
              type="button"
              onClick={startEditing}
            >
              修改
            </button>
            <button
              className="secondary-button secondary-button--small"
              type="button"
              disabled={item.status === "rejected"}
              onClick={() => onUpdate(item.itemId, { status: "rejected" })}
            >
              拒绝
            </button>
            <button
              className="primary-button"
              type="button"
              disabled={item.status === "confirmed"}
              onClick={() => onUpdate(item.itemId, { status: "confirmed" })}
            >
              <Icon name="check" size={14} />
              接受
            </button>
          </div>
        </>
      )}
    </article>
  );
}

function DraftCard({
  item,
  strategy,
}: {
  item: ContentCalendarItem;
  strategy: StrategyRecommendation | undefined;
}) {
  const campaignHashtag = item.campaignTag
    ? `#${item.campaignTag.replace(/[^a-zA-Z0-9\u4e00-\u9fff]/g, "")}`
    : "#LinkedInMarketing";

  return (
    <article className="buffer-draft-card">
      <header>
        <div>
          <span>{item.date} · {CHANNEL_LABELS[item.channel]}</span>
          <h3>{item.topic}</h3>
        </div>
        <span className="draft-ready-status">
          <Icon name="check" size={13} />
          Draft Ready
        </span>
      </header>
      <div className="draft-field">
        <span>Body</span>
        <p>{item.postText}</p>
      </div>
      <dl>
        <div><dt>Hashtags</dt><dd>{campaignHashtag} #B2BMarketing #ContentStrategy</dd></div>
        <div><dt>Media suggestion</dt><dd>{item.mediaRequirement ?? "Text-led post with a branded insight card"}</dd></div>
        <div><dt>Professional terminology</dt><dd>{strategy?.title ?? item.contentFormat} · {item.coreMessage}</dd></div>
        <div><dt>Buffer Status</dt><dd>Ready for Buffer</dd></div>
      </dl>
    </article>
  );
}

function EvidenceSummary({
  title,
  items,
}: {
  title: string;
  items: EvidenceInsight[];
}) {
  return (
    <section className="report-evidence-section">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p>没有已批准的相关洞察。</p>
      ) : (
        <ul>
          {items.map((insight) => (
            <li key={insight.insightId}>
              <strong>{insight.title}</strong>
              <span>{insight.statement}</span>
              <details>
                <summary>证据与限制</summary>
                <p>{insight.possibleMeaning}</p>
                <code>
                  {insight.evidence
                    .map((reference) => reference.metricId)
                    .join(", ")}
                </code>
                <small>{insight.limitations.join(" ")}</small>
              </details>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ActionPlanReport({
  plan,
  approvedInsights,
  approvedStrategies,
  canUndo,
  onUndo,
  onUpdateItem,
  onConfirmPlan,
  onDownload,
}: ActionPlanReportProps) {
  const [view, setView] = useState<"list" | "calendar">("list");
  const contentInsights = approvedInsights.filter(
    (item) => item.category === "content",
  );
  const audienceInsights = approvedInsights.filter(
    (item) => item.category === "audience",
  );

  return (
    <div className="action-plan-report">
      <section className="report-hero">
        <div>
          <span className="section-label">STEP 3 · 30-DAY CONTENT CALENDAR</span>
          <h2>Campaign calendar and approval queue</h2>
          <p>{plan.executiveSummary}</p>
        </div>
        <div className="report-hero__actions">
          <span className={`plan-status plan-status--${plan.status}`}>
            {plan.status === "ai_draft" ? "Human Approval Required" : "Calendar Approved"}
          </span>
          <button
            className="secondary-button"
            type="button"
            disabled={!canUndo}
            onClick={onUndo}
          >
            <Icon name="refresh" size={15} />
            撤销最近修改
          </button>
          <button className="secondary-button" type="button" onClick={onDownload}>
            <Icon name="download" size={15} />
            下载计划 JSON
          </button>
          <button
            className="primary-button"
            type="button"
            disabled={plan.status === "user_confirmed"}
            onClick={onConfirmPlan}
          >
            <Icon name="check" size={15} />
            Approve calendar
          </button>
        </div>
      </section>

      <dl className="report-metadata">
        <div>
          <dt>生成时间</dt>
          <dd>{new Date(plan.generatedAt).toLocaleString("zh-CN")}</dd>
        </div>
        <div>
          <dt>分析范围</dt>
          <dd>
            {plan.analysisPeriod
              ? `${plan.analysisPeriod.start} — ${plan.analysisPeriod.end}`
              : "无共同时间范围"}
          </dd>
        </div>
        <div>
          <dt>Prompt 版本</dt>
          <dd>{plan.promptVersion}</dd>
        </div>
        <div>
          <dt>Snapshot</dt>
          <dd>{plan.snapshotId}</dd>
        </div>
        <div>
          <dt>数据模块</dt>
          <dd>{plan.sourceModules.join("、")}</dd>
        </div>
      </dl>

      <section className="report-risks">
        <div>
          <Icon name="alert" size={21} />
          <div>
            <span className="section-label">RISKS & LIMITATIONS</span>
            <h3>风险与数据限制</h3>
          </div>
        </div>
        <ul>
          {plan.risksAndLimitations.map((risk) => (
            <li key={risk}>{risk}</li>
          ))}
        </ul>
      </section>

      <section className="report-summary-grid">
        <EvidenceSummary title="Audience Insights" items={audienceInsights} />
        <EvidenceSummary title="Content Insights" items={contentInsights} />
        <section className="report-evidence-section">
          <h3>Recommendations</h3>
          <ul>
            {approvedStrategies.map((strategy) => (
              <li key={strategy.strategyId}>
                <strong>{strategy.title}</strong>
                <span>{strategy.objective}</span>
                <details>
                  <summary>引用关系</summary>
                  <code>{strategy.metricIds.join(", ")}</code>
                  <small>
                    洞察：{strategy.insightIds.join(", ")}
                  </small>
                </details>
              </li>
            ))}
          </ul>
        </section>
      </section>

      <section className="four-week-plan">
        <div className="section-heading section-heading--large">
          <div>
            <span className="section-label">FOUR-WEEK PLAN</span>
            <h2>四周目标与任务</h2>
            <p>
              {plan.startDate} — {plan.endDate} · {plan.preferences.timeZone}
            </p>
          </div>
        </div>
        <div className="week-plan-grid">
          {plan.fourWeekPlan.map((week) => (
            <article key={week.weekNumber}>
              <span>WEEK {week.weekNumber}</span>
              <h3>{week.objective}</h3>
              <small>
                {week.dateRange.start} — {week.dateRange.end}
              </small>
              <ul>
                {week.tasks.map((task) => (
                  <li key={task.taskId}>
                    <Icon name="check" size={13} />
                    <span>
                      {task.title}
                      <small>{task.dueDate}</small>
                    </span>
                  </li>
                ))}
              </ul>
              <details>
                <summary>复盘与依赖</summary>
                <p>{week.reviewAction}</p>
                <code>{week.kpiMetricIds.join(", ")}</code>
              </details>
            </article>
          ))}
        </div>
      </section>

      <section className="content-calendar-section">
        <div className="section-heading section-heading--large">
          <div>
            <span className="section-label">STEP 3 · CONTENT CALENDAR</span>
            <h2>30-day publishing schedule</h2>
            <p>
              Date · Post objective · Topic · Content angle · Target audience · CTA · Status
            </p>
          </div>
          <div className="view-toggle" role="group" aria-label="日历视图">
            <button
              type="button"
              className={view === "list" ? "is-active" : ""}
              onClick={() => setView("list")}
            >
              列表
            </button>
            <button
              type="button"
              className={view === "calendar" ? "is-active" : ""}
              onClick={() => setView("calendar")}
            >
              日历
            </button>
          </div>
        </div>

        {view === "list" ? (
          <div className="plan-item-list">
            {plan.contentCalendar.map((item) => (
              <PlanItemCard
                key={item.itemId}
                item={item}
                strategy={approvedStrategies.find(
                  (strategy) => strategy.strategyId === item.strategyId,
                )}
                onUpdate={onUpdateItem}
              />
            ))}
          </div>
        ) : (
          <div className="calendar-grid">
            {plan.fourWeekPlan.map((week) => (
              <section key={week.weekNumber}>
                <header>
                  <strong>第 {week.weekNumber} 周</strong>
                  <span>{week.dateRange.start}</span>
                </header>
                {week.contentItems.map((itemId) => {
                  const item = plan.contentCalendar.find(
                    (candidate) => candidate.itemId === itemId,
                  );
                  return item ? (
                    <article key={item.itemId}>
                      <span>{item.date.slice(5)}</span>
                      <strong>{item.topic}</strong>
                      <small>
                        {item.contentFormat}
                        {item.isExperiment ? " · 实验" : ""}
                      </small>
                    </article>
                  ) : null;
                })}
              </section>
            ))}
          </div>
        )}
      </section>

      <section className="draft-generation-section">
        <div className="workflow-block__header">
          <span className="workflow-block__step">STEP 4</span>
          <div>
            <span className="section-label">DRAFT GENERATION</span>
            <h2>Buffer-ready LinkedIn drafts</h2>
            <p>Generated only after the 30-day calendar is approved.</p>
          </div>
          <span className={`workflow-state ${plan.status === "user_confirmed" ? "workflow-state--complete" : "workflow-state--approval"}`}>
            <Icon name={plan.status === "user_confirmed" ? "check" : "lock"} size={14} />
            {plan.status === "user_confirmed" ? "Drafts ready" : "Approval checkpoint"}
          </span>
        </div>
        {plan.status === "user_confirmed" ? (
          <div className="buffer-draft-grid">
            {plan.contentCalendar
              .filter((item) => item.status !== "rejected")
              .map((item) => (
                <DraftCard
                  key={item.itemId}
                  item={item}
                  strategy={approvedStrategies.find((strategy) => strategy.strategyId === item.strategyId)}
                />
              ))}
          </div>
        ) : (
          <div className="draft-approval-gate">
            <Icon name="lock" size={20} />
            <div>
              <strong>Human Approval Required</strong>
              <p>Approve the calendar to unlock title, body, hashtags, media guidance and Buffer handoff status.</p>
            </div>
          </div>
        )}
      </section>

      <section className="report-bottom-grid">
        <article>
          <span className="section-label">ASSUMPTIONS</span>
          <h3>执行假设</h3>
          <ul>
            {plan.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </article>
        <article>
          <span className="section-label">KPI REVIEW</span>
          <h3>KPI 复盘</h3>
          <ul>
            {plan.kpiReviewPlan.map((review) => (
              <li key={review.reviewId}>
                <strong>{review.reviewDate}</strong>
                <span>{review.action}</span>
                <code>{review.metricIds.join(", ")}</code>
              </li>
            ))}
          </ul>
        </article>
        <article>
          <span className="section-label">NEXT IMPORT</span>
          <h3>下次导入问题</h3>
          <ul>
            {plan.nextImportQuestions.map((question) => (
              <li key={question}>{question}</li>
            ))}
          </ul>
        </article>
      </section>
    </div>
  );
}
