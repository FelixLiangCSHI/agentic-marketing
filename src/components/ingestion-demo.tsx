"use client";

import {
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from "react";

import {
  analysisInputFromParseResults,
  generateAnalysisSnapshot,
} from "@/analysis/snapshot-engine";
import { AnalysisSnapshotView } from "@/components/analysis/analysis-snapshot-view";
import { EmptyState } from "@/components/ui/empty-state";
import { Icon, type IconName } from "@/components/ui/icon";
import { RecognitionPanel } from "@/components/upload/recognition-panel";
import { UploadCard } from "@/components/upload/upload-card";
import {
  MAX_UPLOAD_SIZE_BYTES,
  formatFileSize,
  validateFileEnvelope,
} from "@/data-processing/file-validation";
import { MODULE_CONFIG } from "@/domain/module-config";
import {
  LINKEDIN_MODULES,
  type FileParseResult,
  type LinkedInModule,
  type ParseError,
} from "@/domain/linkedin";
import {
  canStartAnalysis,
  createInitialIngestionState,
  getRepeatedModules,
  ingestionReducer,
} from "@/state/ingestion-reducer";
import {
  ParseClientError,
  parseLinkedInFile,
} from "@/services/parse-client";

interface IngestionDemoProps {
  mockResults: Record<LinkedInModule, FileParseResult>;
}

interface PipelineStage {
  label: string;
  description: string;
  icon: IconName;
}

const PIPELINE_STAGES: readonly PipelineStage[] = [
  {
    label: "Historical Analysis",
    description: "Posts and performance",
    icon: "database",
  },
  {
    label: "Campaign Strategy",
    description: "Human approval required",
    icon: "content",
  },
  {
    label: "30-Day Calendar",
    description: "Schedule and approval",
    icon: "content",
  },
  {
    label: "Prepare Content",
    description: "Publishing-ready content",
    icon: "arrow",
  },
];

function fallbackParseError(): ParseError {
  return {
    code: "PARSE_FAILED",
    message: "The parsing service is unavailable. Check the local service and try again.",
    retryable: true,
  };
}

function slotDetectedModule(
  result: FileParseResult | null,
): LinkedInModule | null {
  return result?.detectedModules.length === 1
    ? result.detectedModules[0]
    : null;
}

function downloadSnapshot(snapshot: unknown) {
  const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "linkedin-analysis-snapshot.json";
  anchor.click();
  URL.revokeObjectURL(url);
}

function StatusIcon({
  status,
}: {
  status: "completed" | "running" | "pending" | "error";
}) {
  if (status === "completed") {
    return <Icon name="check" size={16} />;
  }
  if (status === "running") {
    return <span className="status-dot" aria-hidden="true" />;
  }
  if (status === "error") {
    return <Icon name="alert" size={16} />;
  }
  return <span className="status-index" aria-hidden="true" />;
}

function AppHeader({
  mode,
  onReset,
}: {
  mode: "uploaded" | "mock" | null;
  onReset: () => void;
}) {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand__mark">in</span>
        <span className="brand__divider" />
        <div>
          <strong>Marketing Intelligence</strong>
          <span>Campaign Operations Workspace</span>
        </div>
      </div>
      <div className="app-header__meta">
        <span className="product-status">
          <span />
          Evidence Strategy Demo
        </span>
        {mode && (
          <span
            className={
              mode === "mock"
                ? "mode-badge mode-badge--mock"
                : "mode-badge mode-badge--private"
            }
          >
            <Icon name={mode === "mock" ? "database" : "lock"} size={14} />
            {mode === "mock" ? "Synthetic Demo Data" : "Local Session"}
          </span>
        )}
        {mode && (
          <button className="header-button" type="button" onClick={onReset}>
            <Icon name="refresh" size={15} />
            Start over
          </button>
        )}
      </div>
    </header>
  );
}

function PipelineNavigation({
  ingestionComplete,
  packageReady,
  hasBlockingIssues,
}: {
  ingestionComplete: boolean;
  packageReady: boolean;
  hasBlockingIssues: boolean;
}) {
  return (
    <aside className="pipeline-nav">
      <div className="pipeline-nav__heading">
        <span>CAMPAIGN WORKFLOW</span>
        <strong>Workflow progress</strong>
      </div>
      <ol>
        {PIPELINE_STAGES.map((stage, index) => {
          const status =
            packageReady && index === 0 && hasBlockingIssues
              ? "error"
              : packageReady && index === 0
              ? "completed"
              : packageReady && index === 1 && !hasBlockingIssues
                ? "running"
                : index === 0 && ingestionComplete
                  ? "completed"
                  : (index === 0 && !ingestionComplete) ||
                      (index === 1 && ingestionComplete)
                    ? "running"
                    : "pending";
          return (
            <li
              key={stage.label}
              className={`pipeline-step pipeline-step--${status}`}
            >
              <span className="pipeline-step__status">
                <StatusIcon status={status} />
              </span>
              <span className="pipeline-step__icon">
                <Icon name={stage.icon} size={17} />
              </span>
              <div>
                <strong>{stage.label}</strong>
                <small>{stage.description}</small>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="pipeline-nav__note">
        <Icon name="lock" size={17} />
        <p>Human approval checkpoints prevent unreviewed recommendations from advancing.</p>
      </div>
    </aside>
  );
}

function ContextRail({
  children,
  completedCount,
  validRows,
}: {
  children?: ReactNode;
  completedCount: number;
  validRows: number;
}) {
  return (
    <aside className="context-rail">
      <section className="context-card">
        <span className="section-label">SESSION CONTEXT</span>
        <h3>Current intake</h3>
        <div className="context-score">
          <strong>{completedCount}</strong>
          <span>/ 3 modules confirmed</span>
        </div>
        <div className="context-progress" aria-label={`${completedCount}/3 confirmed`}>
          <span style={{ width: `${(completedCount / 3) * 100}%` }} />
        </div>
        <dl className="context-metrics">
          <div>
            <dt>Valid records</dt>
            <dd>{validRows.toLocaleString("en-US")}</dd>
          </div>
          <div>
            <dt>File limit</dt>
            <dd>{formatFileSize(MAX_UPLOAD_SIZE_BYTES)}</dd>
          </div>
        </dl>
      </section>

      {children}

      <section className="context-card context-card--privacy">
        <Icon name="shield" size={20} />
        <div>
          <h3>Data privacy boundaries</h3>
          <ul>
            <li>Processes aggregate LinkedIn analytics only</li>
            <li>Cannot identify visitors or individual followers</li>
            <li>Does not infer individual purchase intent</li>
            <li>Recognizes and ignores formulas without executing them</li>
          </ul>
        </div>
      </section>
    </aside>
  );
}

export function IngestionDemo({ mockResults }: IngestionDemoProps) {
  const [state, dispatch] = useReducer(
    ingestionReducer,
    undefined,
    createInitialIngestionState,
  );
  const abortControllers = useRef<
    Partial<Record<LinkedInModule, AbortController>>
  >({});

  useEffect(
    () => () => {
      Object.values(abortControllers.current).forEach((controller) =>
        controller?.abort(),
      );
    },
    [],
  );

  const repeatedModules = getRepeatedModules(state);
  const ready = canStartAnalysis(state);
  const completedCount = LINKEDIN_MODULES.filter(
    (module) => state.slots[module].confirmed,
  ).length;
  const validRows = LINKEDIN_MODULES.reduce(
    (sum, module) => sum + (state.slots[module].result?.validRows ?? 0),
    0,
  );
  const activeSlot = state.activeSlot
    ? state.slots[state.activeSlot]
    : null;
  const snapshot = useMemo(() => {
    if (!state.analysisReady || !state.mode) {
      return null;
    }
    return generateAnalysisSnapshot(
      analysisInputFromParseResults(
        {
          followers: state.slots.followers.result ?? undefined,
          visitors: state.slots.visitors.result ?? undefined,
          content: state.slots.content.result ?? undefined,
        },
        state.mode,
      ),
    );
  }, [state.analysisReady, state.mode, state.slots]);

  async function runParse(
    module: LinkedInModule,
    file: File,
    options: {
      preserveMappings?: boolean;
      moduleOverride?: LinkedInModule;
    } = {},
  ) {
    const validation = validateFileEnvelope(file);
    if (!validation.ok) {
      dispatch({
        type: "PARSE_FAILED",
        module,
        error: validation.error,
      });
      return;
    }

    abortControllers.current[module]?.abort();
    const controller = new AbortController();
    abortControllers.current[module] = controller;
    const slot = state.slots[module];

    dispatch({
      type: "PARSE_STARTED",
      module,
      file,
      preserveMappings: options.preserveMappings ?? false,
    });

    try {
      const result = await parseLinkedInFile(file, {
        expectedModule: module,
        moduleOverride: options.moduleOverride,
        mappingOverrides: options.preserveMappings
          ? slot.mappingOverrides
          : undefined,
        signal: controller.signal,
      });
      dispatch({ type: "PARSE_SUCCEEDED", module, result });
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") {
        return;
      }

      dispatch({
        type: "PARSE_FAILED",
        module,
        error:
          reason instanceof ParseClientError
            ? reason.details
            : fallbackParseError(),
      });
    } finally {
      if (abortControllers.current[module] === controller) {
        delete abortControllers.current[module];
      }
    }
  }

  function removeFile(module: LinkedInModule) {
    abortControllers.current[module]?.abort();
    delete abortControllers.current[module];
    dispatch({ type: "REMOVE_FILE", module });
  }

  function loadMock() {
    Object.values(abortControllers.current).forEach((controller) =>
      controller?.abort(),
    );
    abortControllers.current = {};
    dispatch({ type: "LOAD_MOCK", results: mockResults });
  }

  const missingModules = LINKEDIN_MODULES.filter(
    (module) => !state.slots[module].confirmed,
  );
  const hasIntakeActivity = LINKEDIN_MODULES.some(
    (module) => state.slots[module].status !== "idle",
  );
  const confidencePercent = Math.round((completedCount / 3) * 100);
  const hasBlockingIssues = snapshot?.quality.hasBlockingIssues ?? false;
  const hasQualityWarnings = (snapshot?.quality.warningCount ?? 0) > 0;
  let confidenceLabel = "Not assessed";
  let confidenceTone = "neutral";
  let confidenceDetail = `${completedCount} of 3 modules confirmed`;

  if (hasBlockingIssues) {
    const issueCount = snapshot?.quality.blockingIssueCount ?? 0;
    confidenceLabel = "Low";
    confidenceTone = "danger";
    confidenceDetail = `${issueCount} blocking quality issue${issueCount === 1 ? "" : "s"}`;
  } else if (hasQualityWarnings) {
    const warningCount = snapshot?.quality.warningCount ?? 0;
    confidenceLabel = "Moderate";
    confidenceTone = "approval";
    confidenceDetail = `${warningCount} quality warning${warningCount === 1 ? "" : "s"}`;
  } else if (completedCount === 3) {
    confidenceLabel = "High";
    confidenceTone = "ready";
  } else if (completedCount === 2) {
    confidenceLabel = "Moderate";
  } else if (completedCount === 1) {
    confidenceLabel = "Developing";
  }
  const workflowSummary = state.analysisReady
    ? {
        badge: hasBlockingIssues ? "Attention required" : "In review",
        title: hasBlockingIssues
          ? "Analysis requires remediation"
          : "Campaign strategy review",
        detail: "Step 2 of 4",
        tone: hasBlockingIssues ? "danger" : "active",
      }
    : ready
      ? {
          badge: "Ready",
          title: "Historical analysis ready",
          detail: "Step 1 of 4",
          tone: "ready",
        }
      : hasIntakeActivity
        ? {
            badge: "In progress",
            title: "Data intake in progress",
            detail: "Step 1 of 4",
            tone: "active",
          }
        : {
            badge: "Open",
            title: "Awaiting source data",
            detail: "Step 1 of 4",
            tone: "neutral",
          };
  const approvalGate = hasBlockingIssues
    ? {
        badge: "Blocked",
        title: "Resolve data quality issues",
        detail: "Approval cannot advance while blocking issues remain.",
        tone: "danger",
      }
    : state.analysisReady
      ? {
          badge: "Required",
          title: "Human review pending",
          detail: "Recommendations require explicit approval before planning.",
          tone: "approval",
        }
      : ready
        ? {
            badge: "Available",
            title: "Analysis gate available",
            detail: "Start analysis to prepare evidence for human review.",
            tone: "ready",
          }
        : {
            badge: "Locked",
            title: "Approval gate locked",
            detail: "Confirm all three source modules to unlock review.",
            tone: "neutral",
          };

  return (
    <div className="app-shell">
      <AppHeader
        mode={state.mode}
        onReset={() => dispatch({ type: "RESET" })}
      />

      <div className="page-frame">
        <section
          className="dashboard-overview"
          aria-labelledby="workflow-overview-title"
        >
          <header className="dashboard-overview__header">
            <div>
              <span className="section-label">CAMPAIGN OPERATIONS</span>
              <h1 id="workflow-overview-title">Campaign workflow overview</h1>
              <p>
                Governed intake, analysis, approval, and publishing preparation
                for LinkedIn campaign operations.
              </p>
            </div>
            <div className="mock-entry">
              <div>
                <strong>Demo workspace</strong>
                <p>Load fictional data into the same governed intake.</p>
              </div>
              <button
                className="secondary-button"
                type="button"
                onClick={loadMock}
              >
                Use demo data
              </button>
            </div>
          </header>

          <div
            className="dashboard-overview__status"
            aria-label="Current workflow status"
          >
            <article className="overview-status-card">
              <div className="overview-status-card__heading">
                <h2>Workflow status</h2>
                <span
                  className={`overview-badge overview-badge--${workflowSummary.tone}`}
                >
                  {workflowSummary.badge}
                </span>
              </div>
              <strong>{workflowSummary.title}</strong>
              <p>{workflowSummary.detail}</p>
            </article>

            <article className="overview-status-card">
              <div className="overview-status-card__heading">
                <h2>Data confidence</h2>
                <span
                  className={`overview-badge overview-badge--${confidenceTone}`}
                >
                  {confidenceLabel}
                </span>
              </div>
              <strong>{confidencePercent}% source coverage</strong>
              <p>{confidenceDetail}</p>
              <progress
                aria-label="Data confidence based on confirmed source modules"
                max="100"
                value={confidencePercent}
              >
                {confidencePercent}%
              </progress>
            </article>

            <article className="overview-status-card">
              <div className="overview-status-card__heading">
                <h2>Approval gate</h2>
                <span
                  className={`overview-badge overview-badge--${approvalGate.tone}`}
                >
                  {approvalGate.badge}
                </span>
              </div>
              <strong>{approvalGate.title}</strong>
              <p>{approvalGate.detail}</p>
            </article>
          </div>
        </section>

        <div className="ingestion-layout">
          <PipelineNavigation
            ingestionComplete={ready}
            packageReady={state.analysisReady}
            hasBlockingIssues={hasBlockingIssues}
          />

          <main className="workspace">
            {state.analysisReady && snapshot ? (
              <AnalysisSnapshotView
                snapshot={snapshot}
                warningsAcknowledged={state.qualityWarningsAcknowledged}
                onAcknowledgeWarnings={() =>
                  dispatch({ type: "ACKNOWLEDGE_QUALITY_WARNINGS" })
                }
                onBack={() =>
                  dispatch({
                    type: "SET_ACTIVE_SLOT",
                    module: "followers",
                  })
                }
                onDownload={() => downloadSnapshot(snapshot)}
              />
            ) : (
              <>
                <section className="upload-section">
                  <div className="section-heading section-heading--large">
                    <div>
                      <span className="section-label">DATA SOURCES</span>
                      <h2>Upload LinkedIn analytics exports</h2>
                      <p>Confirm each module independently; multi-sheet workbooks are supported.</p>
                    </div>
                    <span className="upload-counter">
                      {completedCount} / 3 confirmed
                    </span>
                  </div>

                  <div className="upload-grid">
                    {LINKEDIN_MODULES.map((module) => {
                      const slot = state.slots[module];
                      const detected = slotDetectedModule(slot.result);
                      return (
                        <UploadCard
                          key={module}
                          module={module}
                          slot={slot}
                          repeated={
                            detected !== null &&
                            repeatedModules.includes(detected)
                          }
                          onFile={(file) => void runParse(module, file)}
                          onRemove={() => removeFile(module)}
                          onInspect={() =>
                            dispatch({ type: "SET_ACTIVE_SLOT", module })
                          }
                        />
                      );
                    })}
                  </div>
                </section>

                {activeSlot && state.activeSlot ? (
                  <RecognitionPanel
                    key={`${state.activeSlot}-${activeSlot.result?.parsedAt ?? "empty"}`}
                    module={state.activeSlot}
                    slot={activeSlot}
                    repeated={
                      slotDetectedModule(activeSlot.result) !== null &&
                      repeatedModules.includes(
                        slotDetectedModule(activeSlot.result) as LinkedInModule,
                      )
                    }
                    onMappingChange={(key, field) =>
                      dispatch({
                        type: "UPDATE_MAPPING",
                        module: state.activeSlot as LinkedInModule,
                        key,
                        field,
                      })
                    }
                    onApplyMappings={() => {
                      if (activeSlot.file && state.activeSlot) {
                        void runParse(state.activeSlot, activeSlot.file, {
                          preserveMappings: true,
                        });
                      }
                    }}
                    onManualOverride={() => {
                      if (activeSlot.file && state.activeSlot) {
                        void runParse(state.activeSlot, activeSlot.file, {
                          moduleOverride: state.activeSlot,
                        });
                      }
                    }}
                    onConfirm={() =>
                      dispatch({
                        type: "CONFIRM_MODULE",
                        module: state.activeSlot as LinkedInModule,
                      })
                    }
                  />
                ) : (
                  <section className="recognition-panel">
                    <EmptyState
                      icon="table"
                      title="Review recognition results here"
                      description="File and sheet details, field mappings, unmatched fields, normalized previews, and quality warnings appear here."
                    />
                  </section>
                )}

                <section className="continue-bar">
                  <div>
                    <span
                      className={
                        ready
                          ? "continue-bar__icon continue-bar__icon--ready"
                          : "continue-bar__icon"
                      }
                    >
                      <Icon name={ready ? "check" : "alert"} size={19} />
                    </span>
                    <div>
                      <strong>
                        {ready
                          ? "All three data modules are confirmed"
                          : "Requirements for the next stage are not yet met"}
                      </strong>
                      <p>
                        {ready
                          ? "The standardized analysis package is ready."
                          : missingModules.length > 0
                            ? `Pending confirmation: ${missingModules
                                .map((item) => MODULE_CONFIG[item].label)
                                .join("、")}。${missingModules
                                .map((item) => MODULE_CONFIG[item].impact)
                                .join("")}`
                            : "Resolve duplicate modules or data quality issues."}
                      </p>
                    </div>
                  </div>
                  <button
                    className="primary-button"
                    type="button"
                    disabled={!ready}
                    onClick={() => dispatch({ type: "MARK_ANALYSIS_READY" })}
                  >
                    Analyze standardized data
                    <Icon name="arrow" size={16} />
                  </button>
                </section>
              </>
            )}
          </main>

          <ContextRail completedCount={completedCount} validRows={validRows}>
            <section className="context-card">
              <span className="section-label">REQUIRED INPUTS</span>
              <h3>Data requirements</h3>
              <ul className="requirement-list">
                {LINKEDIN_MODULES.map((module) => {
                  const slot = state.slots[module];
                  return (
                    <li key={module}>
                      <span
                        className={`requirement-status ${
                          slot.confirmed ? "requirement-status--done" : ""
                        }`}
                      >
                        <Icon
                          name={slot.confirmed ? "check" : "file"}
                          size={15}
                        />
                      </span>
                      <div>
                        <strong>{MODULE_CONFIG[module].label}</strong>
                        <small>
                          {slot.confirmed
                            ? `${slot.result?.validRows.toLocaleString("en-US")} valid records`
                            : slot.status === "parsed"
                              ? "Parsed, awaiting confirmation"
                              : slot.status === "parsing"
                                ? "Analyzing"
                                : "Not confirmed"}
                        </small>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          </ContextRail>
        </div>

        <p className="sr-announcement" aria-live="polite" aria-atomic="true">
          {state.announcement}
        </p>
      </div>
    </div>
  );
}
