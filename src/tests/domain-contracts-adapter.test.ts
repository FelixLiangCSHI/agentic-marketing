import assert from "node:assert/strict";
import test from "node:test";

import {
  assertContractDocument,
  toContractApprovalStatus,
} from "@/domain/contracts";
import type { ApprovalStatus } from "@/domain/strategy";

test("maps every local approval status to a contract enum value", () => {
  const cases: Array<[ApprovalStatus, string]> = [
    ["draft", "PENDING"],
    ["approved", "APPROVED"],
    ["revision_requested", "REJECTED"],
    ["rejected", "REJECTED"],
  ];
  for (const [local, expected] of cases) {
    assert.equal(toContractApprovalStatus(local), expected);
  }
});

test("adapter exposes contract runtime validation", () => {
  const invalid = assertContractDocument("approval.v1", {
    schema_version: "1.0",
    status: "waiting for boss",
  });
  assert.equal(invalid.valid, false);
  assert.ok(invalid.errors.length > 0);
});
