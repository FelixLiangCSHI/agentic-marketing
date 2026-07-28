import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { generateAnalysisSnapshot } from "@/analysis/snapshot-engine";
import { AnalysisSnapshotView } from "@/components/analysis/analysis-snapshot-view";
import { handVerifiedInput } from "@/tests/analysis-fixtures";

const noop = () => undefined;

test("snapshot view exposes formulas, sources, and unavailable states", () => {
  const snapshot = generateAnalysisSnapshot(handVerifiedInput());
  const markup = renderToStaticMarkup(
    createElement(AnalysisSnapshotView, {
      snapshot,
      warningsAcknowledged: false,
      onAcknowledgeWarnings: noop,
      onBack: noop,
      onDownload: noop,
    }),
  );

  assert.match(markup, /确定性指标与数据质量快照/);
  assert.match(markup, /这个数字如何计算/);
  assert.match(markup, /数据来源/);
  assert.match(markup, /不可用/);
  assert.match(markup, /相关性和代理比率均不得解释为因果/);
});

test("blocking quality issues disable the Agent input gate", () => {
  const input = handVerifiedInput();
  input.records.visitors = [];
  const snapshot = generateAnalysisSnapshot(input);
  const markup = renderToStaticMarkup(
    createElement(AnalysisSnapshotView, {
      snapshot,
      warningsAcknowledged: false,
      onAcknowledgeWarnings: noop,
      onBack: noop,
      onDownload: noop,
    }),
  );

  assert.match(markup, /存在阻断问题，不能进入 AI 洞察/);
  assert.match(
    markup,
    /<button class="primary-button" type="button" disabled="">/,
  );
});
