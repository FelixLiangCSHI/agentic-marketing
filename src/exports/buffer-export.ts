import type {
  ActionPlan,
  ContentCalendarItem,
  ContentValidationStatus,
} from "@/domain/action-plan";
import {
  BUFFER_CHANNEL_DEFINITIONS,
  BUFFER_OFFICIAL_GUIDANCE,
  type BufferExportArtifact,
  type BufferExportIssueCode,
  type BufferExportIssueSeverity,
  type BufferExportRecord,
  type BufferExportValidationIssue,
  type BufferHandoffExportResult,
  type BufferHandoffOptions,
  type BufferHandoffPreview,
  type BufferItemReview,
  type BufferSupportedChannel,
} from "@/domain/buffer-handoff";
import { csvDocument, safeFileSlug } from "@/exports/csv-utils";
import {
  addDays,
  isValidIanaTimeZone,
  isValidIsoDate,
  isValidTime,
  localDateInTimeZone,
  zonedDateTimeToUtc,
} from "@/utils/date-time";
import { stableId } from "@/utils/stable-id";

const DIRECT_IMAGE_PATTERN = /\.(?:gif|heic|jpe?g|png|webp)$/i;

export type BufferExportErrorCode =
  | "INVALID_HANDOFF_OPTIONS"
  | "WARNING_ACKNOWLEDGEMENT_REQUIRED"
  | "NO_EXPORTABLE_CONTENT";

export class BufferExportError extends Error {
  constructor(
    public readonly code: BufferExportErrorCode,
    message: string,
    public readonly issues: BufferExportValidationIssue[] = [],
  ) {
    super(message);
    this.name = "BufferExportError";
  }
}

function issue(
  code: BufferExportIssueCode,
  severity: BufferExportIssueSeverity,
  contentItemId: string | null,
  field: string | null,
  message: string,
  suggestedAction: string,
  blocksExport = severity === "error",
): BufferExportValidationIssue {
  return {
    code,
    severity,
    contentItemId,
    field,
    message,
    suggestedAction,
    blocksExport,
  };
}

function httpUrl(value: string): URL | null {
  try {
    const parsed = new URL(value);
    if (
      (parsed.protocol !== "https:" && parsed.protocol !== "http:") ||
      parsed.username ||
      parsed.password
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function isDirectImageUrl(value: string): boolean {
  const parsed = httpUrl(value);
  return parsed !== null && DIRECT_IMAGE_PATTERN.test(parsed.pathname);
}

export function defaultBufferDateRange(
  timeZone: string,
  now: Date = new Date(),
): { start: string; end: string } {
  const start = localDateInTimeZone(now, timeZone);
  if (!start) {
    throw new BufferExportError(
      "INVALID_HANDOFF_OPTIONS",
      `Time zone ${timeZone} is not supported.`,
      [
        issue(
          "INVALID_HANDOFF_TIME_ZONE",
          "error",
          null,
          "timeZone",
          `Time zone ${timeZone} is not supported.`,
          "Select a valid IANA time zone and retry.",
        ),
      ],
    );
  }
  return { start, end: addDays(start, 13) };
}

export function composeBufferPostText(item: ContentCalendarItem): string {
  if (!item.linkUrl || item.postText.includes(item.linkUrl)) {
    return item.postText;
  }
  const separator = item.postText.endsWith("\n") ? "\n" : "\n\n";
  return `${item.postText}${separator}${item.linkUrl}`;
}

function validationStatus(
  issues: readonly BufferExportValidationIssue[],
): ContentValidationStatus {
  if (issues.some((item) => item.severity === "error")) {
    return "error";
  }
  if (issues.some((item) => item.severity === "warning")) {
    return "warning";
  }
  return "ready";
}

function applyReviewValidation(
  plan: ActionPlan,
  reviews: readonly BufferItemReview[],
): ActionPlan {
  const byId = new Map(
    reviews.map((review) => [review.contentItem.itemId, review]),
  );
  return {
    ...plan,
    contentCalendar: plan.contentCalendar.map((item) => {
      const review = byId.get(item.itemId);
      if (!review) {
        return item;
      }
      const status = validationStatus(review.issues);
      const preserveWorkflow =
        item.workflowStatus === "exported_to_buffer" ||
        item.workflowStatus === "published";
      return {
        ...item,
        validationStatus: status,
        validationIssues: review.issues
          .filter((candidate) => candidate.severity !== "info")
          .map((candidate) => candidate.code),
        workflowStatus: preserveWorkflow
          ? item.workflowStatus
          : item.status === "confirmed" && status !== "error"
            ? "ready_for_buffer"
            : "planning",
      };
    }),
  };
}

function itemIssues(
  item: ContentCalendarItem,
  options: BufferHandoffOptions,
  now: Date,
  previouslyExportedIds: ReadonlySet<string>,
): BufferExportValidationIssue[] {
  const issues: BufferExportValidationIssue[] = [];
  const channelDefinition = BUFFER_CHANNEL_DEFINITIONS[item.channel];

  if (!options.channels.includes(item.channel)) {
    issues.push(
      issue(
        "CHANNEL_FILTERED_OUT",
        "info",
        item.itemId,
        "channel",
        "This content does not belong to a selected channel.",
        "Select the channel in the filter to include it.",
        false,
      ),
    );
  }
  if (
    isValidIsoDate(item.date) &&
    (item.date < options.dateRange.start || item.date > options.dateRange.end)
  ) {
    issues.push(
      issue(
        "OUTSIDE_DATE_RANGE",
        "info",
        item.itemId,
        "date",
        "This content is outside the export date range and remains in the 30-day plan.",
        "Adjust the date range or retain it for a later handoff.",
        false,
      ),
    );
  }
  if (item.status !== "confirmed") {
    issues.push(
      issue(
        "CONTENT_NOT_APPROVED",
        "error",
        item.itemId,
        "status",
        "Only reviewer-approved content can be handed off to Buffer.",
        "Complete review and set the content status to approved.",
      ),
    );
  }
  if (item.workflowStatus === "published") {
    issues.push(
      issue(
        "WORKFLOW_NOT_EXPORTABLE",
        "error",
        item.itemId,
        "workflowStatus",
        "This content is marked as published and should not be scheduled again.",
        "Confirm its status or duplicate it as a new plan item.",
      ),
    );
  } else if (item.workflowStatus === "failed") {
    issues.push(
      issue(
        "WORKFLOW_NOT_EXPORTABLE",
        "warning",
        item.itemId,
        "workflowStatus",
        "This content previously failed handoff and will be retried.",
        "Confirm the previous issue is resolved before continuing.",
        false,
      ),
    );
  }
  if (
    item.workflowStatus === "exported_to_buffer" ||
    previouslyExportedIds.has(item.itemId)
  ) {
    issues.push(
      issue(
        "ALREADY_EXPORTED",
        "warning",
        item.itemId,
        "workflowStatus",
        "A Buffer handoff file already includes this content, making this a duplicate export.",
        "Confirm this will not create a duplicate schedule in Buffer.",
        false,
      ),
    );
  }
  if (!item.postText.trim()) {
    issues.push(
      issue(
        "EMPTY_POST_TEXT",
        "error",
        item.itemId,
        "postText",
        "Publishing copy is empty.",
        "Add reviewed copy; the exporter does not create or infer it.",
      ),
    );
  }
  if (!channelDefinition) {
    issues.push(
      issue(
        "UNSUPPORTED_CHANNEL",
        "error",
        item.itemId,
        "channel",
        "The current Buffer adapter does not support this channel.",
        "Select a supported channel.",
      ),
    );
  }
  if (!isValidIsoDate(item.date)) {
    issues.push(
      issue(
        "INVALID_SCHEDULE_DATE",
        "error",
        item.itemId,
        "date",
        "The scheduled date is invalid.",
        "Use a valid YYYY-MM-DD date.",
      ),
    );
  }
  if (!isValidTime(item.scheduledTime)) {
    issues.push(
      issue(
        "INVALID_SCHEDULE_TIME",
        "error",
        item.itemId,
        "scheduledTime",
        "The scheduled time is invalid.",
        "Use 24-hour HH:mm format.",
      ),
    );
  }
  if (!isValidIanaTimeZone(item.timeZone)) {
    issues.push(
      issue(
        "INVALID_ITEM_TIME_ZONE",
        "error",
        item.itemId,
        "timeZone",
        "The content item time zone is not a valid IANA time zone.",
        "Select a supported IANA time zone.",
      ),
    );
  } else if (item.timeZone !== options.timeZone) {
    issues.push(
      issue(
        "HANDOFF_TIME_ZONE_MISMATCH",
        "error",
        item.itemId,
        "timeZone",
        `Content time zone ${item.timeZone} differs from handoff time zone ${options.timeZone}.`,
        "Align content and handoff time zones; CSV does not contain a time-zone column.",
      ),
    );
  }
  if (
    isValidIsoDate(item.date) &&
    isValidTime(item.scheduledTime) &&
    isValidIanaTimeZone(item.timeZone)
  ) {
    const scheduledAt = zonedDateTimeToUtc(
      item.date,
      item.scheduledTime,
      item.timeZone,
    );
    if (!scheduledAt) {
      issues.push(
        issue(
          "INVALID_SCHEDULE_TIME",
          "error",
          item.itemId,
          "scheduledTime",
          "This local time does not exist, possibly due to a daylight-saving transition.",
          "Select a valid local time in this time zone.",
        ),
      );
    } else if (scheduledAt.valueOf() <= now.valueOf()) {
      issues.push(
        issue(
          "SCHEDULE_IN_PAST",
          "error",
          item.itemId,
          "scheduledTime",
          "The scheduled time is in the past after UTC conversion.",
          "Adjust the date or time and revalidate.",
        ),
      );
    }
  }
  if (item.linkUrl && !httpUrl(item.linkUrl)) {
    issues.push(
      issue(
        "INVALID_LINK_URL",
        "error",
        item.itemId,
        "linkUrl",
        "The link must be a public HTTP(S) URL without embedded credentials.",
        "Correct the link or clear the optional field.",
      ),
    );
  }
  if (item.mediaUrls.length > 1) {
    issues.push(
      issue(
        "TOO_MANY_MEDIA",
        "error",
        item.itemId,
        "mediaUrls",
        "Buffer bulk upload supports one image per content item.",
        "Retain one direct image URL and handle other assets manually in Buffer.",
      ),
    );
  }
  for (const mediaUrl of item.mediaUrls) {
    if (!httpUrl(mediaUrl)) {
      issues.push(
        issue(
          "INVALID_MEDIA_URL",
          "error",
          item.itemId,
          "mediaUrls",
          "The media link must be a public HTTP(S) URL without embedded credentials.",
          "Replace it with a public direct image URL.",
        ),
      );
    } else if (!isDirectImageUrl(mediaUrl)) {
      issues.push(
        issue(
          "MEDIA_URL_NOT_DIRECT",
          "error",
          item.itemId,
          "mediaUrls",
          "The media link does not appear to be a direct image URL.",
          "Use a URL ending in jpg, png, gif, webp, or heic that opens the image directly.",
        ),
      );
    }
  }
  if (
    item.contentFormat.includes("carousel") ||
    item.contentFormat.includes("video")
  ) {
    issues.push(
      issue(
        "UNSUPPORTED_BULK_POST_TYPE",
        "error",
        item.itemId,
        "contentFormat",
        "Buffer CSV bulk upload does not support video or carousel content.",
        "Use text or a single image, or create the content manually in Buffer.",
      ),
    );
  } else if (item.mediaRequirement && item.mediaUrls.length === 0) {
    issues.push(
      issue(
        "MISSING_PLANNED_MEDIA",
        "warning",
        item.itemId,
        "mediaUrls",
        "The plan requires media but has no direct image URL; CSV can still carry the text.",
        "Add a direct image URL before export or add the image manually in Buffer.",
        false,
      ),
    );
  }
  if (item.campaignTag) {
    issues.push(
      issue(
        "BUFFER_TAG_MUST_EXIST",
        "warning",
        item.itemId,
        "campaignTag",
        "Buffer tags are case-sensitive and must already exist in the workspace.",
        "Confirm the matching tag exists in Buffer or it will be ignored.",
        false,
      ),
    );
  }
  if (
    channelDefinition &&
    composeBufferPostText(item).length > channelDefinition.maxTextLength
  ) {
    issues.push(
      issue(
        "TEXT_TOO_LONG",
        "error",
        item.itemId,
        "postText",
        `Copy and link exceed ${channelDefinition.maxTextLength} characters.`,
        "Edit the copy; the exporter does not truncate it silently.",
      ),
    );
  }
  return issues;
}

function addPairWarnings(
  reviews: BufferItemReview[],
  code: "SCHEDULE_CONFLICT" | "DUPLICATE_CONTENT",
  keyFor: (item: ContentCalendarItem) => string,
  field: string,
  message: string,
  suggestedAction: string,
): void {
  const groups = new Map<string, BufferItemReview[]>();
  for (const review of reviews) {
    if (
      !review.selected ||
      !review.inDateRange ||
      !review.channelIncluded
    ) {
      continue;
    }
    const key = keyFor(review.contentItem);
    const group = groups.get(key) ?? [];
    group.push(review);
    groups.set(key, group);
  }
  for (const group of groups.values()) {
    if (group.length < 2) {
      continue;
    }
    for (const review of group) {
      review.issues.push(
        issue(
          code,
          "warning",
          review.contentItem.itemId,
          field,
          message,
          suggestedAction,
          false,
        ),
      );
    }
  }
}

export function validateBufferHandoff(
  plan: ActionPlan,
  options: BufferHandoffOptions,
  now: Date = new Date(),
): BufferHandoffPreview {
  const globalIssues: BufferExportValidationIssue[] = [];
  const validRange =
    isValidIsoDate(options.dateRange.start) &&
    isValidIsoDate(options.dateRange.end) &&
    options.dateRange.end >= options.dateRange.start;
  if (!validRange) {
    globalIssues.push(
      issue(
        "INVALID_DATE_RANGE",
        "error",
        null,
        "dateRange",
        "The export date range is invalid; the end cannot precede the start.",
        "Select valid start and end dates.",
      ),
    );
  }
  if (options.channels.length === 0) {
    globalIssues.push(
      issue(
        "NO_CHANNEL_SELECTED",
        "error",
        null,
        "channels",
        "No target channel is selected.",
        "Select at least one supported channel.",
      ),
    );
  }
  if (!isValidIanaTimeZone(options.timeZone)) {
    globalIssues.push(
      issue(
        "INVALID_HANDOFF_TIME_ZONE",
        "error",
        null,
        "timeZone",
        "The handoff time zone is invalid.",
        "Select a valid IANA time zone.",
      ),
    );
  }
  globalIssues.push(
    issue(
      "TEMPLATE_TIME_ZONE_NOT_EMBEDDED",
      "info",
      null,
      "timeZone",
      "Buffer CSV has no time-zone column; Posting Time uses the target channel time zone configured in Buffer.",
      `Before import, confirm the Buffer channel time zone is ${options.timeZone} and verify times in preview.`,
      false,
    ),
  );

  const selectedIds = new Set(options.selectedItemIds);
  const previouslyExportedIds = new Set(
    options.previousExports.flatMap((record) => record.exportedItemIds),
  );
  const channelSet = new Set(options.channels);
  const reviews = plan.contentCalendar.map<BufferItemReview>((contentItem) => {
    const inDateRange =
      validRange &&
      isValidIsoDate(contentItem.date) &&
      contentItem.date >= options.dateRange.start &&
      contentItem.date <= options.dateRange.end;
    const channelIncluded = channelSet.has(contentItem.channel);
    const issues = itemIssues(
      contentItem,
      options,
      now,
      previouslyExportedIds,
    );
    const hasBlockingIssue = issues.some((candidate) => candidate.blocksExport);
    return {
      contentItem,
      selected: selectedIds.has(contentItem.itemId),
      inDateRange,
      channelIncluded,
      issues,
      canExport:
        selectedIds.has(contentItem.itemId) &&
        inDateRange &&
        channelIncluded &&
        !hasBlockingIssue &&
        !globalIssues.some((candidate) => candidate.blocksExport),
    };
  });

  addPairWarnings(
    reviews,
    "SCHEDULE_CONFLICT",
    (item) => `${item.channel}|${item.date}|${item.scheduledTime}`,
    "scheduledTime",
    "Multiple handoff items use the same channel and time.",
    "Review the Buffer queue or adjust one item's time.",
  );
  addPairWarnings(
    reviews,
    "DUPLICATE_CONTENT",
    (item) =>
      `${item.channel}|${composeBufferPostText(item)
        .normalize("NFKC")
        .trim()
        .replace(/\s+/g, " ")
        .toLocaleLowerCase("en-US")}`,
    "postText",
    "Duplicate copy exists for the same channel.",
    "Confirm the repeated publication is intentional.",
  );

  const channelCounts: Partial<Record<BufferSupportedChannel, number>> = {};
  for (const review of reviews.filter((candidate) => candidate.canExport)) {
    channelCounts[review.contentItem.channel] =
      (channelCounts[review.contentItem.channel] ?? 0) + 1;
  }
  const mayExceedFreeQueue = Object.entries(channelCounts).some(
    ([, count]) =>
      (count ?? 0) >
      BUFFER_OFFICIAL_GUIDANCE.freePlan.queueCapacityPerChannel,
  );
  if (mayExceedFreeQueue) {
    globalIssues.push(
      issue(
        "FREE_PLAN_QUEUE_LIMIT",
        "warning",
        null,
        "channels",
        `At least one channel exceeds the documented free queue capacity of ${BUFFER_OFFICIAL_GUIDANCE.freePlan.queueCapacityPerChannel} items.`,
        "Export in date-based batches or confirm capacity for the current Buffer plan.",
        false,
      ),
    );
  }

  const selectedReviews = reviews.filter(
    (review) =>
      review.selected && review.inDateRange && review.channelIncluded,
  );
  const warningCount =
    selectedReviews.reduce(
      (total, review) =>
        total +
        review.issues.filter((candidate) => candidate.severity === "warning")
          .length,
      0,
    ) +
    globalIssues.filter((candidate) => candidate.severity === "warning").length;
  const blockingErrorCount =
    selectedReviews.reduce(
      (total, review) =>
        total + review.issues.filter((candidate) => candidate.blocksExport).length,
      0,
    ) +
    globalIssues.filter((candidate) => candidate.blocksExport).length;
  const exportableCount = reviews.filter((review) => review.canExport).length;
  const updatedPlan = applyReviewValidation(plan, reviews);

  return {
    generatedAt: now.toISOString(),
    dateRange: { ...options.dateRange },
    timeZone: options.timeZone,
    channels: [...options.channels],
    reviews: reviews.map((review) => ({
      ...review,
      contentItem:
        updatedPlan.contentCalendar.find(
          (item) => item.itemId === review.contentItem.itemId,
        ) ?? review.contentItem,
    })),
    globalIssues,
    summary: {
      totalItemCount: reviews.length,
      selectedCount: selectedReviews.length,
      exportableCount,
      excludedCount: reviews.length - exportableCount,
      blockingErrorCount,
      warningCount,
      requiresWarningAcknowledgement: warningCount > 0,
      mayExceedFreeQueue,
      channelCounts,
    },
    updatedPlan,
    guidance: BUFFER_OFFICIAL_GUIDANCE,
  };
}

export function generateBufferChannelCsv(
  channel: BufferSupportedChannel,
  items: readonly ContentCalendarItem[],
): string {
  const definition = BUFFER_CHANNEL_DEFINITIONS[channel];
  const rows: unknown[][] = [
    [...definition.officialCsvHeaders],
    ...items.map((item) => [
      composeBufferPostText(item),
      item.mediaUrls[0] ?? "",
      item.campaignTag ?? "",
      `${item.date} ${item.scheduledTime}`,
    ]),
  ];
  return csvDocument(rows);
}

function bufferFileName(
  projectId: string,
  channel: BufferSupportedChannel,
  options: BufferHandoffOptions,
  generatedAt: Date,
): string {
  return [
    safeFileSlug(projectId, "linkedin-project"),
    "buffer",
    BUFFER_CHANNEL_DEFINITIONS[channel].fileSlug,
    options.dateRange.start,
    "to",
    options.dateRange.end,
    generatedAt.toISOString().slice(0, 10),
  ].join("-") + ".csv";
}

export function createBufferHandoffExport(
  plan: ActionPlan,
  projectId: string,
  options: BufferHandoffOptions,
  now: Date = new Date(),
): BufferHandoffExportResult {
  const preview = validateBufferHandoff(plan, options, now);
  const globalErrors = preview.globalIssues.filter(
    (candidate) => candidate.blocksExport,
  );
  if (globalErrors.length > 0) {
    throw new BufferExportError(
      "INVALID_HANDOFF_OPTIONS",
      globalErrors[0].message,
      globalErrors,
    );
  }
  if (
    preview.summary.requiresWarningAcknowledgement &&
    !options.warningsAcknowledged
  ) {
    const warnings = [
      ...preview.globalIssues,
      ...preview.reviews.flatMap((review) => review.issues),
    ].filter((candidate) => candidate.severity === "warning");
    throw new BufferExportError(
      "WARNING_ACKNOWLEDGEMENT_REQUIRED",
      "Acknowledge the handoff warnings before continuing.",
      warnings,
    );
  }

  const exportableReviews = preview.reviews.filter(
    (review) => review.canExport,
  );
  if (exportableReviews.length === 0) {
    const errors = preview.reviews
      .filter((review) => review.selected)
      .flatMap((review) => review.issues)
      .filter((candidate) => candidate.blocksExport);
    throw new BufferExportError(
      "NO_EXPORTABLE_CONTENT",
      "No content is eligible for a Buffer handoff file.",
      errors,
    );
  }

  const artifacts: BufferExportArtifact[] = [];
  for (const channel of options.channels) {
    const items = exportableReviews
      .filter((review) => review.contentItem.channel === channel)
      .map((review) => review.contentItem);
    if (items.length === 0) {
      continue;
    }
    artifacts.push({
      channel,
      fileName: bufferFileName(projectId, channel, options, now),
      mimeType: "text/csv;charset=utf-8",
      content: generateBufferChannelCsv(channel, items),
      itemIds: items.map((item) => item.itemId),
    });
  }

  const exportedItemIds = artifacts.flatMap((artifact) => artifact.itemIds);
  const exportedSet = new Set(exportedItemIds);
  const selectedItemIds = new Set(options.selectedItemIds);
  const skippedItemIds = plan.contentCalendar
    .filter(
      (item) => selectedItemIds.has(item.itemId) && !exportedSet.has(item.itemId),
    )
    .map((item) => item.itemId);
  const generatedAt = now.toISOString();
  const exportRecord: BufferExportRecord = {
    exportId: stableId(
      "buffer-export",
      JSON.stringify({
        planId: plan.planId,
        generatedAt,
        exportedItemIds,
        dateRange: options.dateRange,
      }),
    ),
    generatedAt,
    dateRange: { ...options.dateRange },
    timeZone: options.timeZone,
    channels: artifacts.map((artifact) => artifact.channel),
    exportedItemIds,
    skippedItemIds,
    fileNames: artifacts.map((artifact) => artifact.fileName),
    status: skippedItemIds.length > 0 ? "partial" : "completed",
  };
  const updatedPlan: ActionPlan = {
    ...preview.updatedPlan,
    updatedAt: generatedAt,
    contentCalendar: preview.updatedPlan.contentCalendar.map((item) =>
      exportedSet.has(item.itemId)
        ? { ...item, workflowStatus: "exported_to_buffer" }
        : item,
    ),
    revisionHistory: [
      ...preview.updatedPlan.revisionHistory,
      {
        revisionId: stableId(
          "revision",
          `${plan.planId}|buffer-handoff|${generatedAt}`,
        ),
        changedAt: generatedAt,
        changeType: "buffer_handoff",
        summary: `Prepared Buffer handoff files: exported ${exportedItemIds.length} items and skipped ${skippedItemIds.length}; no items were marked published.`,
      },
    ],
  };

  return { preview, artifacts, exportRecord, updatedPlan };
}
