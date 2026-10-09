import { ChannelConnectorError } from "@/server/channels/errors";
import { loadProtectedChannelCredentials } from "@/server/channels/protected-channel-credentials";

export interface PardotCredentials {
  clientId: string;
  clientSecret: string;
  businessUnitId: string;
  businessUnitName?: string;
  integrationUserName?: string;
  campaignId?: number;
  environment: "production" | "sandbox" | "developer";
  loginBaseUrl:
    | "https://login.salesforce.com"
    | "https://test.salesforce.com"
    | `https://${string}.my.salesforce.com`;
  apiBaseUrl: "https://pi.pardot.com" | "https://pi.demo.pardot.com";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function invalidCredentials(): ChannelConnectorError {
  return new ChannelConnectorError(
    "CREDENTIALS_INVALID",
    "The protected Account Engagement OAuth credentials are invalid.",
    503,
  );
}

function credentialText(
  value: Record<string, unknown>,
  field: string,
  maximumLength: number,
): string {
  const candidate = value[field];
  if (
    typeof candidate !== "string" ||
    !candidate.trim() ||
    candidate.trim().length > maximumLength ||
    /[\r\n\0]/.test(candidate)
  ) {
    throw invalidCredentials();
  }
  return candidate.trim();
}

function salesforceLoginBaseUrl(
  pardot: Record<string, unknown>,
  environment: PardotCredentials["environment"],
): PardotCredentials["loginBaseUrl"] {
  if (pardot.loginDomain === undefined) {
    return environment === "sandbox"
      ? "https://test.salesforce.com"
      : "https://login.salesforce.com";
  }
  const domain = credentialText(pardot, "loginDomain", 255)
    .replace(/^https:\/\//i, "")
    .replace(/\/$/, "")
    .toLowerCase();
  const match =
    /^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\.(?:(sandbox|develop|scratch|trailblaze)\.)?my\.salesforce\.com$/.exec(
      domain,
    );
  if (!match) throw invalidCredentials();
  return match[2]
    ? `https://${match[1]}.${match[2]}.my.salesforce.com`
    : `https://${match[1]}.my.salesforce.com`;
}

export function parsePardotCredentials(value: unknown): PardotCredentials {
  if (
    !isRecord(value) ||
    value.schemaVersion !== 1 ||
    !isRecord(value.pardot)
  ) {
    throw invalidCredentials();
  }
  const pardot = value.pardot;
  const allowedFields = new Set([
    "clientId",
    "clientSecret",
    "businessUnitId",
    "businessUnitName",
    "integrationUserName",
    "campaignId",
    "environment",
    "loginDomain",
  ]);
  if (Object.keys(pardot).some((field) => !allowedFields.has(field))) {
    throw invalidCredentials();
  }
  const clientId = credentialText(pardot, "clientId", 512);
  const clientSecret = credentialText(pardot, "clientSecret", 4096);
  const businessUnitId = credentialText(pardot, "businessUnitId", 18);
  if (!/^0Uv[A-Za-z0-9]{15}$/.test(businessUnitId)) {
    throw invalidCredentials();
  }
  if (
    pardot.campaignId !== undefined &&
    (!Number.isSafeInteger(pardot.campaignId) ||
      Number(pardot.campaignId) <= 0)
  ) {
    throw invalidCredentials();
  }
  if (
    pardot.environment !== "production" &&
    pardot.environment !== "sandbox" &&
    pardot.environment !== "developer"
  ) {
    throw invalidCredentials();
  }
  return {
    clientId,
    clientSecret,
    businessUnitId,
    ...(pardot.businessUnitName === undefined
      ? {}
      : { businessUnitName: credentialText(pardot, "businessUnitName", 255) }),
    ...(pardot.integrationUserName === undefined
      ? {}
      : { integrationUserName: credentialText(pardot, "integrationUserName", 255) }),
    ...(pardot.campaignId === undefined
      ? {}
      : { campaignId: Number(pardot.campaignId) }),
    environment: pardot.environment,
    loginBaseUrl: salesforceLoginBaseUrl(pardot, pardot.environment),
    apiBaseUrl:
      pardot.environment === "production"
        ? "https://pi.pardot.com"
        : "https://pi.demo.pardot.com",
  };
}

export async function loadPardotCredentials(): Promise<PardotCredentials> {
  return parsePardotCredentials(
    await loadProtectedChannelCredentials("Account Engagement"),
  );
}
