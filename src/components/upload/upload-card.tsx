"use client";

import { useRef, useState, type DragEvent } from "react";

import { Icon, type IconName } from "@/components/ui/icon";
import {
  ACCEPTED_FILE_TYPES,
  MAX_UPLOAD_SIZE_BYTES,
  formatFileSize,
} from "@/data-processing/file-validation";
import { MODULE_CONFIG } from "@/domain/module-config";
import type { LinkedInModule } from "@/domain/linkedin";
import type { UploadSlotState } from "@/state/ingestion-reducer";

interface UploadCardProps {
  module: LinkedInModule;
  slot: UploadSlotState;
  repeated: boolean;
  onFile: (file: File) => void;
  onRemove: () => void;
  onInspect: () => void;
}

const ICONS: Record<LinkedInModule, IconName> = {
  followers: "followers",
  visitors: "visitors",
  content: "content",
};

function statusLabel(slot: UploadSlotState): string {
  if (slot.status === "parsing") {
    return "Securely parsing";
  }
  if (slot.status === "error") {
    return "Action required";
  }
  if (slot.confirmed) {
    return "Confirmed";
  }
  if (slot.status === "parsed") {
    return "Pending confirmation";
  }
  return "Awaiting upload";
}

function aggregateDateRange(slot: UploadSlotState): string {
  const ranges =
    slot.result?.workbook.sheets.flatMap((sheet) =>
      sheet.dateRange ? [sheet.dateRange] : [],
    ) ?? [];

  if (ranges.length === 0) {
    return "Not recognized";
  }

  const starts = ranges.map(({ start }) => start).sort();
  const ends = ranges.map(({ end }) => end).sort();
  return `${starts[0].slice(0, 10)} — ${ends.at(-1)?.slice(0, 10)}`;
}

export function UploadCard({
  module,
  slot,
  repeated,
  onFile,
  onRemove,
  onInspect,
}: UploadCardProps) {
  const config = MODULE_CONFIG[module];
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileName = slot.file?.name ?? slot.result?.file.name;

  function chooseFile(file: File | undefined) {
    if (file) {
      onFile(file);
    }
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  return (
    <article
      className={`upload-card upload-card--${slot.status}${
        slot.confirmed ? " upload-card--confirmed" : ""
      }${repeated ? " upload-card--duplicate" : ""}`}
    >
      <div className="upload-card__header">
        <span className={`module-icon module-icon--${module}`}>
          <Icon name={ICONS[module]} size={20} />
        </span>
        <div>
          <span className="eyebrow">{config.label}</span>
          <h3>{config.title}</h3>
        </div>
        <span className={`status-pill status-pill--${slot.status}`}>
          {slot.status === "parsing" && (
            <Icon name="spinner" size={14} className="spin" />
          )}
          {slot.confirmed && <Icon name="check" size={14} />}
          {slot.status === "error" && <Icon name="alert" size={14} />}
          {statusLabel(slot)}
        </span>
      </div>

      <p className="upload-card__description">{config.description}</p>

      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept={ACCEPTED_FILE_TYPES}
        aria-label={`Select ${config.label} data file`}
        onChange={(event) => chooseFile(event.target.files?.[0])}
      />

      {slot.status === "idle" ? (
        <div
          className={`drop-zone${isDragging ? " drop-zone--active" : ""}`}
          onDragEnter={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          <span className="drop-zone__icon">
            <Icon name="upload" size={22} />
          </span>
          <strong>Drop a file here</strong>
          <span>or</span>
          <button
            className="text-button"
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            Browse files
          </button>
          <small>
            XLSX, XLS, CSV · Maximum {formatFileSize(MAX_UPLOAD_SIZE_BYTES)}
          </small>
        </div>
      ) : (
        <div className="file-summary">
          <div className="file-summary__name">
            <span className="file-icon">
              <Icon name="file" size={18} />
            </span>
            <div>
              <strong title={fileName}>{fileName}</strong>
              <span>
                {slot.result
                  ? `${slot.result.file.format.toLocaleUpperCase("en-US")} · ${formatFileSize(slot.result.file.size)}`
                  : formatFileSize(slot.file?.size ?? 0)}
              </span>
            </div>
          </div>

          {slot.status === "parsing" && (
            <div className="parse-progress" role="status">
              <span />
              <p>Validating the signature, locating headers, and normalizing data...</p>
            </div>
          )}

          {slot.result && (
            <dl className="file-meta-grid">
              <div>
                <dt>Sheet</dt>
                <dd>{slot.result.workbook.sheetCount}</dd>
              </div>
              <div>
                <dt>Valid rows</dt>
                <dd>
                  {slot.result.validRows.toLocaleString("en-US")} /{" "}
                  {slot.result.totalRows.toLocaleString("en-US")}
                </dd>
              </div>
              <div>
                <dt>Date range</dt>
                <dd>{aggregateDateRange(slot)}</dd>
              </div>
            </dl>
          )}

          {slot.error && (
            <div className="inline-error" role="alert">
              <Icon name="alert" size={17} />
              <div>
                <strong>{slot.error.code}</strong>
                <p>{slot.error.message}</p>
              </div>
            </div>
          )}

          {repeated && (
            <div className="inline-warning" role="alert">
              <Icon name="alert" size={17} />
              <span>This module appears in another upload. Remove or replace one file.</span>
            </div>
          )}

          <div className="file-summary__actions">
            {slot.result && (
              <button
                className="secondary-button secondary-button--small"
                type="button"
                onClick={onInspect}
              >
                <Icon name="table" size={15} />
                Review recognition
              </button>
            )}
            <button
              className="icon-text-button"
              type="button"
              disabled={slot.status === "parsing"}
              onClick={() => inputRef.current?.click()}
            >
              <Icon name="refresh" size={15} />
              Replace
            </button>
            <button
              className="icon-text-button icon-text-button--danger"
              type="button"
              disabled={slot.status === "parsing"}
              onClick={onRemove}
            >
              <Icon name="trash" size={15} />
              Remove
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
