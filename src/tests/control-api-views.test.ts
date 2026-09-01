import assert from "node:assert/strict";
import test from "node:test";

import {
  ControlApiShapeError,
  parseApprovalViews,
  parseReviewViews,
} from "@/server/control-api-views";

const validReview = {
  review_id: "rev-0123456789abcdef",
  run_id: "run-0001",
  status: "AWAITING_REVIEW",
  revision: 1,
  automated_status: "PASS",
  policy_version: "1.0.0",
  artifact_hash: `sha256:${"a".repeat(64)}`,
  created_by: "carol",
  created_at: "2026-06-01T00:00:00Z",
  medical: { status: "PENDING", decided_by: null },
  marketing: { status: "APPROVED", decided_by: "dave" },
};

const validApproval = {
  approval_id: "apr-1",
  run_id: "run-0001",
  approval_type: "external_write",
  requester_id: "carol",
  status: "PENDING",
  requested_at: "2026-06-01T00:00:00Z",
  expires_at: "2026-06-01T01:00:00Z",
};

test("parseReviewViews accepts a valid payload", () => {
  const parsed = parseReviewViews([validReview]);
  assert.equal(parsed.length, 1);
  assert.equal(parsed[0].medical.decided_by, null);
  assert.equal(parsed[0].marketing.decided_by, "dave");
});

test("parseReviewViews rejects non-array payloads", () => {
  assert.throws(() => parseReviewViews({}), ControlApiShapeError);
  assert.throws(() => parseReviewViews(null), ControlApiShapeError);
});

test("parseReviewViews rejects drifted shapes instead of rendering them", () => {
  assert.throws(
    () => parseReviewViews([{ ...validReview, revision: "1" }]),
    ControlApiShapeError,
  );
  assert.throws(
    () => parseReviewViews([{ ...validReview, medical: null }]),
    ControlApiShapeError,
  );
  assert.throws(
    () =>
      parseReviewViews([
        { ...validReview, medical: { status: "PENDING", decided_by: 7 } },
      ]),
    ControlApiShapeError,
  );
  const missingField: Record<string, unknown> = { ...validReview };
  delete missingField["policy_version"];
  assert.throws(() => parseReviewViews([missingField]), ControlApiShapeError);
});

test("parseApprovalViews accepts a valid payload", () => {
  const parsed = parseApprovalViews([validApproval]);
  assert.equal(parsed.length, 1);
  assert.equal(parsed[0].approval_type, "external_write");
});

test("parseApprovalViews rejects drifted shapes", () => {
  assert.throws(() => parseApprovalViews("nope"), ControlApiShapeError);
  assert.throws(
    () => parseApprovalViews([{ ...validApproval, expires_at: 123 }]),
    ControlApiShapeError,
  );
  const missingField: Record<string, unknown> = { ...validApproval };
  delete missingField["run_id"];
  assert.throws(() => parseApprovalViews([missingField]), ControlApiShapeError);
});
