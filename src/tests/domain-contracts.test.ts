import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  CONTRACT_NAMES,
  ContractValidationError,
  parseContract,
  tryParseContract,
  validateContract,
  type ContractName,
} from "../../packages/domain-contracts/src/validate";

const FIXTURES_ROOT = path.join(
  process.cwd(),
  "packages",
  "domain-contracts",
  "fixtures",
);

interface FixtureEntry {
  name: string;
  document: unknown;
}

function loadFixtures(kind: "golden" | "invalid", contract: ContractName) {
  const filePath = path.join(FIXTURES_ROOT, kind, `${contract}.json`);
  const entries = JSON.parse(readFileSync(filePath, "utf-8")) as FixtureEntry[];
  assert.ok(entries.length > 0, `fixture file ${filePath} must not be empty`);
  return entries;
}

for (const contract of CONTRACT_NAMES) {
  test(`contract ${contract}: all golden fixtures validate`, () => {
    for (const entry of loadFixtures("golden", contract)) {
      const result = validateContract(contract, entry.document);
      assert.equal(
        result.valid,
        true,
        `golden fixture "${entry.name}" should be valid: ${result.errors.join("; ")}`,
      );
    }
  });

  test(`contract ${contract}: all invalid fixtures are rejected`, () => {
    for (const entry of loadFixtures("invalid", contract)) {
      const result = validateContract(contract, entry.document);
      assert.equal(
        result.valid,
        false,
        `invalid fixture "${entry.name}" must be rejected`,
      );
    }
  });
}

test("unknown fields are rejected by every contract", () => {
  for (const contract of CONTRACT_NAMES) {
    const [entry] = loadFixtures("golden", contract);
    const mutated = {
      ...(entry.document as Record<string, unknown>),
      unexpected_extra_field: "x",
    };
    const result = validateContract(contract, mutated);
    assert.equal(
      result.valid,
      false,
      `${contract} must reject unknown fields per contract rules`,
    );
  }
});

test("parseContract returns a typed document for a golden fixture", () => {
  const [entry] = loadFixtures("golden", "run.v1");
  const run = parseContract("run.v1", entry.document);

  assert.equal(run.schema_version, "1.0");
  assert.equal(typeof run.run_id, "string");
});

test("parseContract throws ContractValidationError for invalid documents", () => {
  const [entry] = loadFixtures("invalid", "run.v1");

  assert.throws(
    () => parseContract("run.v1", entry.document),
    (error: unknown) =>
      error instanceof ContractValidationError &&
      error.contract === "run.v1" &&
      error.issues.length > 0,
  );

  const result = tryParseContract("run.v1", entry.document);
  assert.equal(result.ok, false);
});
