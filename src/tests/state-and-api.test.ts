import assert from "node:assert/strict";
import test from "node:test";

import { POST } from "@/app/api/parse/route";
import { MAX_REQUEST_SIZE_BYTES } from "@/data-processing/file-validation";
import { findRepeatedDetectedModules } from "@/data-processing/readiness";
import { createSyntheticParseResults } from "@/server/parsing/synthetic-results";
import {
  canStartAnalysis,
  createInitialIngestionState,
  ingestionReducer,
} from "@/state/ingestion-reducer";

test("missing modules keep the next-stage action disabled", () => {
  const state = createInitialIngestionState();
  assert.equal(canStartAnalysis(state), false);
});

test("synthetic Mock results use the same contract and complete ingestion", () => {
  const initial = createInitialIngestionState();
  const loaded = ingestionReducer(initial, {
    type: "LOAD_MOCK",
    results: createSyntheticParseResults(),
  });

  assert.equal(canStartAnalysis(loaded), true);
  assert.equal(loaded.slots.followers.result?.parserMode, "synthetic-mock");
  const ready = ingestionReducer(loaded, { type: "MARK_ANALYSIS_READY" });
  assert.equal(ready.analysisReady, true);
  assert.equal(ready.qualityWarningsAcknowledged, false);
  const acknowledged = ingestionReducer(ready, {
    type: "ACKNOWLEDGE_QUALITY_WARNINGS",
  });
  assert.equal(acknowledged.qualityWarningsAcknowledged, true);
});

test("detects repeated module assignments before confirmation", () => {
  const duplicates = findRepeatedDetectedModules([
    {
      slot: "followers",
      detectedModule: "followers",
      confirmed: false,
    },
    {
      slot: "visitors",
      detectedModule: "followers",
      confirmed: false,
    },
    {
      slot: "content",
      detectedModule: "content",
      confirmed: false,
    },
  ]);

  assert.deepEqual(duplicates, ["followers"]);
});

test("Route Handler validates and parses a normal multipart CSV", async () => {
  const formData = new FormData();
  formData.set(
    "file",
    new File(
      ["Date,New followers\n2026-01-01,10"],
      "synthetic_followers.csv",
      { type: "text/csv" },
    ),
  );
  formData.set("expectedModule", "followers");
  const response = await POST(
    new Request("http://localhost/api/parse", {
      method: "POST",
      body: formData,
    }),
  );
  const payload: unknown = await response.json();

  assert.equal(response.status, 200);
  assert.equal(
    typeof payload === "object" &&
      payload !== null &&
      "success" in payload &&
      payload.success,
    true,
  );
  assert.equal(response.headers.get("cache-control"), "no-store, max-age=0");
});

test("Route Handler rejects unsupported files without parsing", async () => {
  const formData = new FormData();
  formData.set(
    "file",
    new File(["synthetic"], "synthetic.txt", { type: "text/plain" }),
  );
  const response = await POST(
    new Request("http://localhost/api/parse", {
      method: "POST",
      body: formData,
    }),
  );
  const payload = (await response.json()) as {
    success: boolean;
    error: { code: string };
  };

  assert.equal(response.status, 415);
  assert.equal(payload.success, false);
  assert.equal(payload.error.code, "UNSUPPORTED_FILE_TYPE");
});

test("Route Handler rejects a cross-module mapping override", async () => {
  const formData = new FormData();
  formData.set(
    "file",
    new File(
      ["Date,New followers\n2026-01-01,10"],
      "synthetic_followers.csv",
      { type: "text/csv" },
    ),
  );
  formData.set("expectedModule", "followers");
  formData.set(
    "mappingOverrides",
    JSON.stringify({ "Sheet1::1::new followers": "impressions" }),
  );
  const response = await POST(
    new Request("http://localhost/api/parse", {
      method: "POST",
      body: formData,
    }),
  );
  const payload = (await response.json()) as {
    success: boolean;
    error: { code: string };
  };

  assert.equal(response.status, 400);
  assert.equal(payload.success, false);
  assert.equal(payload.error.code, "INVALID_MAPPING_OVERRIDE");
});

test("Route Handler rejects an oversized body without Content-Length", async () => {
  const oversized = new Uint8Array(MAX_REQUEST_SIZE_BYTES + 1);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(oversized);
      controller.close();
    },
  });
  const response = await POST(
    new Request("http://localhost/api/parse", {
      method: "POST",
      headers: { "content-type": "multipart/form-data; boundary=x" },
      body: stream,
      // @ts-expect-error duplex is required for stream bodies in undici
      duplex: "half",
    }),
  );
  const payload = (await response.json()) as {
    success: boolean;
    error: { code: string };
  };

  assert.equal(response.status, 413);
  assert.equal(payload.error.code, "REQUEST_TOO_LARGE");
});

test("Route Handler fails closed on an invalid Content-Length header", async () => {
  const response = await POST(
    new Request("http://localhost/api/parse", {
      method: "POST",
      headers: {
        "content-type": "multipart/form-data; boundary=x",
        "content-length": "not-a-number",
      },
      body: new Uint8Array(0),
      // @ts-expect-error duplex is required for stream bodies in undici
      duplex: "half",
    }),
  );
  const payload = (await response.json()) as {
    success: boolean;
    error: { code: string };
  };

  assert.equal(response.status, 413);
  assert.equal(payload.error.code, "REQUEST_TOO_LARGE");
});
