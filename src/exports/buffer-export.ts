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
      `不支持时区 ${timeZone}。`,
      [
        issue(
          "INVALID_HANDOFF_TIME_ZONE",
          "error",
          null,
          "timeZone",
          `不支持时区 ${timeZone}。`,
          "请选择有效的 IANA 时区后重试。",
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
        "该内容不属于本次选择的渠道。",
        "如需导出，请在渠道筛选中选择该渠道。",
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
        "该内容不在本次导出日期范围内，仍保留在 30 天计划中。",
        "调整日期范围或保留到下一批交接。",
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
        "只有用户已确认的内容可以交付 Buffer。",
        "由 Lucy 审核后将内容状态设为已批准。",
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
        "该内容已被用户标记为 published，不应再次排期。",
        "确认实际状态；如需新版本，请复制为新的计划项。",
      ),
    );
  } else if (item.workflowStatus === "failed") {
    issues.push(
      issue(
        "WORKFLOW_NOT_EXPORTABLE",
        "warning",
        item.itemId,
        "workflowStatus",
        "该内容曾标记为交接失败，本次将作为重试。",
        "确认失败原因已修复后再继续。",
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
        "该内容已生成过 Buffer 交接文件，本次属于重复导出。",
        "确认不会在 Buffer 中创建重复排期后再继续。",
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
        "发布文案为空。",
        "补充经审核的发布文案，不会由导出器自动生成或猜测。",
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
        "当前 Buffer 适配器不支持该渠道。",
        "选择当前系统支持的渠道，或等待新增渠道级适配器。",
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
        "排期日期无效。",
        "使用 YYYY-MM-DD 格式的有效日期。",
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
        "排期时间无效。",
        "使用 24 小时 HH:mm 格式。",
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
        "内容项时区不是有效的 IANA 时区。",
        "选择受支持的 IANA 时区。",
      ),
    );
  } else if (item.timeZone !== options.timeZone) {
    issues.push(
      issue(
        "HANDOFF_TIME_ZONE_MISMATCH",
        "error",
        item.itemId,
        "timeZone",
        `内容项时区 ${item.timeZone} 与本次交接时区 ${options.timeZone} 不一致。`,
        "统一内容项和交接时区；CSV 本身不携带时区列。",
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
          "该本地时间不存在，可能落在夏令时跳转区间。",
          "选择该时区中真实存在的本地时间。",
        ),
      );
    } else if (scheduledAt.valueOf() <= now.valueOf()) {
      issues.push(
        issue(
          "SCHEDULE_IN_PAST",
          "error",
          item.itemId,
          "scheduledTime",
          "转换到 UTC 后的排期时间已经过去。",
          "调整日期或时间后重新校验。",
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
        "链接必须是有效的公开 HTTP(S) URL，且不能包含嵌入凭据。",
        "修正链接或清空可选链接字段。",
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
        "Buffer 官方批量上传当前仅支持每条内容一张图片。",
        "只保留一个直接图片 URL，其他素材在 Buffer 中手动处理。",
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
          "媒体链接必须是有效的公开 HTTP(S) URL，且不能包含嵌入凭据。",
          "替换为公开的直接图片 URL。",
        ),
      );
    } else if (!isDirectImageUrl(mediaUrl)) {
      issues.push(
        issue(
          "MEDIA_URL_NOT_DIRECT",
          "error",
          item.itemId,
          "mediaUrls",
          "媒体链接不像以图片扩展名结尾的直接图片 URL。",
          "使用能单独打开图片并以 jpg、png、gif、webp 或 heic 结尾的 URL。",
        ),
      );
    }
  }
  if (
    item.contentFormat.includes("轮播") ||
    item.contentFormat.includes("视频")
  ) {
    issues.push(
      issue(
        "UNSUPPORTED_BULK_POST_TYPE",
        "error",
        item.itemId,
        "contentFormat",
        "Buffer 官方 CSV 批量上传当前不支持视频或轮播内容。",
        "改为文字/单图版本，或在 Buffer Composer 中手动创建该内容。",
      ),
    );
  } else if (item.mediaRequirement && item.mediaUrls.length === 0) {
    issues.push(
      issue(
        "MISSING_PLANNED_MEDIA",
        "warning",
        item.itemId,
        "mediaUrls",
        "计划包含素材需求但尚未提供直接图片 URL；CSV 仍可交付文字。",
        "导出前补充直接图片 URL，或由 Lucy 在 Buffer 中手动添加图片。",
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
        "Buffer Tags 区分大小写，且必须已存在于 Lucy 的账户。",
        "在 Buffer 中确认同名 Tag 已存在，否则该 Tag 会被忽略。",
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
        `文案和链接合计超过 ${channelDefinition.maxTextLength} 个字符。`,
        "由 Lucy 编辑文案；导出器不会静默截断。",
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
        "导出日期范围无效，结束日期不能早于开始日期。",
        "选择有效的开始和结束日期。",
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
        "尚未选择目标渠道。",
        "至少选择一个当前支持的渠道。",
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
        "本次交接时区无效。",
        "选择有效的 IANA 时区。",
      ),
    );
  }
  globalIssues.push(
    issue(
      "TEMPLATE_TIME_ZONE_NOT_EMBEDDED",
      "info",
      null,
      "timeZone",
      "Buffer 官方通用 CSV 没有时区列；Posting Time 按目标渠道在 Buffer 中配置的时区解释。",
      `导入前确认 Buffer 渠道时区为 ${options.timeZone}，并在预览中复核时间。`,
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
    "同一渠道在同一时间存在多条待交接内容。",
    "在 Buffer 中确认队列或调整其中一条内容的时间。",
  );
  addPairWarnings(
    reviews,
    "DUPLICATE_CONTENT",
    (item) =>
      `${item.channel}|${composeBufferPostText(item)
        .normalize("NFKC")
        .trim()
        .replace(/\s+/g, " ")
        .toLocaleLowerCase("zh-CN")}`,
    "postText",
    "同一渠道存在重复文案。",
    "确认这是有意重复发布，而不是误操作。",
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
        `至少一个渠道的本次内容数超过当前官方资料所示 Free 队列容量 ${BUFFER_OFFICIAL_GUIDANCE.freePlan.queueCapacityPerChannel} 条。`,
        "按日期分批导出，或由 Lucy 根据当前 Buffer 套餐确认后继续。",
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
      "请先确认已审阅本次交接警告。",
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
      "没有可生成 Buffer 交接文件的内容。",
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
        summary: `生成 Buffer 交接文件：导出 ${exportedItemIds.length} 项，跳过 ${skippedItemIds.length} 项；未标记为 published。`,
      },
    ],
  };

  return { preview, artifacts, exportRecord, updatedPlan };
}
