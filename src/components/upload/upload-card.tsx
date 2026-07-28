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
    return "安全解析中";
  }
  if (slot.status === "error") {
    return "需要处理";
  }
  if (slot.confirmed) {
    return "已确认";
  }
  if (slot.status === "parsed") {
    return "待确认";
  }
  return "待上传";
}

function aggregateDateRange(slot: UploadSlotState): string {
  const ranges =
    slot.result?.workbook.sheets.flatMap((sheet) =>
      sheet.dateRange ? [sheet.dateRange] : [],
    ) ?? [];

  if (ranges.length === 0) {
    return "未识别";
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
        aria-label={`选择 ${config.label} 数据文件`}
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
          <strong>拖拽文件到这里</strong>
          <span>或</span>
          <button
            className="text-button"
            type="button"
            onClick={() => inputRef.current?.click()}
          >
            浏览本地文件
          </button>
          <small>
            XLSX、XLS、CSV · 最大 {formatFileSize(MAX_UPLOAD_SIZE_BYTES)}
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
              <p>正在服务端校验签名、定位表头并规范化数据…</p>
            </div>
          )}

          {slot.result && (
            <dl className="file-meta-grid">
              <div>
                <dt>Sheet</dt>
                <dd>{slot.result.workbook.sheetCount}</dd>
              </div>
              <div>
                <dt>有效行</dt>
                <dd>
                  {slot.result.validRows.toLocaleString("zh-CN")} /{" "}
                  {slot.result.totalRows.toLocaleString("zh-CN")}
                </dd>
              </div>
              <div>
                <dt>时间范围</dt>
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
              <span>同一模块已在其他上传卡片中出现，请移除或重新选择。</span>
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
                查看识别
              </button>
            )}
            <button
              className="icon-text-button"
              type="button"
              disabled={slot.status === "parsing"}
              onClick={() => inputRef.current?.click()}
            >
              <Icon name="refresh" size={15} />
              重新选择
            </button>
            <button
              className="icon-text-button icon-text-button--danger"
              type="button"
              disabled={slot.status === "parsing"}
              onClick={onRemove}
            >
              <Icon name="trash" size={15} />
              移除
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
