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
  reviewActionPlan,
  reviseActionPlanSchedule,
  reviseCalendarItem,
  runActionPlanAgent,
} from "@/agents/action-plan-agent";
import { generateEvidenceStrategyBundle } from "@/agents/evidence-strategy-agent";
import { ActionPlanReport } from "@/components/analysis/action-plan-report";
import { EnterpriseApprovalControls } from "@/components/analysis/enterprise-approval-controls";
import { Icon } from "@/components/ui/icon";
import { ConsultingReport } from "@/components/analysis/consulting-report";
import type {
  ActionPlanInput,
  ActionPlanPreferences,
  ContentCalendarItem,
} from "@/domain/action-plan";
import type { AnalysisSnapshot } from "@/domain/analysis";
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
  draft: "Prepared for review",
  approved: "Approved",
  revision_requested: "Revision requested",
  rejected: "Rejected",
};

const INSIGHT_CATEGORY_LABELS: Record<EvidenceInsight["category"], string> = {
  audience: "Audience Insights",
  content: "Content Insights",
  opportunity: "Posting Pattern",
  risk: "Competitor Observations",
};

function WorkflowPipeline({
  strategyApproved,
  calendarReady,
  draftsReady,
}: {
  strategyApproved: boolean;
  calendarReady: boolean;
  draftsReady: boolean;
}) {
  const stages = [
    {
      number: "01",
      title: "Analysis",
      detail: "Historical LinkedIn Analysis",
      status: "complete",
    },
    {
      number: "02",
      title: "Strategy",
      detail: "Campaign Strategy",
      status: "complete",
    },
    {
      number: "03",
      title: "Approval",
      detail: "Strategy reviewer checkpoint",
      status: strategyApproved ? "complete" : "active",
    },
    {
      number: "04",
      title: "Content Calendar",
      detail: "30-Day Content Calendar",
      status: calendarReady ? "complete" : strategyApproved ? "active" : "locked",
    },
    {
      number: "05",
      title: "Approval",
      detail: "Calendar reviewer checkpoint",
      status: draftsReady ? "complete" : calendarReady ? "active" : "locked",
    },
    {
      number: "06",
      title: "Prepare Content",
      detail: "LinkedIn publishing drafts",
      status: draftsReady ? "complete" : "locked",
    },
    {
      number: "07",
      title: "Publishing Handoff",
      detail: "Approved drafts ready for handoff",
      status: draftsReady ? "complete" : "locked",
    },
  ] as const;

  return (
    <nav className="agent-pipeline" aria-label="Marketing workflow progress">
      <div className="agent-pipeline__header">
        <div>
          <span className="section-label">WORKFLOW PROGRESS</span>
          <h2>Governed campaign workflow</h2>
        </div>
        <span className="agent-pipeline__run">RUN · {draftsReady ? "COMPLETE" : "IN PROGRESS"}</span>
      </div>
      <ol>
        {stages.map((stage) => (
          <li key={stage.number} className={`agent-stage agent-stage--${stage.status}`}>
            <span className="agent-stage__number">
              {stage.status === "complete" ? <Icon name="check" size={17} /> : stage.number}
            </span>
            <div>
              <strong>{stage.title}</strong>
              <small>{stage.detail}</small>
            </div>
            <span className="agent-stage__status">
              {stage.status === "complete"
                ? "Complete"
                : stage.status === "active"
                  ? "In progress"
                  : "Locked"}
            </span>
          </li>
        ))}
      </ol>
    </nav>
  );
}

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
          <span>{INSIGHT_CATEGORY_LABELS[insight.category]}</span>
          <h3>{insight.title}</h3>
        </div>
        <span className={`approval-status approval-status--${insight.approvalStatus}`}>
          {STATUS_LABELS[insight.approvalStatus]}
        </span>
      </header>
      <ConsultingReport report={insight.report} />
      <details className="approval-evidence">
        <summary>Review metric evidence and limitations</summary>
        <ul>
          {insight.evidence.map((reference) => (
            <li key={reference.metricId}>
              <strong>{reference.metricId}</strong>
              <span>{reference.formattedValue}</span>
              <small>
                {reference.period
                  ? `${reference.period.start} — ${reference.period.end}`
                  : "No date range available"}{" "}
                · {reference.sourceModules.join(", ")}
              </small>
            </li>
          ))}
        </ul>
        <p>{insight.limitations.join(" ")}</p>
      </details>
      <EnterpriseApprovalControls
        recommendation={insight.title}
        status={insight.approvalStatus}
        onDecision={onStatus}
      />
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
          <span>Campaign Strategy</span>
          <h3>{strategy.title}</h3>
        </div>
        <span className={`approval-status approval-status--${strategy.approvalStatus}`}>
          {STATUS_LABELS[strategy.approvalStatus]}
        </span>
      </header>
      <label className="strategy-edit-field">
        Strategy objective
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
      <ConsultingReport report={strategy.report} />
      <details className="approval-evidence">
        <summary>Review insight and metric references</summary>
        <code>{strategy.insightIds.join(", ")}</code>
        <code>{strategy.metricIds.join(", ")}</code>
      </details>
      {!canApprove && (
        <p className="approval-dependency">
          <Icon name="lock" size={14} />
          Approve every referenced insight before approving this strategy.
        </p>
      )}
      <EnterpriseApprovalControls
        recommendation={strategy.title}
        status={strategy.approvalStatus}
        canApprove={canApprove}
        onDecision={onStatus}
      />
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
    "Support healthcare professionals and hospital procurement teams with clinical evidence, regulatory progress, and economic value.",
  );
  const [businessGoal, setBusinessGoal] = useState<BusinessGoal | null>(null);
  const initialTimeZone =
    Intl.DateTimeFormat().resolvedOptions().timeZone || "America/New_York";
  const [preferences, setPreferences] = useState<ActionPlanPreferences>({
    startDate: defaultPlanStartDate(initialTimeZone),
    timeZone: initialTimeZone,
    postsPerWeek: 2,
    teamSize: null,
    contentResources: [],
    targetMarket: null,
    focusAudience: "Healthcare professionals, clinical leaders, and hospital procurement teams",
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
      setGenerationMessage("Confirm the business goal before preparing the plan.");
      return;
    }
    generationController.current?.abort();
    const controller = new AbortController();
    generationController.current = controller;
    setGenerationStatus("generating");
    setGenerationMessage("Validating references and preparing the four-week plan...");
    try {
      const plan = await runActionPlanAgent(input, {
        signal: controller.signal,
      });
      if (generationController.current !== controller) {
        return;
      }
      dispatchPlan({ type: "LOAD_PLAN", plan });
      setGenerationStatus("completed");
      setGenerationMessage("Plan structure and reference validation passed.");
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
        setGenerationMessage("Preparation cancelled. Existing approvals were retained.");
      } else {
        setGenerationStatus("error");
        setGenerationMessage(
          reason instanceof Error ? reason.message : "Plan preparation failed. Try again.",
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
        "Updated the schedule, content calendar, and KPI review without rerunning the snapshot.",
      );
      setPreferencesDirty(false);
    } catch (reason) {
      setGenerationStatus("error");
      setGenerationMessage(
        reason instanceof Error ? reason.message : "Plan settings could not be updated.",
      );
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

  function reviewCurrentPlan(status: "revision_requested" | "rejected") {
    if (!planState.current) {
      return;
    }
    dispatchPlan({
      type: "APPLY_REVISION",
      plan: reviewActionPlan(planState.current, status),
    });
  }

  const canGenerate =
    businessGoal !== null &&
    approvedInsights.length > 0 &&
    approvedStrategies.length > 0 &&
    generationStatus !== "generating";
  const strategyApproved = approvedStrategies.length > 0;
  const calendarReady = planState.current !== null;
  const draftsReady = planState.current?.status === "user_confirmed";

  return (
    <div className="planning-workspace">
      <section className="planning-hero">
        <div>
          <button className="text-button" type="button" onClick={onBack}>
            <Icon name="chevron" size={15} />
            Back to snapshot
          </button>
          <span className="section-label">MARKETING OPERATIONS</span>
          <h2>LinkedIn Campaign Intelligence Workflow</h2>
          <p>
            Move from historical performance to approved publishing drafts through clear inputs, structured recommendations, and reviewer checkpoints.
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
            <dt>Mode</dt>
            <dd>Deterministic Mock</dd>
          </div>
        </dl>
      </section>

      <WorkflowPipeline
        strategyApproved={strategyApproved}
        calendarReady={calendarReady}
        draftsReady={draftsReady}
      />

      <section className="planning-limits">
        <Icon name="shield" size={21} />
        <div>
          <strong>Data and recommendation safeguards remain active</strong>
          <p>
            Aggregate data cannot identify people. Proxy metrics are not conversions, correlation is not causation, and plans do not promise fixed growth.
          </p>
        </div>
      </section>

      <section className="approval-section workflow-block workflow-block--analysis">
        <div className="workflow-block__header">
          <span className="workflow-block__step">STEP 1</span>
          <div>
            <span className="section-label">HISTORICAL LINKEDIN ANALYSIS</span>
            <h2>Historical performance intelligence</h2>
            <p>Input · Past LinkedIn posts and performance</p>
          </div>
          <span className="workflow-state workflow-state--complete">
            <Icon name="check" size={14} />
            Analysis complete
          </span>
        </div>
        <div className="analysis-output-grid">
          {(["audience", "content", "opportunity", "risk"] as const).map((category) => {
            const categoryInsights = insights.filter((insight) => insight.category === category);
            return (
              <article key={category}>
                <span>{INSIGHT_CATEGORY_LABELS[category]}</span>
                <strong>{categoryInsights[0]?.title ?? "Insufficient historical evidence"}</strong>
                <p>{categoryInsights[0]?.statement ?? "Upload additional LinkedIn performance data to improve this output."}</p>
                <small>{categoryInsights.length} evidence-backed observation{categoryInsights.length === 1 ? "" : "s"}</small>
              </article>
            );
          })}
        </div>
        <div className="approval-grid">
          {insights.map((insight) => (
            <EvidenceInsightCard
              key={insight.insightId}
              insight={insight}
              onStatus={(status) => setInsightStatus(insight.insightId, status)}
            />
          ))}
        </div>
      </section>

      <section className="planning-config">
        <div className="section-heading section-heading--large">
          <div>
            <span className="section-label">STEP 2 · STRATEGY INPUTS</span>
            <h2>Campaign Strategy</h2>
            <p>Unspecified teams and resources use clear placeholders rather than invented details.</p>
          </div>
          {businessGoal && (
            <span className="approval-status approval-status--approved">
              Goal confirmed
            </span>
          )}
        </div>
        <div className="planning-config-grid">
          <label className="planning-field planning-field--wide">
            Business goal
            <input
              value={goalText}
              maxLength={180}
              onChange={(event) => {
                setGoalText(event.target.value);
                setBusinessGoal(null);
                clearPlanForEvidenceChange();
              }}
            />
            <small>Avoid fixed growth promises; identify numeric targets as reviewer-defined.</small>
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
            {businessGoal ? "Business goal confirmed" : "Confirm business goal"}
          </button>
          <label className="planning-field">
            Plan start date
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
            Workspace time zone
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
            Weekly publishing capacity
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
                  {value} posts / week
                </option>
              ))}
            </select>
          </label>
          <label className="planning-field">
            Team size (optional)
            <input
              type="number"
              min={1}
              max={99}
              value={preferences.teamSize ?? ""}
              placeholder="Not provided"
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
            Focus audience
            <input
              value={preferences.focusAudience}
              onChange={(event) =>
                updatePreferences({ focusAudience: event.target.value })
              }
            />
          </label>
          <label className="planning-field">
            Target market (optional)
            <input
              value={preferences.targetMarket ?? ""}
              placeholder="For example, APAC"
              onChange={(event) =>
                updatePreferences({
                  targetMarket: event.target.value || null,
                })
              }
            />
          </label>
          <label className="planning-field planning-field--wide">
            Content resources (optional, comma-separated)
            <input
              value={resourcesText}
              placeholder="Copywriting, design, video"
              onChange={(event) => {
                const value = event.target.value;
                setResourcesText(value);
                updatePreferences({
                  contentResources: value
                    .split(",")
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
                ? "Execution settings have changed but are not yet applied."
                : "The current plan uses these execution settings."}
            </span>
            <button
              className="secondary-button"
              type="button"
              disabled={!preferencesDirty}
              onClick={() => applyPreferenceRevision()}
            >
              Update affected schedule
            </button>
          </div>
        )}
      </section>

      <section className="approval-section workflow-block workflow-block--strategy">
        <div className="workflow-block__header">
          <span className="workflow-block__step">STEP 2</span>
          <div>
            <span className="section-label">CAMPAIGN STRATEGY</span>
            <h2>Strategy recommendation package</h2>
            <p>Prepared recommendation · Human approval required</p>
          </div>
          <span className={`workflow-state ${strategyApproved ? "workflow-state--complete" : "workflow-state--approval"}`}>
            <Icon name={strategyApproved ? "check" : "lock"} size={14} />
            {strategyApproved ? "Approved" : "Human approval required"}
          </span>
        </div>
        <dl className="strategy-recommendation-grid">
          <div><dt>Target audience</dt><dd>{preferences.focusAudience}</dd></div>
          <div><dt>Key messaging</dt><dd>{strategies[0]?.objective ?? goalText}</dd></div>
          <div><dt>Content pillars</dt><dd>{strategies.slice(0, 3).map((item) => item.title).join(" · ")}</dd></div>
          <div><dt>Campaign objective</dt><dd>{businessGoal?.statement ?? goalText}</dd></div>
          <div><dt>Posting frequency</dt><dd>{preferences.postsPerWeek} posts / week</dd></div>
          <div><dt>Confidence score</dt><dd>{approvedInsights.length > 1 ? "82% · High" : "68% · Medium"}</dd></div>
        </dl>
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
                ? "Approval inputs are complete"
                : "Confirm the goal and approve at least one insight and strategy"}
            </strong>
            <p>
              The plan will use {approvedInsights.length} approved insights and{" "}
              {approvedStrategies.length} approved strategies.
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
              Cancel preparation
            </button>
          ) : (
            <button
              className="primary-button"
              type="button"
              disabled={!canGenerate}
              onClick={() => void generatePlan()}
            >
              <Icon name="content" size={16} />
              {generationStatus === "cancelled" || generationStatus === "error"
                ? "Retry preparation"
                : planState.current
                  ? "Prepare revised draft"
                  : "Prepare 30-day plan"}
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
          onReviewPlan={reviewCurrentPlan}
          onDownload={() => downloadPlan(planState.current)}
        />
      )}

    </div>
  );
}
