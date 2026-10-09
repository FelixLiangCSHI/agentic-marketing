import { ChannelConnectorError, type ChannelConnectorErrorCode } from "@/server/channels/errors";
import { createPardotConnector } from "@/server/channels/pardot";
import { loadPardotCredentials, type PardotCredentials } from "@/server/channels/pardot-credentials";

type VerificationStage = "approval" | "credentials" | "oauth" | "campaign-query";

export class PardotProductionVerificationError extends Error {
  constructor(
    public readonly code: ChannelConnectorErrorCode,
    public readonly stage: VerificationStage,
    public readonly reason: string,
    public readonly httpStatus: number | null = null,
  ) {
    super("Protected Pardot production verification failed.");
    this.name = "PardotProductionVerificationError";
  }
}

interface VerificationOptions {
  environment?: Readonly<Record<string, string | undefined>>;
  fetchImpl?: typeof fetch;
  loadCredentials?: () => Promise<PardotCredentials>;
  now?: Date;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function approvedContext(environment: Readonly<Record<string, string | undefined>>) {
  const sha = environment.GITHUB_SHA;
  const approval = environment.PARDOT_APPROVAL_REFERENCE;
  const secretRef = /^secretref:\/\/[a-zA-Z0-9._-]+\/([a-zA-Z0-9._/-]+)$/.exec(
    environment.PARDOT_CREDENTIALS_SECRET_REF ?? "",
  );
  const secretSegments = secretRef?.[1].split("/");
  if (
    environment.GITHUB_ACTIONS !== "true" ||
    environment.GITHUB_EVENT_NAME !== "workflow_dispatch" ||
    environment.GITHUB_REPOSITORY !== "FelixLiangCSHI/agentic-marketing" ||
    environment.GITHUB_REF !== "refs/heads/main" ||
    environment.GITHUB_REF_PROTECTED !== "true" ||
    environment.PARDOT_VERIFICATION_ENVIRONMENT !== "production" ||
    environment.PARDOT_READ_ONLY_CONFIRMED !== "true" ||
    !sha || !/^[a-f0-9]{40}$/.test(sha) ||
    sha !== environment.PARDOT_APPROVED_COMMIT_SHA ||
    !approval || !/^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}$/.test(approval) ||
    approval !== environment.PARDOT_REQUESTED_APPROVAL_REFERENCE ||
    !environment.GITHUB_RUN_ID || !/^[1-9][0-9]*$/.test(environment.GITHUB_RUN_ID) ||
    !environment.GITHUB_TOKEN ||
    !secretSegments ||
    secretSegments.some((segment) => !segment || segment === "." || segment === "..") ||
    !secretSegments.some((segment) => segment === "prd" || segment === "production")
  ) {
    throw new PardotProductionVerificationError(
      "APPROVAL_REQUIRED", "approval", "protected_workflow_context_required",
    );
  }
  return {
    sha,
    approval,
    workflowRunId: environment.GITHUB_RUN_ID,
    githubToken: environment.GITHUB_TOKEN,
  };
}

async function requireProductionProtection(
  githubToken: string,
  fetchImpl: typeof fetch,
): Promise<void> {
  let response: Response;
  try {
    response = await fetchImpl(
      "https://api.github.com/repos/FelixLiangCSHI/agentic-marketing/environments/production",
      {
        method: "GET",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${githubToken}`,
          "X-GitHub-Api-Version": "2022-11-28",
        },
        redirect: "error",
        credentials: "omit",
        cache: "no-store",
        signal: AbortSignal.timeout(15_000),
      },
    );
  } catch {
    throw new PardotProductionVerificationError(
      "APPROVAL_REQUIRED", "approval", "environment_protection_unavailable",
    );
  }
  if (response.status !== 200) {
    throw new PardotProductionVerificationError(
      "APPROVAL_REQUIRED", "approval", "environment_protection_unavailable", response.status,
    );
  }
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new PardotProductionVerificationError(
      "APPROVAL_REQUIRED", "approval", "environment_protection_invalid", response.status,
    );
  }
  const hasReviewer = isRecord(value) &&
    Array.isArray(value.protection_rules) &&
    value.protection_rules.some((rule: unknown) =>
      isRecord(rule) &&
      rule.type === "required_reviewers" &&
      rule.prevent_self_review === true &&
      Array.isArray(rule.reviewers) &&
      rule.reviewers.some((entry: unknown) =>
        isRecord(entry) &&
        (entry.type === "User" || entry.type === "Team") &&
        isRecord(entry.reviewer) &&
        typeof entry.reviewer.id === "number" &&
        Number.isSafeInteger(entry.reviewer.id) &&
        entry.reviewer.id > 0,
      ),
    );
  if (
    !isRecord(value) ||
    value.name !== "production" ||
    !hasReviewer ||
    value.can_admins_bypass === true ||
    !isRecord(value.deployment_branch_policy) ||
    value.deployment_branch_policy.protected_branches !== true ||
    value.deployment_branch_policy.custom_branch_policies !== false
  ) {
    throw new PardotProductionVerificationError(
      "APPROVAL_REQUIRED", "approval", "production_environment_protection_required",
    );
  }
}

export async function verifyPardotProductionConnection(options: VerificationOptions = {}) {
  const context = approvedContext(options.environment ?? process.env);
  const fetchImpl = options.fetchImpl ?? fetch;
  await requireProductionProtection(context.githubToken, fetchImpl);

  let credentials: PardotCredentials;
  try {
    credentials = await (options.loadCredentials ?? loadPardotCredentials)();
  } catch (error) {
    throw new PardotProductionVerificationError(
      error instanceof ChannelConnectorError ? error.code : "CREDENTIALS_INVALID",
      "credentials",
      "protected_credentials_unavailable",
    );
  }
  if (
    credentials.environment !== "production" ||
    credentials.apiBaseUrl !== "https://pi.pardot.com"
  ) {
    throw new PardotProductionVerificationError(
      "CREDENTIALS_INVALID", "credentials", "production_credentials_required",
    );
  }

  let stage: VerificationStage = "oauth";
  const calls = { oauth: 0, "campaign-query": 0 };
  const status: Record<"oauth" | "campaign-query", number | null> = {
    oauth: null, "campaign-query": null,
  };
  let requestFailure: PardotProductionVerificationError | null = null;
  function rejectRequest(
    code: ChannelConnectorErrorCode,
    reason: string,
    httpStatus: number | null = null,
  ): never {
    requestFailure = new PardotProductionVerificationError(code, stage, reason, httpStatus);
    throw requestFailure;
  }
  const connector = createPardotConnector({
    mode: "api",
    credentials,
    fetchImpl: async (input, init) => {
      const url = new URL(String(input));
      if (
        url.origin === credentials.loginBaseUrl &&
        url.pathname === "/services/oauth2/token" &&
        !url.search &&
        init?.method === "POST"
      ) {
        stage = "oauth";
      } else if (
        url.origin === "https://pi.pardot.com" &&
        url.pathname === "/api/v5/objects/campaigns" &&
        init?.method === "GET" &&
        url.searchParams.get("fields") === "id,name,isDeleted" &&
        url.searchParams.get("limit") === "100"
      ) {
        stage = "campaign-query";
      } else {
        rejectRequest("INVALID_REQUEST", "request_outside_read_only_verification");
      }
      if (++calls[stage] !== 1) {
        rejectRequest("INVALID_REQUEST", "verification_retries_not_allowed");
      }
      const response = await fetchImpl(input, init);
      status[stage] = response.status;
      if (response.status !== 200) {
        rejectRequest("PARDOT_UNAVAILABLE", "http_200_required", response.status);
      }
      return response;
    },
  });
  let campaignSampleCount: number;
  try {
    campaignSampleCount = (await connector.queryCampaigns()).campaigns.length;
  } catch (error) {
    if (requestFailure) throw requestFailure;
    if (error instanceof PardotProductionVerificationError) throw error;
    throw new PardotProductionVerificationError(
      error instanceof ChannelConnectorError ? error.code : "PARDOT_UNAVAILABLE",
      stage,
      "provider_request_failed",
      stage === "oauth" || stage === "campaign-query" ? status[stage] : null,
    );
  }
  return {
    success: true,
    environment: "production",
    mode: "api",
    apiBaseUrl: "https://pi.pardot.com",
    oauthHttpStatus: status.oauth,
    campaignQueryHttpStatus: status["campaign-query"],
    campaignSampleCount,
    externalBusinessWrites: 0,
    checkedAt: (options.now ?? new Date()).toISOString(),
    commitSha: context.sha,
    approvalReference: context.approval,
    workflowRunId: context.workflowRunId,
  };
}
