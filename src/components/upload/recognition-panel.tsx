"use client";

import { useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { Icon } from "@/components/ui/icon";
import {
  FIELD_LABELS,
  MODULE_FIELDS,
  MODULE_LABELS,
  getMappingOverrideKey,
  isStandardField,
} from "@/data-processing/field-aliases";
import { formatFileSize } from "@/data-processing/file-validation";
import { MODULE_CONFIG } from "@/domain/module-config";
import type {
  ConfidenceLevel,
  FieldMapping,
  LinkedInModule,
  NormalizedLinkedInRecord,
  RawCellValue,
  StandardField,
  ValidationIssue,
} from "@/domain/linkedin";
import type { UploadSlotState } from "@/state/ingestion-reducer";

interface RecognitionPanelProps {
  module: LinkedInModule;
  slot: UploadSlotState;
  repeated: boolean;
  onMappingChange: (
    key: string,
    field: StandardField | null | undefined,
  ) => void;
  onApplyMappings: () => void;
  onManualOverride: () => void;
  onConfirm: () => void;
}

const PERCENTAGE_FIELDS = new Set<StandardField>([
  "demographicPercentage",
  "engagementRate",
  "clickThroughRate",
]);

function confidenceLabel(confidence: ConfidenceLevel): string {
  if (confidence === "high") {
    return "高置信度";
  }
  if (confidence === "medium") {
    return "中置信度";
  }
  return "低置信度";
}

function confidenceClass(confidence: ConfidenceLevel): string {
  return `confidence-badge confidence-badge--${confidence}`;
}

function recordValue(
  record: NormalizedLinkedInRecord,
  field: StandardField,
): unknown {
  return Object.entries(record).find(([key]) => key === field)?.[1] ?? null;
}

function formatValue(value: unknown, field: StandardField): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (typeof value === "number") {
    return PERCENTAGE_FIELDS.has(field)
      ? new Intl.NumberFormat("zh-CN", {
          style: "percent",
          maximumFractionDigits: 2,
        }).format(value)
      : value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  }

  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }

  return String(value);
}

function displayRawValue(value: RawCellValue): string {
  if (value === null) {
    return "空值";
  }
  const text = String(value);
  return text.length > 80 ? `${text.slice(0, 77)}…` : text;
}

function issuePriority(issue: ValidationIssue): number {
  if (issue.severity === "error") {
    return 0;
  }
  if (issue.severity === "warning") {
    return 1;
  }
  return 2;
}

function currentMappingValue(
  slot: UploadSlotState,
  sheetName: string,
  mapping: FieldMapping,
): string {
  const key = getMappingOverrideKey(
    sheetName,
    mapping.columnIndex,
    mapping.rawHeader,
  );

  if (!Object.hasOwn(slot.mappingOverrides, key)) {
    return "__auto__";
  }

  return slot.mappingOverrides[key] ?? "__ignore__";
}

export function RecognitionPanel({
  module,
  slot,
  repeated,
  onMappingChange,
  onApplyMappings,
  onManualOverride,
  onConfirm,
}: RecognitionPanelProps) {
  const [selectedSheetName, setSelectedSheetName] = useState<string | null>(
    null,
  );
  const result = slot.result;

  if (!result) {
    return (
      <section className="recognition-panel">
        <EmptyState
          icon="table"
          title="等待识别结果"
          description="上传任一文件后，这里会显示模块判断、字段映射、标准化预览和数据质量问题。"
        />
      </section>
    );
  }

  const selectedSheet =
    result.workbook.sheets.find(
      (sheet) => sheet.sheetName === selectedSheetName,
    ) ?? result.workbook.sheets[0];

  if (!selectedSheet) {
    return (
      <section className="recognition-panel">
        <EmptyState
          icon="alert"
          title="工作簿没有可展示的 Sheet"
          description="请重新导出文件后再试。"
        />
      </section>
    );
  }

  const detectedModule = selectedSheet.detection.detectedModule;
  const mappingModule = detectedModule ?? module;
  const mappedColumns = [
    ...new Set(
      selectedSheet.mappings.flatMap((mapping) =>
        mapping.status === "mapped" && mapping.standardField
          ? [mapping.standardField]
          : [],
      ),
    ),
  ];
  const sortedIssues = [...selectedSheet.issues].sort(
    (left, right) => issuePriority(left) - issuePriority(right),
  );
  const moduleMatches =
    result.detectedModules.length === 1 &&
    result.detectedModules[0] === module;
  const canConfirm =
    result.canProceed &&
    moduleMatches &&
    !slot.mappingDirty &&
    !repeated;

  return (
    <section className="recognition-panel" aria-labelledby="recognition-title">
      <header className="recognition-panel__header">
        <div>
          <div className="recognition-panel__eyebrow">
            <span
              className={
                result.parserMode === "synthetic-mock"
                  ? "mode-badge mode-badge--mock"
                  : "mode-badge mode-badge--private"
              }
            >
              <Icon
                name={
                  result.parserMode === "synthetic-mock"
                    ? "sparkles"
                    : "lock"
                }
                size={14}
              />
              {result.parserMode === "synthetic-mock"
                ? "Synthetic Mock"
                : "临时解析 · 不持久化"}
            </span>
            <span>{result.file.format.toLocaleUpperCase("en-US")}</span>
            <span>{formatFileSize(result.file.size)}</span>
          </div>
          <h2 id="recognition-title">{result.file.name}</h2>
          <p>
            已识别 {result.workbook.sheetCount} 个 Sheet；请确认模块和字段映射后再进入分析。
          </p>
        </div>
        <div className="recognition-panel__status">
          <span className={confidenceClass(selectedSheet.detection.confidence)}>
            {confidenceLabel(selectedSheet.detection.confidence)}
          </span>
          <span
            className={`readiness-badge ${
              selectedSheet.canProceed
                ? "readiness-badge--ready"
                : "readiness-badge--blocked"
            }`}
          >
            <Icon
              name={selectedSheet.canProceed ? "check" : "alert"}
              size={15}
            />
            {selectedSheet.canProceed ? "可进入下一阶段" : "需要处理"}
          </span>
        </div>
      </header>

      {!moduleMatches && (
        <div className="callout callout--warning" role="alert">
          <Icon name="alert" size={20} />
          <div>
            <strong>模块与上传槽位不一致</strong>
            <p>
              当前识别为{" "}
              {result.detectedModules.length
                ? result.detectedModules
                    .map((item) => MODULE_LABELS[item])
                    .join("、")
                : "无法确定"}
              ，上传位置是 {MODULE_LABELS[module]}。如确认文件属于该模块，可按槽位重新识别。
            </p>
          </div>
          {slot.file && (
            <button
              className="secondary-button secondary-button--small"
              type="button"
              onClick={onManualOverride}
            >
              按 {MODULE_LABELS[module]} 重新识别
            </button>
          )}
        </div>
      )}

      {repeated && (
        <div className="callout callout--danger" role="alert">
          <Icon name="alert" size={20} />
          <div>
            <strong>检测到重复模块</strong>
            <p>另一个上传文件也被识别为同一模块；确认前请移除或替换其中一个。</p>
          </div>
        </div>
      )}

      <div className="recognition-summary">
        <div>
          <span>推测模块</span>
          <strong>
            {detectedModule ? MODULE_LABELS[detectedModule] : "待手动选择"}
          </strong>
        </div>
        <div>
          <span>表头行</span>
          <strong>
            {selectedSheet.headerRow
              ? `第 ${selectedSheet.headerRow} 行`
              : "未定位"}
          </strong>
        </div>
        <div>
          <span>有效数据</span>
          <strong>
            {selectedSheet.validRows.toLocaleString("zh-CN")} /{" "}
            {selectedSheet.totalRows.toLocaleString("zh-CN")} 行
          </strong>
        </div>
        <div>
          <span>时间范围</span>
          <strong>
            {selectedSheet.dateRange
              ? `${selectedSheet.dateRange.start.slice(0, 10)} — ${selectedSheet.dateRange.end.slice(0, 10)}`
              : "未识别"}
          </strong>
        </div>
      </div>

      <div className="sheet-layout">
        <nav className="sheet-list" aria-label="工作簿 Sheet">
          <span className="section-label">WORKBOOK SHEETS</span>
          {result.workbook.sheets.map((sheet) => (
            <button
              key={sheet.sheetName}
              className={
                sheet.sheetName === selectedSheet.sheetName
                  ? "sheet-button sheet-button--active"
                  : "sheet-button"
              }
              type="button"
              aria-current={
                sheet.sheetName === selectedSheet.sheetName
                  ? "true"
                  : undefined
              }
              onClick={() => setSelectedSheetName(sheet.sheetName)}
            >
              <span>
                <Icon name="table" size={16} />
                <strong>{sheet.sheetName}</strong>
              </span>
              <small>
                {sheet.detection.detectedModule
                  ? MODULE_LABELS[sheet.detection.detectedModule]
                  : "待识别"}{" "}
                · {sheet.validRows}/{sheet.totalRows}
              </small>
              <Icon name="chevron" size={15} />
            </button>
          ))}
        </nav>

        <div className="sheet-detail">
          <div className="sheet-detail__heading">
            <div>
              <span className="section-label">FIELD MAPPING</span>
              <h3>{selectedSheet.sheetName}</h3>
            </div>
            <span>
              {selectedSheet.mappings.filter(
                (mapping) => mapping.status === "mapped",
              ).length}{" "}
              个字段已映射
            </span>
          </div>

          {selectedSheet.detection.reasons.length > 0 && (
            <div className="detection-reasons">
              <strong>识别依据</strong>
              <ul>
                {selectedSheet.detection.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mapping-table-wrap">
            <table className="mapping-table">
              <thead>
                <tr>
                  <th>原始字段</th>
                  <th>标准字段</th>
                  <th>状态</th>
                  <th>映射依据</th>
                </tr>
              </thead>
              <tbody>
                {selectedSheet.mappings.map((mapping) => {
                  const overrideKey = getMappingOverrideKey(
                    selectedSheet.sheetName,
                    mapping.columnIndex,
                    mapping.rawHeader,
                  );
                  return (
                    <tr key={overrideKey}>
                      <td>
                        <strong>{mapping.rawHeader}</strong>
                        <small>第 {mapping.columnIndex + 1} 列</small>
                      </td>
                      <td>
                        <select
                          value={currentMappingValue(
                            slot,
                            selectedSheet.sheetName,
                            mapping,
                          )}
                          disabled={
                            result.parserMode === "synthetic-mock" ||
                            slot.status === "parsing"
                          }
                          aria-label={`映射字段 ${mapping.rawHeader}`}
                          onChange={(event) => {
                            const value = event.target.value;
                            if (value === "__auto__") {
                              onMappingChange(overrideKey, undefined);
                            } else if (value === "__ignore__") {
                              onMappingChange(overrideKey, null);
                            } else if (isStandardField(value)) {
                              onMappingChange(overrideKey, value);
                            }
                          }}
                        >
                          <option value="__auto__">
                            自动：
                            {mapping.standardField
                              ? FIELD_LABELS[mapping.standardField]
                              : "未映射"}
                          </option>
                          <option value="__ignore__">忽略此字段</option>
                          {MODULE_FIELDS[mappingModule].map((field) => (
                            <option key={field} value={field}>
                              {FIELD_LABELS[field]}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <span
                          className={`mapping-status mapping-status--${mapping.status}`}
                        >
                          {mapping.status === "mapped"
                            ? "已映射"
                            : mapping.status === "conflict"
                              ? "有冲突"
                              : "未映射"}
                        </span>
                      </td>
                      <td>{mapping.reason}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {(selectedSheet.unmappedFields.length > 0 ||
            selectedSheet.missingCriticalFields.length > 0) && (
            <div className="field-groups">
              {selectedSheet.unmappedFields.length > 0 && (
                <div>
                  <strong>未映射字段</strong>
                  <div className="tag-list">
                    {selectedSheet.unmappedFields.map((field) => (
                      <span key={field}>{field}</span>
                    ))}
                  </div>
                </div>
              )}
              {selectedSheet.missingCriticalFields.length > 0 && (
                <div>
                  <strong>缺失关键字段</strong>
                  <div className="tag-list tag-list--danger">
                    {selectedSheet.missingCriticalFields.map((field) => (
                      <span key={field}>{FIELD_LABELS[field]}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="preview-section">
            <div className="section-heading">
              <div>
                <span className="section-label">NORMALIZED PREVIEW</span>
                <h3>标准化预览</h3>
              </div>
              <span>最多显示前 {selectedSheet.preview.length} 条</span>
            </div>

            {selectedSheet.preview.length === 0 ||
            mappedColumns.length === 0 ? (
              <EmptyState
                icon="table"
                title="暂无可预览记录"
                description="请先解决模块或关键字段识别问题。"
              />
            ) : (
              <div className="preview-table-wrap">
                <table className="preview-table">
                  <thead>
                    <tr>
                      <th>来源行</th>
                      {mappedColumns.map((field) => (
                        <th key={field}>{FIELD_LABELS[field]}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {selectedSheet.preview.map((record) => (
                      <tr
                        key={`${record.source.sheetName}-${record.source.rowNumber}`}
                        className={record.isDuplicate ? "duplicate-row" : ""}
                      >
                        <td>
                          <span className="source-cell">
                            {record.source.sheetName} ·{" "}
                            {record.source.rowNumber}
                          </span>
                        </td>
                        {mappedColumns.map((field) => (
                          <td key={field} title={formatValue(recordValue(record, field), field)}>
                            {formatValue(recordValue(record, field), field)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="quality-section">
            <div className="section-heading">
              <div>
                <span className="section-label">DATA QUALITY</span>
                <h3>质量问题与提示</h3>
              </div>
              <span>{selectedSheet.issues.length} 项</span>
            </div>

            {sortedIssues.length === 0 ? (
              <div className="quality-clear">
                <Icon name="check" size={18} />
                <span>未发现阻断性问题。</span>
              </div>
            ) : (
              <ul className="issue-list">
                {sortedIssues.slice(0, 12).map((issue, index) => (
                  <li
                    key={`${issue.code}-${issue.rowNumber ?? "sheet"}-${index}`}
                    className={`issue-item issue-item--${issue.severity}`}
                  >
                    <Icon
                      name={issue.severity === "info" ? "table" : "alert"}
                      size={17}
                    />
                    <div>
                      <strong>
                        {issue.code}
                        {issue.rowNumber ? ` · 第 ${issue.rowNumber} 行` : ""}
                      </strong>
                      <p>{issue.message}</p>
                      {issue.rawValue !== undefined && (
                        <small>
                          原始值：{displayRawValue(issue.rawValue)}
                        </small>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      <footer className="recognition-actions">
        <div>
          <Icon name="shield" size={18} />
          <span>确认仅代表字段识别无误，不代表已完成指标分析。</span>
        </div>
        <div>
          {slot.mappingDirty && slot.file && (
            <button
              className="secondary-button"
              type="button"
              onClick={onApplyMappings}
            >
              <Icon name="refresh" size={16} />
              应用映射并重新校验
            </button>
          )}
          <button
            className="primary-button"
            type="button"
            disabled={!canConfirm || slot.confirmed}
            onClick={onConfirm}
          >
            <Icon name={slot.confirmed ? "check" : "arrow"} size={16} />
            {slot.confirmed
              ? result.parserMode === "synthetic-mock"
                ? "示例已确认"
                : "模块已确认"
              : `确认 ${MODULE_CONFIG[module].label} 识别结果`}
          </button>
        </div>
      </footer>
    </section>
  );
}
