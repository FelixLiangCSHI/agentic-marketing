"use client";

import {
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";

import {
  ActionPlanAgentError,
  confirmActionPlan,
  defaultPlanStartDate,
  localDateInTimeZone,
  reviseActionPlanSchedule,
  reviseCalendarItem,
  runActionPlanAgent,
} from "@/agents/action-plan-agent";
import { generateEvidenceStrategyBundle } from "@/agents/evidence-strategy-agent";
import { ActionPlanReport } from "@/components/analysis/action-plan-report";
import { EvidenceChatPanel } from "@/components/analysis/evidence-chat-panel";
import { Icon } from "@/components/ui/icon";
import type {
  ActionPlanInput,
  ActionPlanPreferences,
  ContentCalendarItem,
} from "@/domain/action-plan";
import type { AnalysisSnapshot } from "@/domain/analysis";
import type { SuggestedPlanChange } from "@/domain/chat";
import type {
  ApprovalStatus,
  BusinessGoal,
  EvidenceInsight,
  StrategyRecommendation,
} from "@/domain/strategy";
import {
  createInitialPlanEditorState,
  planEditorReducer,
} from "@/state/plan-editor-reducer";

interface StrategyPlanningWorkspaceProps {
  snapshot: AnalysisSnapshot;
  onBack: () => void;
}

type GenerationStatus =
  | "idle"
  | "generating"
  | "completed"
  | "cancelled"
  | "error";

const STATUS_LABELS: Record<ApprovalStatus, string> = {
  draft: "AI 初稿",
  approved: "用户已批准",
  rejected: "用户已拒绝",
};

function downloadPlan(plan: unknown) {
  const blob = new Blob([JSON.stringify(plan, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "linkedin-30-day-action-plan.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function EvidenceInsightCard({
  insight,
  onStatus,
}: {
  insight: EvidenceInsight;
  onStatus: (status: ApprovalStatus) => void;
}) {
  return (
    <article className={`approval-card approval-card--${insight.approvalStatus}`}>
      <header>
        <div>
          <span>{insight.category}</span>
          <h3>{insight.title}</h3>
        </div>
        <span className={`approval-status approval-status--${insight.approvalStatus}`}>
          {STATUS_LABELS[insight.approvalStatus]}
        </span>
      </header>
      <p>{insight.statement}</p>
      <div className="evidence-language">
        <div>
          <strong>可能意味着</strong>
          <span>{insight.possibleMeaning}</span>
        </div>
        <div>
          <strong>建议验证</strong>
          <span>{insight.suggestedValidation}</span>
        </div>
      </div>
      <details className="approval-evidence">
        <summary>查看 Metric 证据与限制</summary>
        <ul>
          {insight.evidence.map((reference) => (
            <li key={reference.metricId}>
              <strong>{reference.metricId}</strong>
              <span>{reference.formattedValue}</span>
              <small>
                {reference.period
                  ? `${reference.period.start} — ${reference.period.end}`
                  : "无可用时间范围"}{" "}
                · {reference.sourceModules.join("、")}
              </small>
            </li>
          ))}
        </ul>
        <p>{insight.limitations.join(" ")}</p>
      </details>
      <div className="approval-card__actions">
        <button
          className="secondary-button secondary-button--small"
          type="button"
          disabled={insight.approvalStatus === "rejected"}
          onClick={() => onStatus("rejected")}
        >
          拒绝
        </button>
        <button
          className="primary-button"
          type="button"
          disabled={insight.approvalStatus === "approved"}
          onClick={() => onStatus("approved")}
        >
          <Icon name="check" size={14} />
          批准洞察
        </button>
      </div>
    </article>
  );
}

function StrategyCard({
  strategy,
  canApprove,
  onChange,
  onStatus,
}: {
  strategy: StrategyRecommendation;
  canApprove: boolean;
  onChange: (patch: Partial<StrategyRecommendation>) => void;
  onStatus: (status: ApprovalStatus) => void;
}) {
  return (
    <article className={`approval-card approval-card--${strategy.approvalStatus}`}>
      <header>
        <div>
          <span>strategy</span>
          <h3>{strategy.title}</h3>
        </div>
        <span className={`approval-status approval-status--${strategy.approvalStatus}`}>
          {STATUS_LABELS[strategy.approvalStatus]}
        </span>
      </header>
      <label className="strategy-edit-field">
        策略目标
        <textarea
          value={strategy.objective}
          rows={3}
          onChange={(event) =>
            onChange({
              objective: event.target.value,
              editedByUser: true,
              approvalStatus: "draft",
            })
          }
        />
      </label>
      <p>{strategy.rationale}</p>
      <ul className="strategy-actions">
        {strategy.actions.map((action) => (
          <li key={action}>
            <Icon name="arrow" size={13} />
            {action}
          </li>
        ))}
      </ul>
      <details className="approval-evidence">
        <summary>查看洞察与 Metric 引用</summary>
        <code>{strategy.insightIds.join(", ")}</code>
        <code>{strategy.metricIds.join(", ")}</code>
      </details>
      {!canApprove && (
        <p className="approval-dependency">
          <Icon name="lock" size={14} />
          必须先批准该策略引用的全部洞察。
        </p>
      )}
      <div className="approval-card__actions">
        <button
          className="secondary-button secondary-button--small"
          type="button"
          disabled={strategy.approvalStatus === "rejected"}
          onClick={() => onStatus("rejected")}
        >
          拒绝
        </button>
        <button
          className="primary-button"
          type="button"
          disabled={!canApprove || strategy.approvalStatus === "approved"}
          onClick={() => onStatus("approved")}
        >
          <Icon name="check" size={14} />
          批准策略
        </button>
      </div>
    </article>
  );
}

export function StrategyPlanningWorkspace({
  snapshot,
  onBack,
}: StrategyPlanningWorkspaceProps) {
  const bundle = useMemo(
    () => generateEvidenceStrategyBundle(snapshot),
    [snapshot],
  );
  const [insights, setInsights] = useState(bundle.insights);
  const [strategies, setStrategies] = useState(bundle.strategies);
  const [goalText, setGoalText] = useState(
    "建立可持续、可复盘的 LinkedIn 内容与受众运营节奏",
  );
  const [businessGoal, setBusinessGoal] = useState<BusinessGoal | null>(null);
  const initialTimeZone =
    Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Shanghai";
  const [preferences, setPreferences] = useState<ActionPlanPreferences>({
    startDate: defaultPlanStartDate(initialTimeZone),
    timeZone: initialTimeZone,
    postsPerWeek: 2,
    teamSize: null,
    contentResources: [],
    targetMarket: null,
    focusAudience: "LinkedIn 聚合受众（待用户确认）",
  });
  const [resourcesText, setResourcesText] = useState("");
  const [planState, dispatchPlan] = useReducer(
    planEditorReducer,
    undefined,
    createInitialPlanEditorState,
  );
  const [generationStatus, setGenerationStatus] =
    useState<GenerationStatus>("idle");
  const [generationMessage, setGenerationMessage] = useState("");
  const [preferencesDirty, setPreferencesDirty] = useState(false);
  const generationController = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      generationController.current?.abort();
    },
    [],
  );

  const approvedInsights = insights.filter(
    (item) => item.approvalStatus === "approved",
  );
  const approvedInsightIds = new Set(
    approvedInsights.map((item) => item.insightId),
  );
  const approvedStrategies = strategies.filter(
    (item) =>
      item.approvalStatus === "approved" &&
      item.insightIds.every((insightId) => approvedInsightIds.has(insightId)),
  );
  const localToday =
    localDateInTimeZone(new Date(), preferences.timeZone) ??
    new Date().toISOString().slice(0, 10);

  function clearPlanForEvidenceChange() {
    generationController.current?.abort();
    generationController.current = null;
    dispatchPlan({ type: "CLEAR_PLAN" });
    setGenerationStatus("idle");
    setGenerationMessage("");
    setPreferencesDirty(false);
  }

  function setInsightStatus(insightId: string, status: ApprovalStatus) {
    clearPlanForEvidenceChange();
    setInsights((current) =>
      current.map((insight) =>
        insight.insightId === insightId
          ? { ...insight, approvalStatus: status }
          : insight,
      ),
    );
    if (status !== "approved") {
      setStrategies((current) =>
        current.map((strategy) =>
          strategy.insightIds.includes(insightId)
            ? { ...strategy, approvalStatus: "draft" }
            : strategy,
        ),
      );
    }
  }

  function updateStrategy(
    strategyId: string,
    patch: Partial<StrategyRecommendation>,
  ) {
    clearPlanForEvidenceChange();
    setStrategies((current) =>
      current.map((strategy) =>
        strategy.strategyId === strategyId
          ? { ...strategy, ...patch }
          : strategy,
      ),
    );
  }

  function setStrategyStatus(strategyId: string, status: ApprovalStatus) {
    updateStrategy(strategyId, { approvalStatus: status });
  }

  function updatePreferences(patch: Partial<ActionPlanPreferences>) {
    setPreferences((current) => ({ ...current, ...patch }));
    if (planState.current) {
      setPreferencesDirty(true);
    }
  }

  function actionInput(
    selectedPreferences: ActionPlanPreferences = preferences,
  ): ActionPlanInput | null {
    if (!businessGoal) {
      return null;
    }
    return {
      snapshot,
      businessGoal,
      approvedInsights,
      approvedStrategies,
      preferences: selectedPreferences,
    };
  }

  async function generatePlan() {
    const input = actionInput();
    if (!input) {
      setGenerationStatus("error");
      setGenerationMessage("请先确认业务目标。");
      return;
    }
    generationController.current?.abort();
    const controller = new AbortController();
    generationController.current = controller;
    setGenerationStatus("generating");
    setGenerationMessage("正在校验引用并生成四周计划…");
    try {
      const plan = await runActionPlanAgent(input, {
        signal: controller.signal,
      });
      if (generationController.current !== controller) {
        return;
      }
      dispatchPlan({ type: "LOAD_PLAN", plan });
      setGenerationStatus("completed");
      setGenerationMessage("计划结构与引用完整性校验通过。");
      setPreferencesDirty(false);
    } catch (reason) {
      if (generationController.current !== controller) {
        return;
      }
      if (
        reason instanceof ActionPlanAgentError &&
        reason.code === "GENERATION_CANCELLED"
      ) {
        setGenerationStatus("cancelled");
        setGenerationMessage("已取消生成；可以保留当前审批并重试。");
      } else {
        setGenerationStatus("error");
        setGenerationMessage(
          reason instanceof Error ? reason.message : "计划生成失败，请重试。",
        );
      }
    } finally {
      if (generationController.current === controller) {
        generationController.current = null;
      }
    }
  }

  function cancelGeneration() {
    generationController.current?.abort();
  }

  function applyPreferenceRevision(
    nextPreferences: ActionPlanPreferences = preferences,
  ) {
    if (!planState.current) {
      return;
    }
    const input = actionInput(nextPreferences);
    if (!input) {
      return;
    }
    try {
      const revised = reviseActionPlanSchedule(
        planState.current,
        input,
        nextPreferences,
      );
      dispatchPlan({ type: "APPLY_REVISION", plan: revised });
      setGenerationStatus("completed");
      setGenerationMessage(
        "仅更新四周排期、内容日历和 KPI 复盘；Snapshot 与洞察未重跑。",
      );
      setPreferencesDirty(false);
    } catch (reason) {
      setGenerationStatus("error");
      setGenerationMessage(
        reason instanceof Error ? reason.message : "计划设置更新失败。",
      );
    }
  }

  function applyChatChange(change: SuggestedPlanChange) {
    const nextPreferences =
      change.type === "posts_per_week"
        ? { ...preferences, postsPerWeek: change.postsPerWeek }
        : { ...preferences, focusAudience: change.focusAudience };
    setPreferences(nextPreferences);
    if (planState.current) {
      applyPreferenceRevision(nextPreferences);
    }
  }

  function updateCalendarItem(
    itemId: string,
    patch: Partial<
      Pick<
        ContentCalendarItem,
        "topic" | "targetAudience" | "callToAction" | "status"
      >
    >,
  ) {
    if (!planState.current) {
      return;
    }
    dispatchPlan({
      type: "APPLY_REVISION",
      plan: reviseCalendarItem(planState.current, itemId, patch),
    });
  }

  function confirmCurrentPlan() {
    if (!planState.current) {
      return;
    }
    dispatchPlan({
      type: "APPLY_REVISION",
      plan: confirmActionPlan(planState.current),
    });
  }

  const canGenerate =
    businessGoal !== null &&
    approvedInsights.length > 0 &&
    approvedStrategies.length > 0 &&
    generationStatus !== "generating";

  return (
    <div className="planning-workspace">
      <section className="planning-hero">
        <div>
          <button className="text-button" type="button" onClick={onBack}>
            <Icon name="chevron" size={15} />
            返回 Snapshot
          </button>
          <span className="section-label">STRATEGY → EXECUTION</span>
          <h2>从已批准证据生成 30 天计划</h2>
          <p>
            未批准洞察和策略不会进入计划。所有 KPI 只引用当前可计算指标或明确标记为“下次采集”的指标。
          </p>
        </div>
        <dl>
          <div>
            <dt>Snapshot ID</dt>
            <dd>{snapshot.snapshotId}</dd>
          </div>
          <div>
            <dt>Prompt</dt>
            <dd>{bundle.promptVersion}</dd>
          </div>
          <div>
            <dt>模式</dt>
            <dd>Deterministic Mock</dd>
          </div>
        </dl>
      </section>

      <section className="planning-limits">
        <Icon name="shield" size={21} />
        <div>
          <strong>数据与建议边界始终生效</strong>
          <p>
            聚合数据不能识别匿名访客或具体关注者；Proxy 不是转化率；相关性不代表因果；计划不会承诺固定增长。
          </p>
        </div>
      </section>

      <section className="planning-config">
        <div className="section-heading section-heading--large">
          <div>
            <span className="section-label">CONFIRMED INPUTS</span>
            <h2>业务目标与执行约束</h2>
            <p>团队和资源留空时使用清晰占位符，不虚构员工。</p>
          </div>
          {businessGoal && (
            <span className="approval-status approval-status--approved">
              目标已确认
            </span>
          )}
        </div>
        <div className="planning-config-grid">
          <label className="planning-field planning-field--wide">
            业务目标
            <input
              value={goalText}
              maxLength={180}
              onChange={(event) => {
                setGoalText(event.target.value);
                setBusinessGoal(null);
                clearPlanForEvidenceChange();
              }}
            />
            <small>不填写具体增长承诺；如需数值目标，应明确标记为用户设定。</small>
          </label>
          <button
            className="secondary-button planning-confirm-goal"
            type="button"
            disabled={!goalText.trim() || businessGoal !== null}
            onClick={() =>
              setBusinessGoal({
                goalId: `goal-${snapshot.snapshotId}`,
                statement: goalText.trim(),
                confirmed: true,
                confirmedAt: new Date().toISOString(),
              })
            }
          >
            <Icon name="check" size={15} />
            {businessGoal ? "业务目标已确认" : "确认业务目标"}
          </button>
          <label className="planning-field">
            计划开始日期
            <input
              type="date"
              min={localToday}
              value={preferences.startDate}
              onChange={(event) =>
                updatePreferences({ startDate: event.target.value })
              }
            />
          </label>
          <label className="planning-field">
            用户时区
            <select
              value={preferences.timeZone}
              onChange={(event) =>
                updatePreferences({ timeZone: event.target.value })
              }
            >
              <option value="Asia/Shanghai">Asia/Shanghai</option>
              <option value="Asia/Singapore">Asia/Singapore</option>
              <option value="Europe/London">Europe/London</option>
              <option value="America/New_York">America/New_York</option>
              <option value="America/Los_Angeles">America/Los_Angeles</option>
              {![
                "Asia/Shanghai",
                "Asia/Singapore",
                "Europe/London",
                "America/New_York",
                "America/Los_Angeles",
              ].includes(preferences.timeZone) && (
                <option value={preferences.timeZone}>
                  {preferences.timeZone}
                </option>
              )}
            </select>
          </label>
          <label className="planning-field">
            每周发帖能力
            <select
              value={preferences.postsPerWeek}
              onChange={(event) =>
                updatePreferences({
                  postsPerWeek: Number(event.target.value),
                })
              }
            >
              {[1, 2, 3, 4, 5].map((value) => (
                <option key={value} value={value}>
                  {value} 条 / 周
                </option>
              ))}
            </select>
          </label>
          <label className="planning-field">
            团队规模（可选）
            <input
              type="number"
              min={1}
              max={99}
              value={preferences.teamSize ?? ""}
              placeholder="未提供"
              onChange={(event) =>
                updatePreferences({
                  teamSize: event.target.value
                    ? Number(event.target.value)
                    : null,
                })
              }
            />
          </label>
          <label className="planning-field">
            重点受众
            <input
              value={preferences.focusAudience}
              onChange={(event) =>
                updatePreferences({ focusAudience: event.target.value })
              }
            />
          </label>
          <label className="planning-field">
            目标市场（可选）
            <input
              value={preferences.targetMarket ?? ""}
              placeholder="例如 APAC"
              onChange={(event) =>
                updatePreferences({
                  targetMarket: event.target.value || null,
                })
              }
            />
          </label>
          <label className="planning-field planning-field--wide">
            内容资源（可选，逗号分隔）
            <input
              value={resourcesText}
              placeholder="文案、设计、视频"
              onChange={(event) => {
                const value = event.target.value;
                setResourcesText(value);
                updatePreferences({
                  contentResources: value
                    .split(/[,，]/)
                    .map((item) => item.trim())
                    .filter(Boolean),
                });
              }}
            />
          </label>
        </div>
        {planState.current && (
          <div className="planning-config__apply">
            <span>
              {preferencesDirty
                ? "执行设置已修改，尚未应用到当前计划。"
                : "当前计划已使用这些执行设置。"}
            </span>
            <button
              className="secondary-button"
              type="button"
              disabled={!preferencesDirty}
              onClick={() => applyPreferenceRevision()}
            >
              仅更新受影响排期
            </button>
          </div>
        )}
      </section>

      <section className="approval-section">
        <div className="section-heading section-heading--large">
          <div>
            <span className="section-label">AUDIENCE & CONTENT</span>
            <h2>审批洞察</h2>
            <p>每条洞察保留 Metric、时间和来源引用。</p>
          </div>
          <span>{approvedInsights.length} 条已批准</span>
        </div>
        <div className="approval-grid">
          {insights.map((insight) => (
            <EvidenceInsightCard
              key={insight.insightId}
              insight={insight}
              onStatus={(status) =>
                setInsightStatus(insight.insightId, status)
              }
            />
          ))}
        </div>
      </section>

      <section className="approval-section">
        <div className="section-heading section-heading--large">
          <div>
            <span className="section-label">RECOMMENDATIONS</span>
            <h2>审批与修改策略</h2>
            <p>策略修改后恢复为 AI 初稿，必须重新批准。</p>
          </div>
          <span>{approvedStrategies.length} 条已批准</span>
        </div>
        <div className="approval-grid approval-grid--strategies">
          {strategies.map((strategy) => (
            <StrategyCard
              key={strategy.strategyId}
              strategy={strategy}
              canApprove={strategy.insightIds.every((insightId) =>
                approvedInsightIds.has(insightId),
              )}
              onChange={(patch) => updateStrategy(strategy.strategyId, patch)}
              onStatus={(status) =>
                setStrategyStatus(strategy.strategyId, status)
              }
            />
          ))}
        </div>
      </section>

      <section className="plan-generation-gate">
        <div>
          <span
            className={
              canGenerate
                ? "insight-gate__icon insight-gate__icon--ready"
                : "insight-gate__icon"
            }
          >
            <Icon name={canGenerate ? "check" : "lock"} size={20} />
          </span>
          <div>
            <strong>
              {canGenerate
                ? "审批输入已满足"
                : "确认目标，并批准至少一条洞察和策略"}
            </strong>
            <p>
              计划只会引用 {approvedInsights.length} 条已批准洞察与{" "}
              {approvedStrategies.length} 条已批准策略。
            </p>
          </div>
        </div>
        <div>
          {generationStatus === "generating" ? (
            <button
              className="secondary-button"
              type="button"
              onClick={cancelGeneration}
            >
              取消生成
            </button>
          ) : (
            <button
              className="primary-button"
              type="button"
              disabled={!canGenerate}
              onClick={() => void generatePlan()}
            >
              <Icon name="sparkles" size={16} />
              {generationStatus === "cancelled" || generationStatus === "error"
                ? "重试生成"
                : planState.current
                  ? "重新生成初稿"
                  : "生成 30 天计划"}
            </button>
          )}
        </div>
      </section>

      {generationStatus !== "idle" && (
        <div
          className={`generation-status generation-status--${generationStatus}`}
          role="status"
        >
          <Icon
            name={
              generationStatus === "generating"
                ? "spinner"
                : generationStatus === "completed"
                  ? "check"
                  : "alert"
            }
            size={17}
            className={generationStatus === "generating" ? "spin" : ""}
          />
          {generationMessage}
        </div>
      )}

      {planState.current && (
        <ActionPlanReport
          plan={planState.current}
          approvedInsights={approvedInsights}
          approvedStrategies={approvedStrategies}
          canUndo={planState.history.length > 0}
          onUndo={() => dispatchPlan({ type: "UNDO_LAST_REVISION" })}
          onUpdateItem={updateCalendarItem}
          onConfirmPlan={confirmCurrentPlan}
          onDownload={() => downloadPlan(planState.current)}
        />
      )}

      <EvidenceChatPanel
        context={{
          snapshot,
          insights,
          strategies,
          plan: planState.current,
        }}
        onApplyPlanChange={applyChatChange}
      />
    </div>
  );
}
