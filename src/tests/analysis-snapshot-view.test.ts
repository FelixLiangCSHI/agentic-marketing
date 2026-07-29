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

  assert.match(markup, /Deterministic metrics and data quality snapshot/);
  assert.match(markup, /How this value is calculated/);
  assert.match(markup, /Data sources/);
  assert.match(markup, /Unavailable/);
  assert.match(markup, /correlations and proxies are not causation/);
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

  assert.match(markup, /Blocking issues prevent recommendation review/);
  assert.match(
    markup,
    /<button class="primary-button" type="button" disabled="">/,
  );
});
