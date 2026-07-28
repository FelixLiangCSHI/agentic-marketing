import type {
  ActionPlan,
  ContentCalendarItem,
  SocialChannel,
} from "@/domain/action-plan";

export type BufferSupportedChannel = SocialChannel;

export interface BufferChannelDefinition {
  key: BufferSupportedChannel;
  label: string;
  fileSlug: string;
  maxTextLength: number;
  officialCsvHeaders: readonly [
    "Text",
    "Image URL",
    "Tags",
    "Posting Time",
  ];
}

export const BUFFER_CHANNEL_DEFINITIONS: Record<
  BufferSupportedChannel,
  BufferChannelDefinition
> = {
  linkedin_page: {
    key: "linkedin_page",
    label: "LinkedIn Page",
    fileSlug: "linkedin-page",
    maxTextLength: 3_000,
    officialCsvHeaders: ["Text", "Image URL", "Tags", "Posting Time"],
  },
  linkedin_profile: {
    key: "linkedin_profile",
    label: "LinkedIn Profile",
    fileSlug: "linkedin-profile",
    maxTextLength: 3_000,
    officialCsvHeaders: ["Text", "Image URL", "Tags", "Posting Time"],
  },
};

export const BUFFER_SUPPORTED_CHANNELS = Object.freeze(
  Object.keys(BUFFER_CHANNEL_DEFINITIONS) as BufferSupportedChannel[],
);

export const BUFFER_OFFICIAL_GUIDANCE = {
  reviewedAt: "2026-07-28",
  bulkUploadArticle:
    "https://support.buffer.com/article/926-how-to-upload-posts-in-bulk-to-buffer",
  supportedChannelsArticle:
    "https://support.buffer.com/article/567-supported-channels",
  queueLimitArticle:
    "https://support.buffer.com/article/643-how-many-posts-can-i-schedule-in-advance",
  timeZoneArticle:
    "https://support.buffer.com/article/514-setting-up-your-timezones-and-posting-schedules",
  freePlan: {
    uploadLimitPerChannel: 10,
    queueCapacityPerChannel: 10,
  },
  paidPlan: {
    uploadLimitPerChannel: 100,
  },
  accountImportPreviewVerified: false,
  note:
    "字段依据 Buffer 官方帮助页；仍应从目标渠道设置下载最新模板并在 Buffer 预览中复核。",
} as const;

export interface BufferDateRange {
  start: string;
  end: string;
}

export type BufferExportIssueSeverity = "info" | "warning" | "error";

export type BufferExportIssueCode =
  | "INVALID_DATE_RANGE"
  | "NO_CHANNEL_SELECTED"
  | "INVALID_HANDOFF_TIME_ZONE"
  | "CONTENT_NOT_APPROVED"
  | "WORKFLOW_NOT_EXPORTABLE"
  | "EMPTY_POST_TEXT"
  | "UNSUPPORTED_CHANNEL"
  | "INVALID_SCHEDULE_DATE"
  | "INVALID_SCHEDULE_TIME"
  | "INVALID_ITEM_TIME_ZONE"
  | "HANDOFF_TIME_ZONE_MISMATCH"
  | "SCHEDULE_IN_PAST"
  | "OUTSIDE_DATE_RANGE"
  | "CHANNEL_FILTERED_OUT"
  | "INVALID_LINK_URL"
  | "INVALID_MEDIA_URL"
  | "MEDIA_URL_NOT_DIRECT"
  | "TOO_MANY_MEDIA"
  | "MISSING_PLANNED_MEDIA"
  | "UNSUPPORTED_BULK_POST_TYPE"
  | "TEXT_TOO_LONG"
  | "SCHEDULE_CONFLICT"
  | "DUPLICATE_CONTENT"
  | "ALREADY_EXPORTED"
  | "BUFFER_TAG_MUST_EXIST"
  | "FREE_PLAN_QUEUE_LIMIT"
  | "TEMPLATE_TIME_ZONE_NOT_EMBEDDED";

export interface BufferExportValidationIssue {
  code: BufferExportIssueCode;
  severity: BufferExportIssueSeverity;
  contentItemId: string | null;
  field: string | null;
  message: string;
  suggestedAction: string;
  blocksExport: boolean;
}

export interface BufferExportRecord {
  exportId: string;
  generatedAt: string;
  dateRange: BufferDateRange;
  timeZone: string;
  channels: BufferSupportedChannel[];
  exportedItemIds: string[];
  skippedItemIds: string[];
  fileNames: string[];
  status: "completed" | "partial" | "failed";
}

export interface BufferHandoffOptions {
  dateRange: BufferDateRange;
  timeZone: string;
  channels: BufferSupportedChannel[];
  selectedItemIds: string[];
  warningsAcknowledged: boolean;
  previousExports: BufferExportRecord[];
}

export interface BufferItemReview {
  contentItem: ContentCalendarItem;
  selected: boolean;
  inDateRange: boolean;
  channelIncluded: boolean;
  issues: BufferExportValidationIssue[];
  canExport: boolean;
}

export interface BufferHandoffSummary {
  totalItemCount: number;
  selectedCount: number;
  exportableCount: number;
  excludedCount: number;
  blockingErrorCount: number;
  warningCount: number;
  requiresWarningAcknowledgement: boolean;
  mayExceedFreeQueue: boolean;
  channelCounts: Partial<Record<BufferSupportedChannel, number>>;
}

export interface BufferHandoffPreview {
  generatedAt: string;
  dateRange: BufferDateRange;
  timeZone: string;
  channels: BufferSupportedChannel[];
  reviews: BufferItemReview[];
  globalIssues: BufferExportValidationIssue[];
  summary: BufferHandoffSummary;
  updatedPlan: ActionPlan;
  guidance: typeof BUFFER_OFFICIAL_GUIDANCE;
}

export interface BufferExportArtifact {
  channel: BufferSupportedChannel;
  fileName: string;
  mimeType: "text/csv;charset=utf-8";
  content: string;
  itemIds: string[];
}

export interface BufferHandoffExportResult {
  preview: BufferHandoffPreview;
  artifacts: BufferExportArtifact[];
  exportRecord: BufferExportRecord;
  updatedPlan: ActionPlan;
}
