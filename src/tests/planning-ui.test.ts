import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  confirmActionPlan,
  generateActionPlan,
} from "@/agents/action-plan-agent";
import { ActionPlanReport } from "@/components/analysis/action-plan-report";
import { StrategyPlanningWorkspace } from "@/components/analysis/strategy-planning-workspace";
import {
  approvedPlanningInput,
  PLANNING_NOW,
} from "@/tests/planning-fixtures";

const noop = () => undefined;
const noopReview = () => undefined;

test("planning workspace starts with explicit goal and approval gates", () => {
  const input = approvedPlanningInput();
  const markup = renderToStaticMarkup(
    createElement(StrategyPlanningWorkspace, {
      snapshot: input.snapshot,
      onBack: noop,
    }),
  );

  assert.match(markup, /Governed campaign workflow/);
  assert.match(markup, /Historical LinkedIn Analysis/);
  assert.match(markup, /Campaign Strategy/);
  assert.match(markup, /30-Day Content Calendar/);
  assert.match(markup, /Prepare Content/);
  assert.match(markup, /Confirm business goal/);
  assert.match(markup, /Human approval required/i);
  assert.match(markup, /Marketing Recommendation/);
  assert.match(markup, /Approval Status/);
  assert.match(markup, /Reviewer/);
  assert.match(markup, /Comments/);
  assert.match(markup, /Approve/);
  assert.match(markup, /Request Revision/);
  assert.match(markup, /Rejected/);
  assert.match(markup, /Publishing Handoff/);
  assert.match(markup, /Approve every referenced insight/);
  assert.doesNotMatch(markup, /\bAI\b|sparkle/i);
  assert.doesNotMatch(markup, /chat-message/);
});

test("action plan report shows status, risks, views, metadata, and evidence", () => {
  const input = approvedPlanningInput();
  const plan = generateActionPlan(input, PLANNING_NOW);
  const markup = renderToStaticMarkup(
    createElement(ActionPlanReport, {
      plan,
      approvedInsights: input.approvedInsights,
      approvedStrategies: input.approvedStrategies,
      canUndo: false,
      onUndo: noop,
      onUpdateItem: noop,
      onConfirmPlan: noop,
      onReviewPlan: noopReview,
      onDownload: noop,
    }),
  );

  assert.match(markup, /Prepared draft/);
  assert.match(markup, /Risks and data limitations/);
  assert.match(markup, /Audience Insights/);
  assert.match(markup, /Content Insights/);
  assert.match(markup, /Prompt version/);
  assert.match(markup, /Content calendar/i);
  assert.match(markup, /Experiment/);
  assert.match(markup, /Post objective/);
  assert.match(markup, /Content angle/);
  assert.match(markup, /Approval checkpoint/);
  assert.doesNotMatch(markup, /Draft Ready/);
});

test("approved calendar exposes Buffer-ready draft cards", () => {
  const input = approvedPlanningInput();
  const plan = confirmActionPlan(generateActionPlan(input, PLANNING_NOW), PLANNING_NOW);
  const markup = renderToStaticMarkup(
    createElement(ActionPlanReport, {
      plan,
      approvedInsights: input.approvedInsights,
      approvedStrategies: input.approvedStrategies,
      canUndo: false,
      onUndo: noop,
      onUpdateItem: noop,
      onConfirmPlan: noop,
      onReviewPlan: noopReview,
      onDownload: noop,
    }),
  );

  assert.match(markup, /Draft Ready/);
  assert.match(markup, /Ready to Publish/);
  assert.match(markup, /Media suggestion/);
  assert.match(markup, /Professional terminology/);
  for (const label of [
    "Buffer Connection",
    "Workspace",
    "Scheduled Drafts",
    "Ready to Publish",
    "Pending Review",
    "Publishing Queue",
    "Mock / Demo",
  ]) {
    assert.match(markup, new RegExp(label));
  }
  assert.match(markup, /No network or API calls/);
  assert.doesNotMatch(markup, /\bAI\b|sparkle/i);
});
