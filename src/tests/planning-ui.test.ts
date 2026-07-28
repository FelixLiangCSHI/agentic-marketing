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

  assert.match(markup, /Multi-stage AI agent pipeline/);
  assert.match(markup, /Historical LinkedIn Analysis/);
  assert.match(markup, /AI Marketing Strategy Recommendation/);
  assert.match(markup, /30-Day Content Calendar/);
  assert.match(markup, /Draft Generation/);
  assert.match(markup, /确认业务目标/);
  assert.match(markup, /Human approval required/i);
  assert.match(markup, /AI Recommendation/);
  assert.match(markup, /Approval Status/);
  assert.match(markup, /Reviewer/);
  assert.match(markup, /Comments/);
  assert.match(markup, /Approve/);
  assert.match(markup, /Request Revision/);
  assert.match(markup, /Rejected/);
  assert.match(markup, /Ready for Buffer/);
  assert.match(markup, /必须先批准该策略引用的全部洞察/);
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

  assert.match(markup, /AI 初稿/);
  assert.match(markup, /风险与数据限制/);
  assert.match(markup, /Audience Insights/);
  assert.match(markup, /Content Insights/);
  assert.match(markup, /Prompt 版本/);
  assert.match(markup, /内容日历/);
  assert.match(markup, /实验/);
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
  assert.match(markup, /Ready for Buffer/);
  assert.match(markup, /Media suggestion/);
  assert.match(markup, /Professional terminology/);
});
