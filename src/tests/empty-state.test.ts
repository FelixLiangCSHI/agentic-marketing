import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { EmptyState } from "@/components/ui/empty-state";

test("renders an accessible empty-state placeholder", () => {
  const markup = renderToStaticMarkup(
    createElement(EmptyState, {
      title: "等待识别结果",
      description: "上传文件后显示预览。",
    }),
  );

  assert.match(markup, /role="status"/);
  assert.match(markup, /等待识别结果/);
  assert.match(markup, /上传文件后显示预览/);
});
