import assert from "node:assert/strict";
import test from "node:test";

import {
  confirmActionPlan,
  generateActionPlan,
} from "@/agents/action-plan-agent";
import type { ActionPlan } from "@/domain/action-plan";
import {
  BUFFER_OFFICIAL_GUIDANCE,
  type BufferHandoffOptions,
} from "@/domain/buffer-handoff";
import {
  BufferExportError,
  createBufferHandoffExport,
  defaultBufferDateRange,
  generateBufferChannelCsv,
  validateBufferHandoff,
} from "@/exports/buffer-export";
import {
  approvedPlanningInput,
  PLANNING_NOW,
} from "@/tests/planning-fixtures";
import { zonedDateTimeToUtc } from "@/utils/date-time";

function exportablePlan(postsPerWeek = 3): ActionPlan {
  const input = approvedPlanningInput({
    preferences: {
      ...approvedPlanningInput().preferences,
      postsPerWeek,
    },
  });
  const plan = confirmActionPlan(
    generateActionPlan(input, PLANNING_NOW),
    PLANNING_NOW,
  );
  return {
    ...plan,
    contentCalendar: plan.contentCalendar.map((item, index) => ({
      ...item,
      contentFormat: "文字短帖",
      postText: `医疗器械临床证据审阅稿 ${index + 1}`,
      mediaRequirement: null,
      mediaUrls: [],
      linkUrl: null,
      campaignTag: null,
      workflowStatus: "planning",
      validationStatus: "not_validated",
      validationIssues: [],
    })),
  };
}

function options(
  plan: ActionPlan,
  overrides: Partial<BufferHandoffOptions> = {},
): BufferHandoffOptions {
  return {
    dateRange: { start: "2026-07-28", end: "2026-08-10" },
    timeZone: "Asia/Shanghai",
    channels: ["linkedin_page", "linkedin_profile"],
    selectedItemIds: plan.contentCalendar.map((item) => item.itemId),
    warningsAcknowledged: true,
    previousExports: [],
    ...overrides,
  };
}

test("calculates a continuous 14-day window across month and year boundaries", () => {
  assert.deepEqual(
    defaultBufferDateRange(
      "Asia/Shanghai",
      new Date("2026-07-31T01:00:00.000Z"),
    ),
    { start: "2026-07-31", end: "2026-08-13" },
  );
  assert.deepEqual(
    defaultBufferDateRange(
      "America/New_York",
      new Date("2026-12-31T15:00:00.000Z"),
    ),
    { start: "2026-12-31", end: "2027-01-13" },
  );
});

test("validates local wall-clock times across a daylight-saving boundary", () => {
  assert.equal(
    zonedDateTimeToUtc("2026-03-08", "02:30", "America/New_York"),
    null,
  );
  assert.equal(
    zonedDateTimeToUtc(
      "2026-03-08",
      "03:30",
      "America/New_York",
    )?.toISOString(),
    "2026-03-08T07:30:00.000Z",
  );
});

test("filters by approval, channel, and date range without deleting plan items", () => {
  const plan = exportablePlan();
  plan.contentCalendar[0].status = "ai_draft";
  const selectedChannel = plan.contentCalendar[1].channel;
  const preview = validateBufferHandoff(
    plan,
    options(plan, {
      channels: [selectedChannel],
      dateRange: {
        start: plan.contentCalendar[0].date,
        end: plan.contentCalendar[1].date,
      },
    }),
    PLANNING_NOW,
  );

  const draftReview = preview.reviews[0];
  assert.equal(draftReview.canExport, false);
  assert.ok(
    draftReview.issues.some((item) => item.code === "CONTENT_NOT_APPROVED"),
  );
  assert.equal(preview.updatedPlan.contentCalendar.length, plan.contentCalendar.length);
  assert.ok(
    preview.reviews.some((review) =>
      review.issues.some((item) => item.code === "CHANNEL_FILTERED_OUT"),
    ),
  );
  assert.ok(
    preview.reviews.some((review) =>
      review.issues.some((item) => item.code === "OUTSIDE_DATE_RANGE"),
    ),
  );
});

test("distinguishes blocking errors from confirmable warnings", () => {
  const plan = exportablePlan();
  plan.contentCalendar[0].postText = "";
  plan.contentCalendar[1].mediaRequirement = "需要一张 synthetic 图片";
  const handoffOptions = options(plan, { warningsAcknowledged: false });
  const preview = validateBufferHandoff(plan, handoffOptions, PLANNING_NOW);

  assert.equal(preview.reviews[0].canExport, false);
  assert.ok(
    preview.reviews[0].issues.some((item) => item.code === "EMPTY_POST_TEXT"),
  );
  assert.equal(preview.reviews[1].canExport, true);
  assert.ok(
    preview.reviews[1].issues.some(
      (item) => item.code === "MISSING_PLANNED_MEDIA",
    ),
  );
  assert.equal(preview.summary.requiresWarningAcknowledgement, true);
  assert.throws(
    () =>
      createBufferHandoffExport(
        plan,
        "synthetic-demo",
        handoffOptions,
        PLANNING_NOW,
      ),
    (reason) =>
      reason instanceof BufferExportError &&
      reason.code === "WARNING_ACKNOWLEDGEMENT_REQUIRED",
  );
});

test("invalid links, media URLs, unsupported formats, and conflicts are explicit", () => {
  const plan = exportablePlan();
  plan.contentCalendar[0] = {
    ...plan.contentCalendar[0],
    linkUrl: "javascript:alert(1)",
    mediaUrls: ["https://example.invalid/not-an-image"],
    contentFormat: "文档轮播",
  };
  plan.contentCalendar[1] = {
    ...plan.contentCalendar[1],
    channel: plan.contentCalendar[0].channel,
    date: plan.contentCalendar[0].date,
    scheduledTime: plan.contentCalendar[0].scheduledTime,
    postText: plan.contentCalendar[0].postText,
    linkUrl: plan.contentCalendar[0].linkUrl,
  };
  const preview = validateBufferHandoff(
    plan,
    options(plan),
    PLANNING_NOW,
  );
  const codes = preview.reviews.flatMap((review) =>
    review.issues.map((item) => item.code),
  );

  for (const code of [
    "INVALID_LINK_URL",
    "MEDIA_URL_NOT_DIRECT",
    "UNSUPPORTED_BULK_POST_TYPE",
    "SCHEDULE_CONFLICT",
    "DUPLICATE_CONTENT",
  ]) {
    assert.ok(codes.includes(code as (typeof codes)[number]), code);
  }
});

test("exports valid items when another selected item has a blocking error", () => {
  const plan = exportablePlan();
  const blockedId = plan.contentCalendar[0].itemId;
  plan.contentCalendar[0].postText = "";
  const result = createBufferHandoffExport(
    plan,
    "Ultrasound Clinical Evidence Campaign",
    options(plan),
    PLANNING_NOW,
  );

  assert.ok(result.exportRecord.skippedItemIds.includes(blockedId));
  assert.ok(result.exportRecord.exportedItemIds.length > 0);
  assert.equal(result.exportRecord.status, "partial");
  assert.equal(
    result.updatedPlan.contentCalendar.find((item) => item.itemId === blockedId)
      ?.workflowStatus,
    "planning",
  );
  assert.ok(
    result.updatedPlan.contentCalendar
      .filter((item) => result.exportRecord.exportedItemIds.includes(item.itemId))
      .every((item) => item.workflowStatus === "exported_to_buffer"),
  );
  assert.ok(
    result.updatedPlan.contentCalendar.every(
      (item) => item.workflowStatus !== "published",
    ),
  );
});

test("creates one official-column CSV per channel with safe Unicode escaping", () => {
  const plan = exportablePlan();
  const item = {
    ...plan.contentCalendar[0],
    postText: '=HYPERLINK("https://invalid.example","中文,主题")\n第二行',
    campaignTag: "+SyntheticTag",
    mediaUrls: ["https://example.invalid/synthetic.png"],
  };
  const csv = generateBufferChannelCsv(item.channel, [item]);

  assert.ok(csv.startsWith("\uFEFF"));
  assert.ok(csv.includes('"Text","Image URL","Tags","Posting Time"'));
  assert.ok(csv.includes(`"'=HYPERLINK(""https://invalid.example""`));
  assert.ok(csv.includes("中文,主题"));
  assert.ok(csv.includes("\n第二行"));
  assert.ok(csv.includes(`"'+SyntheticTag"`));
});

test("uses dated channel filenames and warns on repeat export", () => {
  const plan = exportablePlan();
  const first = createBufferHandoffExport(
    plan,
    "Ultrasound Clinical Evidence Campaign",
    options(plan),
    PLANNING_NOW,
  );
  assert.ok(
    first.artifacts.every((artifact) =>
      artifact.fileName.match(
        /^Ultrasound-Clinical-Evidence-Campaign-buffer-linkedin-(?:page|profile)-2026-07-28-to-2026-08-10-2026-07-28\.csv$/,
      ),
    ),
  );

  const repeated = validateBufferHandoff(
    first.updatedPlan,
    options(first.updatedPlan, {
      previousExports: [first.exportRecord],
    }),
    new Date("2026-07-28T02:00:00.000Z"),
  );
  assert.ok(
    repeated.reviews.some((review) =>
      review.issues.some((item) => item.code === "ALREADY_EXPORTED"),
    ),
  );
});

test("free queue guidance is configurable metadata and never deletes excess items", () => {
  const plan = exportablePlan(7);
  plan.contentCalendar = plan.contentCalendar.map((item) => ({
    ...item,
    channel: "linkedin_page",
  }));
  const preview = validateBufferHandoff(
    plan,
    options(plan, {
      dateRange: { start: plan.startDate, end: plan.endDate },
      channels: ["linkedin_page"],
    }),
    PLANNING_NOW,
  );

  assert.equal(
    BUFFER_OFFICIAL_GUIDANCE.freePlan.queueCapacityPerChannel,
    10,
  );
  assert.equal(preview.summary.mayExceedFreeQueue, true);
  assert.equal(preview.updatedPlan.contentCalendar.length, 28);
  assert.ok(
    preview.globalIssues.some((item) => item.code === "FREE_PLAN_QUEUE_LIMIT"),
  );
});

test("rejects a handoff timezone mismatch because CSV has no timezone column", () => {
  const plan = exportablePlan();
  plan.contentCalendar[0].timeZone = "America/New_York";
  const preview = validateBufferHandoff(
    plan,
    options(plan),
    PLANNING_NOW,
  );
  assert.ok(
    preview.reviews[0].issues.some(
      (item) => item.code === "HANDOFF_TIME_ZONE_MISMATCH",
    ),
  );
  assert.equal(preview.reviews[0].canExport, false);
});
