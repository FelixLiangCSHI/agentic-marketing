import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { generateActionPlan } from "@/agents/action-plan-agent";
import { ActionPlanReport } from "@/components/analysis/action-plan-report";
import { StrategyPlanningWorkspace } from "@/components/analysis/strategy-planning-workspace";
import {
  approvedPlanningInput,
  PLANNING_NOW,
} from "@/tests/planning-fixtures";

const noop = () => undefined;

test("planning workspace starts with explicit goal and approval gates", () => {
  const input = approvedPlanningInput();
  const markup = renderToStaticMarkup(
    createElement(StrategyPlanningWorkspace, {
      snapshot: input.snapshot,
      onBack: noop,
    }),
  );

  assert.match(markup, /从已批准证据生成 30 天计划/);
  assert.match(markup, /确认业务目标/);
  assert.match(markup, /审批洞察/);
  assert.match(markup, /必须先批准该策略引用的全部洞察/);
  assert.match(markup, /基于证据的问答/);
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
});
