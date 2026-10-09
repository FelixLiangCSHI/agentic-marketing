import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import test from "node:test";

import { parsePardotCredentials } from "@/server/channels/pardot-credentials";
import {
  PardotProductionVerificationError,
  verifyPardotProductionConnection,
} from "@/server/channels/pardot-production-verification";

const SHA = "a".repeat(40);
const environment = {
  GITHUB_ACTIONS: "true",
  GITHUB_EVENT_NAME: "workflow_dispatch",
  GITHUB_REPOSITORY: "FelixLiangCSHI/agentic-marketing",
  GITHUB_REF: "refs/heads/main",
  GITHUB_REF_PROTECTED: "true",
  GITHUB_SHA: SHA,
  GITHUB_RUN_ID: "12345",
  GITHUB_TOKEN: "synthetic-github-job-token",
  PARDOT_VERIFICATION_ENVIRONMENT: "production",
  PARDOT_APPROVED_COMMIT_SHA: SHA,
  PARDOT_APPROVAL_REFERENCE: "CHANGE-123",
  PARDOT_REQUESTED_APPROVAL_REFERENCE: "CHANGE-123",
  PARDOT_READ_ONLY_CONFIRMED: "true",
  PARDOT_CREDENTIALS_SECRET_REF: "secretref://corp-vault/dmt/prd/pardot/oauth",
};
const credentials = parsePardotCredentials({
  schemaVersion: 1,
  pardot: {
    clientId: "synthetic-production-client",
    clientSecret: ["synthetic", "production", "client", "secret"].join("-"),
    businessUnitId: `0Uv${"A".repeat(15)}`,
    environment: "production",
    loginDomain: "synthetic.my.salesforce.com",
  },
});
const protection = {
  name: "production",
  protection_rules: [{
    type: "required_reviewers",
    prevent_self_review: true,
    reviewers: [{ type: "Team", reviewer: { id: 123 } }],
  }],
  deployment_branch_policy: {
    protected_branches: true,
    custom_branch_policies: false,
  },
};

function jsonResponse(value: unknown, status = 200): Response {
  return Response.json(value, { status });
}

test("production verification blocks local, fork, PR, unreviewed and unconfirmed runs before credentials or HTTP", async () => {
  const invalid = [
    { GITHUB_ACTIONS: "false" },
    { GITHUB_EVENT_NAME: "pull_request" },
    { GITHUB_REPOSITORY: "attacker/agentic-marketing" },
    { GITHUB_REF: "refs/heads/feature" },
    { GITHUB_REF_PROTECTED: "false" },
    { GITHUB_SHA: "b".repeat(40) },
    { GITHUB_RUN_ID: "" },
    { GITHUB_TOKEN: "" },
    { PARDOT_VERIFICATION_ENVIRONMENT: "dev" },
    { PARDOT_APPROVED_COMMIT_SHA: "" },
    { PARDOT_APPROVAL_REFERENCE: "" },
    { PARDOT_REQUESTED_APPROVAL_REFERENCE: "CHANGE-OTHER" },
    { PARDOT_READ_ONLY_CONFIRMED: "false" },
    { PARDOT_CREDENTIALS_SECRET_REF: "literal-credential" },
    { PARDOT_CREDENTIALS_SECRET_REF: "secretref://corp-vault/dmt/prd/../pardot" },
  ];
  for (const overrides of invalid) {
    await assert.rejects(
      verifyPardotProductionConnection({
        environment: { ...environment, ...overrides },
        loadCredentials: async () => {
          assert.fail("Blocked runs must not load credentials.");
        },
        fetchImpl: async () => {
          assert.fail("Blocked runs must not make HTTP requests.");
        },
      }),
      { code: "APPROVAL_REQUIRED", stage: "approval" },
    );
  }
});

test("production verification checks actual environment protection before loading credentials", async () => {
  const unsafe = [
    { ...protection, name: "dev" },
    { ...protection, can_admins_bypass: true },
    { ...protection, protection_rules: [] },
    { ...protection, protection_rules: [{ type: "required_reviewers", prevent_self_review: false, reviewers: [{}] }] },
    { ...protection, protection_rules: [{ type: "required_reviewers", prevent_self_review: true, reviewers: [] }] },
    { ...protection, deployment_branch_policy: null },
    { ...protection, deployment_branch_policy: { protected_branches: false, custom_branch_policies: true } },
  ];
  for (const value of unsafe) {
    let calls = 0;
    await assert.rejects(
      verifyPardotProductionConnection({
        environment,
        loadCredentials: async () => {
          assert.fail("Unprotected environments must not load credentials.");
        },
        fetchImpl: async (input, init) => {
          calls += 1;
          assert.equal(String(input), "https://api.github.com/repos/FelixLiangCSHI/agentic-marketing/environments/production");
          assert.equal(init?.method, "GET");
          assert.equal(init?.redirect, "error");
          return jsonResponse(value);
        },
      }),
      { code: "APPROVAL_REQUIRED", stage: "approval" },
    );
    assert.equal(calls, 1);
  }
});

test("production verification rejects unavailable environment protection metadata", async () => {
  await assert.rejects(
    verifyPardotProductionConnection({
      environment,
      loadCredentials: async () => assert.fail("No credentials before protection verification."),
      fetchImpl: async () => jsonResponse({}, 403),
    }),
    { code: "APPROVAL_REQUIRED", stage: "approval", httpStatus: 403 },
  );
});

test("production verification rejects developer credentials without requesting Salesforce or Pardot", async () => {
  let calls = 0;
  await assert.rejects(
    verifyPardotProductionConnection({
      environment,
      loadCredentials: async () => ({
        ...credentials,
        environment: "developer",
        apiBaseUrl: "https://pi.demo.pardot.com",
      }),
      fetchImpl: async () => {
        calls += 1;
        return jsonResponse(protection);
      },
    }),
    { code: "CREDENTIALS_INVALID", stage: "credentials" },
  );
  assert.equal(calls, 1);
});

test("production verification requests only OAuth and Campaign Query and returns a redacted receipt", async () => {
  const calls: string[] = [];
  const token = "synthetic-salesforce-access-token";
  const report = await verifyPardotProductionConnection({
    environment,
    loadCredentials: async () => credentials,
    now: new Date("2026-10-09T01:10:00.000Z"),
    fetchImpl: async (input, init) => {
      const url = new URL(String(input));
      calls.push(url.toString());
      assert.equal(init?.redirect, "error");
      if (url.hostname === "api.github.com") {
        assert.equal(init?.method, "GET");
        return jsonResponse(protection);
      }
      if (url.pathname === "/services/oauth2/token") {
        assert.equal(url.origin, credentials.loginBaseUrl);
        assert.equal(init?.method, "POST");
        const body = new URLSearchParams(String(init?.body));
        assert.equal(body.get("grant_type"), "client_credentials");
        assert.equal(body.get("client_id"), credentials.clientId);
        assert.equal(body.get("client_secret"), credentials.clientSecret);
        return jsonResponse({ access_token: token, token_type: "Bearer" });
      }
      assert.equal(url.origin, "https://pi.pardot.com");
      assert.equal(url.pathname, "/api/v5/objects/campaigns");
      assert.equal(init?.method, "GET");
      assert.equal(url.searchParams.get("fields"), "id,name,isDeleted");
      assert.equal(url.searchParams.get("limit"), "100");
      assert.equal(new Headers(init?.headers).get("Authorization"), `Bearer ${token}`);
      assert.equal(new Headers(init?.headers).get("Pardot-Business-Unit-Id"), credentials.businessUnitId);
      return jsonResponse({ values: [{ id: 42, name: "Internal Campaign Name", isDeleted: false }] });
    },
  });
  assert.deepEqual(report, {
    success: true,
    environment: "production",
    mode: "api",
    apiBaseUrl: "https://pi.pardot.com",
    oauthHttpStatus: 200,
    campaignQueryHttpStatus: 200,
    campaignSampleCount: 1,
    externalBusinessWrites: 0,
    checkedAt: "2026-10-09T01:10:00.000Z",
    commitSha: SHA,
    approvalReference: "CHANGE-123",
    workflowRunId: "12345",
  });
  assert.equal(calls.length, 3);
  for (const privateValue of [credentials.clientId, credentials.clientSecret, credentials.businessUnitId, token, "Internal Campaign Name"]) {
    assert.equal(JSON.stringify(report).includes(privateValue), false);
  }
});

test("production verification accepts an empty Campaign Query but fails on HTTP errors without retries or fallback", async () => {
  for (const status of [200, 201, 403]) {
    let calls = 0;
    const operation = verifyPardotProductionConnection({
      environment,
      loadCredentials: async () => credentials,
      fetchImpl: async (input) => {
        calls += 1;
        if (String(input).includes("api.github.com")) return jsonResponse(protection);
        if (String(input).endsWith("/services/oauth2/token")) {
          return jsonResponse({ access_token: "synthetic-token", token_type: "Bearer" });
        }
        return jsonResponse(status === 200 ? { values: [] } : { code: 201, message: "private-provider-message" }, status);
      },
    });
    if (status === 200) {
      assert.equal((await operation).campaignSampleCount, 0);
    } else {
      await assert.rejects(operation, (error: unknown) => {
        assert.ok(error instanceof PardotProductionVerificationError);
        assert.equal(error.stage, "campaign-query");
        assert.equal(error.httpStatus, status);
        assert.equal(error.reason, "http_200_required");
        assert.equal(JSON.stringify(error).includes("private-provider-message"), false);
        return true;
      });
    }
    assert.equal(calls, 3);
  }
});

test("production verification rejects invalid successful provider response shapes", async () => {
  await assert.rejects(
    verifyPardotProductionConnection({
      environment,
      loadCredentials: async () => credentials,
      fetchImpl: async (input) => {
        if (String(input).includes("api.github.com")) return jsonResponse(protection);
        if (String(input).endsWith("/services/oauth2/token")) {
          return jsonResponse({ access_token: "synthetic-token", token_type: "Bearer" });
        }
        return jsonResponse({ values: [{ id: "invalid", name: "private-name" }] });
      },
    }),
    { code: "UPSTREAM_RESPONSE_INVALID", stage: "campaign-query" },
  );
});

test("production verification stops at an OAuth HTTP failure and preserves its diagnostic", async () => {
  let calls = 0;
  await assert.rejects(
    verifyPardotProductionConnection({
      environment,
      loadCredentials: async () => credentials,
      fetchImpl: async (input) => {
        calls += 1;
        if (String(input).includes("api.github.com")) return jsonResponse(protection);
        assert.ok(String(input).endsWith("/services/oauth2/token"));
        return jsonResponse({ error: "private-oauth-error" }, 401);
      },
    }),
    { code: "PARDOT_UNAVAILABLE", stage: "oauth", httpStatus: 401, reason: "http_200_required" },
  );
  assert.equal(calls, 2);
});

test("production verification does not echo credential loader or network exception content", async () => {
  for (const failingStage of ["credentials", "oauth"] as const) {
    await assert.rejects(
      verifyPardotProductionConnection({
        environment,
        loadCredentials: async () => {
          if (failingStage === "credentials") throw new Error("private-credential-content");
          return credentials;
        },
        fetchImpl: async (input) => {
          if (String(input).includes("api.github.com")) return jsonResponse(protection);
          throw new Error("private-network-content");
        },
      }),
      (error: unknown) => {
        assert.ok(error instanceof PardotProductionVerificationError);
        assert.equal(error.stage, failingStage);
        assert.equal(error.httpStatus, null);
        assert.doesNotMatch(`${error.message}${JSON.stringify(error)}`, /private-credential-content|private-network-content/);
        return true;
      },
    );
  }
});

test("production verification CLI refuses ordinary local execution", () => {
  const result = spawnSync(process.execPath, ["--import", "tsx", "scripts/verify-pardot-production.ts"], {
    cwd: process.cwd(),
    env: { ...process.env, GITHUB_ACTIONS: "false" },
    encoding: "utf8",
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /APPROVAL_REQUIRED/);
  assert.doesNotMatch(result.stderr, /clientSecret|access_token|Bearer/);
});

test("production verification workflow replaces the DEV placeholder without enabling PR access or deployment", async () => {
  const workflow = await readFile(".github/workflows/deploy-dev.yml", "utf8");
  assert.match(workflow, /^name: verify-pardot-production$/m);
  assert.match(workflow, /environment: production/);
  assert.match(workflow, /workflow_dispatch:/);
  assert.doesNotMatch(workflow, /^\s+(push|pull_request|pull_request_target|schedule):/m);
  assert.match(workflow, /runs-on: \[self-hosted, linux, x64, pardot-production-verification\]/);
  assert.match(workflow, /ref: \$\{\{ github\.sha \}\}/);
  assert.match(workflow, /persist-credentials: false/);
  assert.match(workflow, /npm ci --ignore-scripts/);
  assert.match(workflow, /npm run pardot:verify:production/);
  assert.match(workflow, /PARDOT_CREDENTIALS_SECRET_REF: \$\{\{ vars\.PARDOT_CREDENTIALS_SECRET_REF \}\}/);
  assert.doesNotMatch(workflow, /Deploy to DEV|environment: dev|client_secret:|clientSecret:|sendOneToOneEmail/);
});

test("production verification can be published without YouTube or campaign delivery application modules", async () => {
  const [credentialSource, connectorSource] = await Promise.all([
    readFile("src/server/channels/pardot-credentials.ts", "utf8"),
    readFile("src/server/channels/pardot.ts", "utf8"),
  ]);
  assert.match(credentialSource, /from "@\/server\/channels\/protected-channel-credentials"/);
  assert.doesNotMatch(credentialSource, /youtube-credentials/);
  assert.match(connectorSource, /from "@\/domain\/pardot-connector"/);
  assert.doesNotMatch(connectorSource, /from "@\/domain\/pardot"/);
});
