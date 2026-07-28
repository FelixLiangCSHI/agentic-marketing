import assert from "node:assert/strict";
import test from "node:test";

import {
  ActionPlanAgentError,
  addDays,
  confirmActionPlan,
  generateActionPlan,
  isActionPlanShape,
  localDateInTimeZone,
  normalizeActionPlan,
  reviseActionPlanSchedule,
  reviseCalendarItem,
  runActionPlanAgent,
  runValidatedActionPlanAdapter,
  validateActionPlan,
} from "@/agents/action-plan-agent";
import {
  createInitialPlanEditorState,
  planEditorReducer,
} from "@/state/plan-editor-reducer";
import {
  approvedPlanningInput,
  PLANNING_NOW,
} from "@/tests/planning-fixtures";

test("rejects any unapproved insight or strategy before plan generation", () => {
  const input = approvedPlanningInput();
  input.approvedStrategies[0] = {
    ...input.approvedStrategies[0],
    approvalStatus: "draft",
  };

  assert.throws(
    () => generateActionPlan(input, PLANNING_NOW),
    (reason) =>
      reason instanceof ActionPlanAgentError &&
      reason.issues.some((issue) => issue.code === "STRATEGY_NOT_APPROVED"),
  );
});

test("builds a timezone-safe four-week plan within the 30-day range", () => {
  const input = approvedPlanningInput();
  const plan = generateActionPlan(input, PLANNING_NOW);

  assert.equal(
    localDateInTimeZone(
      new Date("2026-07-27T16:30:00.000Z"),
      "Asia/Shanghai",
    ),
    "2026-07-28",
  );
  assert.equal(
    localDateInTimeZone(
      new Date("2026-07-27T16:30:00.000Z"),
      "America/Los_Angeles",
    ),
    "2026-07-27",
  );
  assert.equal(plan.startDate, "2026-07-29");
  assert.equal(plan.endDate, addDays(plan.startDate, 29));
  assert.equal(plan.fourWeekPlan.length, 4);
  assert.equal(plan.contentCalendar.length, 12);
  assert.equal(plan.schemaVersion, "1.1");
  assert.equal(plan.promptVersion, "action-plan-v1.1");
  assert.deepEqual(Object.keys(plan.report ?? {}), [
    "executiveSummary",
    "keyFindings",
    "businessImplications",
    "recommendations",
    "confidenceLevel",
    "evidence",
    "observedTrends",
  ]);
  assert.equal(new Set(plan.contentCalendar.map((item) => item.date)).size, 12);
  assert.ok(plan.contentCalendar.every((item) => item.date >= plan.startDate));
  assert.ok(
    plan.contentCalendar.every((item) => item.ownerPlaceholder.includes("待指定")),
  );
  assert.ok(
    plan.contentCalendar.every(
      (item) =>
        item.postText.length > 0 &&
        item.scheduledTime.length === 5 &&
        item.timeZone === input.preferences.timeZone &&
        item.workflowStatus === "planning" &&
        item.status === "ai_draft",
    ),
  );
});

test("rejects past dates in the user's timezone", () => {
  const input = approvedPlanningInput({
    preferences: {
      ...approvedPlanningInput().preferences,
      startDate: "2026-07-27",
    },
  });

  assert.throws(
    () => generateActionPlan(input, PLANNING_NOW),
    (reason) =>
      reason instanceof ActionPlanAgentError &&
      reason.issues.some((issue) => issue.code === "START_DATE_IN_PAST"),
  );
});

test("enforces weekly posting capacity and complete KPI references", () => {
  const input = approvedPlanningInput();
  const plan = generateActionPlan(input, PLANNING_NOW);
  const validation = validateActionPlan(plan, input, PLANNING_NOW);

  assert.equal(validation.valid, true);
  for (const week of plan.fourWeekPlan) {
    assert.equal(week.contentItems.length, input.preferences.postsPerWeek);
  }
  const knownKpis = new Set(
    plan.kpiDefinitions.map((definition) => definition.metricId),
  );
  assert.ok(
    plan.contentCalendar.every((item) =>
      item.measurementMetricIds.every((metricId) => knownKpis.has(metricId)),
    ),
  );

  const broken = structuredClone(plan);
  broken.contentCalendar[0].measurementMetricIds.push("unknown.metric");
  const brokenValidation = validateActionPlan(broken, input, PLANNING_NOW);
  assert.equal(brokenValidation.valid, false);
  assert.ok(
    brokenValidation.issues.some(
      (issue) => issue.code === "KPI_REFERENCE_INVALID",
    ),
  );
});

test("labels experiments with hypothesis, success criteria, and review date", () => {
  const plan = generateActionPlan(approvedPlanningInput(), PLANNING_NOW);
  const experiments = plan.contentCalendar.filter((item) => item.isExperiment);

  assert.ok(experiments.length > 0);
  for (const item of experiments) {
    assert.ok(item.experiment);
    assert.ok(item.experiment.hypothesis.length > 0);
    assert.ok(item.experiment.successCriteria.includes("不承诺固定增长幅度"));
    assert.ok(item.experiment.reviewDate >= item.date);
  }
});

test("applies scoped plan edits and supports undoing the latest revision", () => {
  const input = approvedPlanningInput();
  const original = generateActionPlan(input, PLANNING_NOW);
  const firstItem = original.contentCalendar[0];
  const edited = reviseCalendarItem(
    original,
    firstItem.itemId,
    { topic: "用户修改的主题", status: "confirmed" },
    new Date("2026-07-28T02:00:00.000Z"),
  );
  let state = planEditorReducer(createInitialPlanEditorState(), {
    type: "LOAD_PLAN",
    plan: original,
  });
  state = planEditorReducer(state, { type: "APPLY_REVISION", plan: edited });

  assert.equal(state.current?.contentCalendar[0].topic, "用户修改的主题");
  assert.equal(state.current?.status, "ai_draft");
  state = planEditorReducer(state, { type: "UNDO_LAST_REVISION" });
  assert.equal(state.current?.contentCalendar[0].topic, firstItem.topic);

  const rescheduled = reviseActionPlanSchedule(
    original,
    input,
    { ...input.preferences, postsPerWeek: 2 },
    new Date("2026-07-28T03:00:00.000Z"),
  );
  assert.equal(rescheduled.contentCalendar.length, 8);
  assert.equal(rescheduled.executiveSummary, original.executiveSummary);
  assert.equal(rescheduled.snapshotId, original.snapshotId);
  assert.ok(
    rescheduled.assumptions.some((assumption) =>
      assumption.includes("Maximum weekly publishing volume: 2"),
    ),
  );

  const confirmed = confirmActionPlan(rescheduled, PLANNING_NOW);
  assert.equal(confirmed.status, "user_confirmed");
  assert.ok(
    confirmed.contentCalendar.every((item) => item.status === "confirmed"),
  );
});

test("supports cancellation followed by a clean retry", async () => {
  const input = approvedPlanningInput();
  const controller = new AbortController();
  const pending = runActionPlanAgent(input, {
    signal: controller.signal,
    delayMs: 50,
    now: PLANNING_NOW,
  });
  controller.abort();

  await assert.rejects(
    pending,
    (reason) =>
      reason instanceof ActionPlanAgentError &&
      reason.code === "GENERATION_CANCELLED",
  );
  const retried = await runActionPlanAgent(input, {
    delayMs: 0,
    now: PLANNING_NOW,
  });
  assert.equal(isActionPlanShape(retried), true);
});

test("keeps the same validated schema for mock and uploaded Snapshot modes", () => {
  const mockInput = approvedPlanningInput();
  const uploadedInput = approvedPlanningInput();
  uploadedInput.snapshot = {
    ...uploadedInput.snapshot,
    inputMode: "uploaded",
  };
  const mockPlan = generateActionPlan(mockInput, PLANNING_NOW);
  const uploadedPlan = generateActionPlan(uploadedInput, PLANNING_NOW);

  assert.deepEqual(
    Object.keys(JSON.parse(JSON.stringify(mockPlan))).sort(),
    Object.keys(JSON.parse(JSON.stringify(uploadedPlan))).sort(),
  );
  assert.equal(isActionPlanShape(JSON.parse(JSON.stringify(uploadedPlan))), true);
});

test("validates mock and model adapters against the same output contract", async () => {
  const input = approvedPlanningInput();
  const expected = generateActionPlan(input, PLANNING_NOW);
  const mockOutput = await runValidatedActionPlanAdapter(
    {
      mode: "mock",
      generate: async () => expected,
    },
    input,
    { now: PLANNING_NOW },
  );
  const modelOutput = await runValidatedActionPlanAdapter(
    {
      mode: "model",
      generate: async () => JSON.parse(JSON.stringify(expected)),
    },
    input,
    { now: PLANNING_NOW },
  );

  assert.deepEqual(Object.keys(modelOutput).sort(), Object.keys(mockOutput).sort());
  assert.equal(modelOutput.schemaVersion, mockOutput.schemaVersion);
  assert.equal(modelOutput.promptVersion, mockOutput.promptVersion);
});

test("migrates a legacy in-session plan without losing references", () => {
  const current = generateActionPlan(approvedPlanningInput(), PLANNING_NOW);
  const legacy = JSON.parse(JSON.stringify(current)) as Record<string, unknown>;
  legacy.schemaVersion = "1.0";
  legacy.promptVersion = "action-plan-v1.0";
  const items = legacy.contentCalendar;
  assert.ok(Array.isArray(items));
  for (const item of items) {
    assert.equal(typeof item, "object");
    assert.ok(item);
    for (const field of [
      "postText",
      "channel",
      "scheduledTime",
      "timeZone",
      "mediaUrls",
      "mediaRequirement",
      "linkUrl",
      "campaignTag",
      "sourceInsightIds",
      "workflowStatus",
      "validationStatus",
      "validationIssues",
      "lastEditedAt",
    ]) {
      delete (item as Record<string, unknown>)[field];
    }
  }

  const migrated = normalizeActionPlan(legacy);
  assert.ok(migrated);
  assert.equal(migrated.schemaVersion, "1.1");
  assert.equal(migrated.promptVersion, "action-plan-v1.0");
  assert.deepEqual(migrated.sourceInsightIds, current.sourceInsightIds);
  assert.ok(
    migrated.contentCalendar.every(
      (item) =>
        item.postText.length > 0 &&
        item.sourceInsightIds.length === current.sourceInsightIds.length,
    ),
  );
});

test("rejects malformed model output and broken evidence references safely", async () => {
  const input = approvedPlanningInput();
  const expected = generateActionPlan(input, PLANNING_NOW);
  const malformed = {
    ...expected,
    contentCalendar: [null],
  };
  await assert.rejects(
    runValidatedActionPlanAdapter(
      {
        mode: "model",
        generate: async () => malformed,
      },
      input,
      { now: PLANNING_NOW },
    ),
    (reason) =>
      reason instanceof ActionPlanAgentError &&
      reason.code === "VALIDATION_FAILED",
  );

  const brokenInput = approvedPlanningInput();
  brokenInput.approvedInsights[0] = {
    ...brokenInput.approvedInsights[0],
    evidence: [
      {
        ...brokenInput.approvedInsights[0].evidence[0],
        metricId: "unknown.metric",
      },
    ],
  };
  assert.throws(
    () => generateActionPlan(brokenInput, PLANNING_NOW),
    (reason) =>
      reason instanceof ActionPlanAgentError &&
      reason.issues.some(
        (issue) => issue.code === "INSIGHT_REFERENCE_INVALID",
      ),
  );
});
