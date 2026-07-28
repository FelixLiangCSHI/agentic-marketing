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
    label: "AI Strategy",
    description: "Human approval required",
    icon: "sparkles",
  },
  {
    label: "30-Day Calendar",
    description: "Schedule and approval",
    icon: "content",
  },
  {
    label: "Draft Generation",
    description: "Buffer-ready content",
    icon: "arrow",
  },
];

function fallbackParseError(): ParseError {
  return {
    code: "PARSE_FAILED",
    message: "无法连接解析服务，请检查本地服务后重试。",
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
          <span>AI Agent Workspace</span>
        </div>
      </div>
      <div className="app-header__meta">
        <span className="product-status">
          <span />
          证据策略 Demo
        </span>
        {mode && (
          <span
            className={
              mode === "mock"
                ? "mode-badge mode-badge--mock"
                : "mode-badge mode-badge--private"
            }
          >
            <Icon name={mode === "mock" ? "sparkles" : "lock"} size={14} />
            {mode === "mock" ? "Synthetic Mock" : "本地临时会话"}
          </span>
        )}
        {mode && (
          <button className="header-button" type="button" onClick={onReset}>
            <Icon name="refresh" size={15} />
            重新开始
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
        <span>AGENT PIPELINE</span>
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
        <p>Human approval checkpoints prevent unreviewed AI output from advancing.</p>
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
        <h3>本次接入</h3>
        <div className="context-score">
          <strong>{completedCount}</strong>
          <span>/ 3 模块已确认</span>
        </div>
        <div className="context-progress" aria-label={`${completedCount}/3 已确认`}>
          <span style={{ width: `${(completedCount / 3) * 100}%` }} />
        </div>
        <dl className="context-metrics">
          <div>
            <dt>有效记录</dt>
            <dd>{validRows.toLocaleString("zh-CN")}</dd>
          </div>
          <div>
            <dt>文件上限</dt>
            <dd>{formatFileSize(MAX_UPLOAD_SIZE_BYTES)}</dd>
          </div>
        </dl>
      </section>

      {children}

      <section className="context-card context-card--privacy">
        <Icon name="shield" size={20} />
        <div>
          <h3>数据隐私边界</h3>
          <ul>
            <li>仅处理 LinkedIn 聚合分析数据</li>
            <li>不能识别匿名访客或具体关注者</li>
            <li>不会推断个人购买意向</li>
            <li>公式只识别并忽略，不执行</li>
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

  return (
    <div className="app-shell">
      <AppHeader
        mode={state.mode}
        onReset={() => dispatch({ type: "RESET" })}
      />

      <div className="page-frame">
        <section className="hero">
          <div>
            <span className="hero__eyebrow">
              <Icon name="sparkles" size={15} />
              MULTI-STAGE MARKETING AI
            </span>
            <h1>Turn LinkedIn performance into an approved 30-day campaign</h1>
            <p>
              A governed AI agent workflow for historical analysis, strategy recommendation, content planning and Buffer-ready draft generation.
            </p>
            <div className="hero__trust">
              <span>
                <Icon name="shield" size={15} />
                服务端双重校验
              </span>
              <span>
                <Icon name="lock" size={15} />
                默认不持久化
              </span>
              <span>
                <Icon name="table" size={15} />
                行级证据来源
              </span>
            </div>
          </div>
          <div className="mock-entry">
            <span className="mock-entry__icon">
              <Icon name="sparkles" size={22} />
            </span>
            <div>
              <strong>没有文件？</strong>
              <p>载入完全虚构的小型 CSV，体验相同的识别与确认接口。</p>
            </div>
            <button className="secondary-button" type="button" onClick={loadMock}>
              使用脱敏示例
              <Icon name="arrow" size={16} />
            </button>
          </div>
        </section>

        <div className="ingestion-layout">
          <PipelineNavigation
            ingestionComplete={ready}
            packageReady={state.analysisReady}
            hasBlockingIssues={snapshot?.quality.hasBlockingIssues ?? false}
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
                      <h2>上传 LinkedIn 分析导出</h2>
                      <p>三个模块必须独立确认；支持多 Sheet 工作簿。</p>
                    </div>
                    <span className="upload-counter">
                      {completedCount} / 3 已确认
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
                      title="上传后在这里确认识别结果"
                      description="系统会展示文件与 Sheet 信息、字段映射、未识别字段、标准化预览和质量警告。"
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
                          ? "三个数据模块已确认"
                          : "尚未满足进入下一阶段的条件"}
                      </strong>
                      <p>
                        {ready
                          ? "可以生成供指标计算使用的统一数据包。"
                          : missingModules.length > 0
                            ? `待确认：${missingModules
                                .map((item) => MODULE_CONFIG[item].label)
                                .join("、")}。${missingModules
                                .map((item) => MODULE_CONFIG[item].impact)
                                .join("")}`
                            : "请解决重复模块或数据质量问题。"}
                      </p>
                    </div>
                  </div>
                  <button
                    className="primary-button"
                    type="button"
                    disabled={!ready}
                    onClick={() => dispatch({ type: "MARK_ANALYSIS_READY" })}
                  >
                    生成统一数据包
                    <Icon name="arrow" size={16} />
                  </button>
                </section>
              </>
            )}
          </main>

          <ContextRail completedCount={completedCount} validRows={validRows}>
            <section className="context-card">
              <span className="section-label">REQUIRED INPUTS</span>
              <h3>数据要求</h3>
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
                            ? `${slot.result?.validRows.toLocaleString("zh-CN")} 条有效记录`
                            : slot.status === "parsed"
                              ? "已解析，等待确认"
                              : slot.status === "parsing"
                                ? "正在识别"
                                : "尚未确认"}
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
