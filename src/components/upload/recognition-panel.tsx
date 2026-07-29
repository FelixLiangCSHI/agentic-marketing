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
    return "High confidence";
  }
  if (confidence === "medium") {
    return "Medium confidence";
  }
  return "Low confidence";
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
      ? new Intl.NumberFormat("en-US", {
          style: "percent",
          maximumFractionDigits: 2,
        }).format(value)
      : value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  return String(value);
}

function displayRawValue(value: RawCellValue): string {
  if (value === null) {
    return "Empty";
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
          title="Awaiting recognition results"
          description="Upload a file to review module detection, field mappings, normalized previews, and quality issues."
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
          title="The workbook has no displayable sheets"
          description="Export the file again and retry."
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
                    ? "database"
                    : "lock"
                }
                size={14}
              />
              {result.parserMode === "synthetic-mock"
                ? "Synthetic Mock"
                : "Temporary analysis · Not persisted"}
            </span>
            <span>{result.file.format.toLocaleUpperCase("en-US")}</span>
            <span>{formatFileSize(result.file.size)}</span>
          </div>
          <h2 id="recognition-title">{result.file.name}</h2>
          <p>
            {result.workbook.sheetCount} sheets recognized. Confirm the module and mappings before analysis.
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
            {selectedSheet.canProceed ? "Ready for next stage" : "Action required"}
          </span>
        </div>
      </header>

      {!moduleMatches && (
        <div className="callout callout--warning" role="alert">
          <Icon name="alert" size={20} />
          <div>
            <strong>Module does not match the upload slot</strong>
            <p>
              Recognized as{" "}
              {result.detectedModules.length
                ? result.detectedModules
                    .map((item) => MODULE_LABELS[item])
                    .join("、")
                : "Undetermined"}
              ; the upload slot is {MODULE_LABELS[module]}. Reanalyze using the slot if that assignment is correct.
            </p>
          </div>
          {slot.file && (
            <button
              className="secondary-button secondary-button--small"
              type="button"
              onClick={onManualOverride}
            >
              Reanalyze as {MODULE_LABELS[module]}
            </button>
          )}
        </div>
      )}

      {repeated && (
        <div className="callout callout--danger" role="alert">
          <Icon name="alert" size={20} />
          <div>
            <strong>Duplicate module detected</strong>
            <p>Another upload represents the same module. Remove or replace one before confirmation.</p>
          </div>
        </div>
      )}

      <div className="recognition-summary">
        <div>
          <span>Detected module</span>
          <strong>
            {detectedModule ? MODULE_LABELS[detectedModule] : "Manual selection required"}
          </strong>
        </div>
        <div>
          <span>Header row</span>
          <strong>
            {selectedSheet.headerRow
              ? `Row ${selectedSheet.headerRow}`
              : "Not located"}
          </strong>
        </div>
        <div>
          <span>Valid data</span>
          <strong>
            {selectedSheet.validRows.toLocaleString("en-US")} /{" "}
            {selectedSheet.totalRows.toLocaleString("en-US")} rows
          </strong>
        </div>
        <div>
          <span>Date range</span>
          <strong>
            {selectedSheet.dateRange
              ? `${selectedSheet.dateRange.start.slice(0, 10)} — ${selectedSheet.dateRange.end.slice(0, 10)}`
              : "Not recognized"}
          </strong>
        </div>
      </div>

      <div className="sheet-layout">
        <nav className="sheet-list" aria-label="Workbook sheets">
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
                  : "Pending"}{" "}
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
              fields mapped
            </span>
          </div>

          {selectedSheet.detection.reasons.length > 0 && (
            <div className="detection-reasons">
              <strong>Recognition evidence</strong>
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
                  <th>Source field</th>
                  <th>Standard field</th>
                  <th>Status</th>
                  <th>Mapping evidence</th>
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
                        <small>Column {mapping.columnIndex + 1}</small>
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
                          aria-label={`Map field ${mapping.rawHeader}`}
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
                            Automatic:
                            {mapping.standardField
                              ? FIELD_LABELS[mapping.standardField]
                              : "Unmapped"}
                          </option>
                          <option value="__ignore__">Ignore this field</option>
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
                            ? "Mapped"
                            : mapping.status === "conflict"
                              ? "Conflict"
                              : "Unmapped"}
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
                  <strong>Unmapped fields</strong>
                  <div className="tag-list">
                    {selectedSheet.unmappedFields.map((field) => (
                      <span key={field}>{field}</span>
                    ))}
                  </div>
                </div>
              )}
              {selectedSheet.missingCriticalFields.length > 0 && (
                <div>
                  <strong>Missing required fields</strong>
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
                <h3>Normalized preview</h3>
              </div>
              <span>Showing up to {selectedSheet.preview.length} records</span>
            </div>

            {selectedSheet.preview.length === 0 ||
            mappedColumns.length === 0 ? (
              <EmptyState
                icon="table"
                title="No preview records available"
                description="Resolve module or required-field recognition first."
              />
            ) : (
              <div className="preview-table-wrap">
                <table className="preview-table">
                  <thead>
                    <tr>
                      <th>Source row</th>
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
                <h3>Quality issues and notices</h3>
              </div>
              <span>{selectedSheet.issues.length} items</span>
            </div>

            {sortedIssues.length === 0 ? (
              <div className="quality-clear">
                <Icon name="check" size={18} />
                <span>No blocking issues found.</span>
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
                        {issue.rowNumber ? ` · Row ${issue.rowNumber}` : ""}
                      </strong>
                      <p>{issue.message}</p>
                      {issue.rawValue !== undefined && (
                        <small>
                          Source value: {displayRawValue(issue.rawValue)}
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
          <span>Confirmation verifies field recognition only; metric analysis follows.</span>
        </div>
        <div>
          {slot.mappingDirty && slot.file && (
            <button
              className="secondary-button"
              type="button"
              onClick={onApplyMappings}
            >
              <Icon name="refresh" size={16} />
              Apply mappings and revalidate
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
                ? "Demo confirmed"
                : "Module confirmed"
              : `Confirm ${MODULE_CONFIG[module].label} recognition`}
          </button>
        </div>
      </footer>
    </section>
  );
}
