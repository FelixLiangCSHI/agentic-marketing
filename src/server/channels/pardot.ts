import type {
  PardotCampaign,
  PardotCampaignQueryResult,
  PardotMode,
  PardotProspect,
  PardotProspectSearchResult,
} from "@/domain/pardot-connector";
import { ChannelConnectorError } from "@/server/channels/errors";
import type { PardotCredentials } from "@/server/channels/pardot-credentials";

const PROSPECT_FIELDS = [
  "id",
  "email",
  "firstName",
  "lastName",
  "company",
  "isDoNotEmail",
  "optedOut",
] as const;
const MAX_RESPONSE_BYTES = 1024 * 1024;
const MAX_SEARCH_RESULTS = 50;
const CAMPAIGN_FIELDS = ["id", "name", "isDeleted"] as const;
const CAMPAIGN_PAGE_SIZE = 100;
const MOCK_CAMPAIGNS: readonly PardotCampaign[] = [
  { id: 42_001, name: "Synthetic Evidence Update" },
  { id: 42_002, name: "Synthetic Product Introduction" },
];

const MOCK_PROSPECTS: readonly PardotProspect[] = [
  {
    id: 10_001,
    firstName: "Avery",
    lastName: "Chen",
    email: "avery.chen@example.test",
    company: "Synthetic General Hospital",
    emailStatus: "eligible",
  },
  {
    id: 10_002,
    firstName: "Morgan",
    lastName: "Lee",
    email: "morgan.lee@example.test",
    company: "Synthetic Imaging Center",
    emailStatus: "eligible",
  },
  {
    id: 10_003,
    firstName: "Jordan",
    lastName: "Patel",
    email: "jordan.patel@example.test",
    company: "Synthetic Medical Group",
    emailStatus: "opted_out",
  },
  {
    id: 10_004,
    firstName: "Taylor",
    lastName: "Kim",
    email: "taylor.kim@example.test",
    company: "Synthetic Health Network",
    emailStatus: "do_not_email",
  },
];

export interface PardotOneToOneEmailInput {
  campaignId: number;
  prospectId: number;
  planId: string;
  subject: string;
  textMessage: string;
}

export interface PardotOneToOneEmailResult {
  prospect: PardotProspect;
  emailId: number | null;
  sentAt: string | null;
  reconciliationRequired: boolean;
}

export interface PardotConnector {
  readonly mode: PardotMode;
  queryCampaigns(afterId?: number | null): Promise<PardotCampaignQueryResult>;
  getCampaign(id: number): Promise<PardotCampaign>;
  searchProspects(query: string): Promise<PardotProspectSearchResult>;
  getProspects(ids: readonly number[]): Promise<readonly PardotProspect[]>;
  sendOneToOneEmail(
    input: PardotOneToOneEmailInput,
  ): Promise<PardotOneToOneEmailResult>;
}

interface PardotConnectorOptions {
  mode: PardotMode;
  credentials?: PardotCredentials;
  fetchImpl?: typeof fetch;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validText(value: unknown, maximumLength: number): value is string {
  return (
    typeof value === "string" &&
    Boolean(value.trim()) &&
    value.length <= maximumLength &&
    !/[\0]/.test(value)
  );
}

function upstreamInvalid(): ChannelConnectorError {
  return new ChannelConnectorError(
    "UPSTREAM_RESPONSE_INVALID",
    "Account Engagement returned an invalid API response.",
    502,
  );
}

function parseOptionalText(
  value: unknown,
  maximumLength: number,
): string | null {
  if (value === undefined || value === null || value === "") return null;
  if (!validText(value, maximumLength)) throw upstreamInvalid();
  return value.trim();
}

function parseProspect(value: unknown): PardotProspect {
  if (
    !isRecord(value) ||
    !Number.isSafeInteger(value.id) ||
    Number(value.id) <= 0 ||
    !validText(value.email, 320) ||
    !/^[^\s@]+@[^\s@]+$/.test(value.email) ||
    typeof value.isDoNotEmail !== "boolean" ||
    typeof value.optedOut !== "boolean"
  ) {
    throw upstreamInvalid();
  }
  return {
    id: Number(value.id),
    email: value.email.trim(),
    firstName: parseOptionalText(value.firstName, 160),
    lastName: parseOptionalText(value.lastName, 160),
    company: parseOptionalText(value.company, 255),
    emailStatus:
      value.optedOut === true
        ? "opted_out"
        : value.isDoNotEmail === true
          ? "do_not_email"
          : "eligible",
  };
}

function parseCampaign(value: unknown): PardotCampaign {
  if (
    !isRecord(value) ||
    !Number.isSafeInteger(value.id) ||
    Number(value.id) <= 0 ||
    !validText(value.name, 255) ||
    value.isDeleted !== false
  ) {
    throw upstreamInvalid();
  }
  return { id: Number(value.id), name: value.name.trim() };
}

function positiveCampaignId(value: number): number {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new ChannelConnectorError(
      "INVALID_REQUEST",
      "Select a positive numeric Account Engagement Campaign ID.",
      400,
    );
  }
  return value;
}

function campaignUnavailable(): ChannelConnectorError {
  return new ChannelConnectorError(
    "TARGET_NOT_FOUND",
    "The selected Account Engagement Campaign no longer exists or is unavailable.",
    404,
  );
}

function parseSearchQuery(value: string): string {
  const query = value.trim();
  if (query.length > 160 || /[\0\r\n]/.test(query)) {
    throw new ChannelConnectorError(
      "INVALID_REQUEST",
      "Prospect search must be 160 characters or fewer.",
      400,
    );
  }
  return query;
}

function normalizeSearchText(prospect: PardotProspect): string {
  return [
    prospect.id,
    prospect.firstName,
    prospect.lastName,
    prospect.email,
    prospect.company,
  ]
    .filter((value) => value !== null)
    .join(" ")
    .toLocaleLowerCase();
}

function filterProspects(
  prospects: readonly PardotProspect[],
  query: string,
): PardotProspect[] {
  const normalized = query.toLocaleLowerCase();
  return prospects
    .filter(
      (prospect) =>
        !normalized || normalizeSearchText(prospect).includes(normalized),
    )
    .slice(0, MAX_SEARCH_RESULTS);
}

function positiveProspectId(value: number): number {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new ChannelConnectorError(
      "INVALID_REQUEST",
      "Prospect IDs must be positive integers.",
      400,
    );
  }
  return value;
}

function requireApiCredentials(
  options: PardotConnectorOptions,
): PardotCredentials {
  if (options.mode !== "api" || !options.credentials) {
    throw new ChannelConnectorError(
      "CREDENTIALS_MISSING",
      "Configure protected Account Engagement OAuth credentials before using API mode.",
      503,
    );
  }
  return options.credentials;
}

function providerFailure(status: number): ChannelConnectorError {
  if (status === 400) {
    return new ChannelConnectorError(
      "INVALID_REQUEST",
      "Account Engagement rejected the request.",
      400,
    );
  }
  if (status === 401) {
    return new ChannelConnectorError(
      "AUTH_REQUIRED",
      "Account Engagement authentication failed. Verify the External Client App and Run As user.",
      401,
    );
  }
  if (status === 403) {
    return new ChannelConnectorError(
      "INSUFFICIENT_SCOPE",
      "The Account Engagement integration user lacks the required Campaign, prospect or one-to-one email ability.",
      403,
    );
  }
  if (status === 404) {
    return new ChannelConnectorError(
      "TARGET_NOT_FOUND",
      "The selected Account Engagement prospect no longer exists or is unavailable.",
      404,
    );
  }
  if (status === 429) {
    return new ChannelConnectorError(
      "RATE_LIMITED",
      "Account Engagement rate-limited the request. Wait before trying again.",
      429,
    );
  }
  return new ChannelConnectorError(
    "PARDOT_UNAVAILABLE",
    "Account Engagement is unavailable.",
    502,
  );
}

function validateEmailInput(input: PardotOneToOneEmailInput): void {
  positiveCampaignId(input.campaignId);
  positiveProspectId(input.prospectId);
  if (
    !validText(input.planId, 256) ||
    !validText(input.subject, 255) ||
    !validText(input.textMessage, 16_000)
  ) {
    throw new ChannelConnectorError(
      "INVALID_REQUEST",
      "The approved email content is missing or exceeds Account Engagement limits.",
      400,
    );
  }
}

export function createPardotConnector(
  options: PardotConnectorOptions,
): PardotConnector {
  const fetchImpl = options.fetchImpl ?? fetch;
  let accessToken: string | null = null;

  async function readJson(
    url: URL,
    init: RequestInit,
    allowEmpty = false,
  ): Promise<{ status: number; value: unknown }> {
    let response: Response;
    try {
      response = await fetchImpl(url.toString(), {
        ...init,
        cache: "no-store",
        credentials: "omit",
        redirect: "error",
        signal: AbortSignal.timeout(15_000),
      });
    } catch {
      throw new ChannelConnectorError(
        "PARDOT_UNAVAILABLE",
        "Account Engagement is unavailable.",
        502,
      );
    }
    const declaredLength = response.headers.get("content-length");
    if (
      declaredLength !== null &&
      (!Number.isFinite(Number(declaredLength)) ||
        Number(declaredLength) < 0 ||
        Number(declaredLength) > MAX_RESPONSE_BYTES)
    ) {
      throw upstreamInvalid();
    }
    let bytes: Uint8Array;
    try {
      bytes = new Uint8Array(await response.arrayBuffer());
    } catch {
      throw upstreamInvalid();
    }
    if (bytes.byteLength > MAX_RESPONSE_BYTES) throw upstreamInvalid();
    let value: unknown = null;
    if (bytes.byteLength > 0) {
      try {
        value = JSON.parse(
          new TextDecoder("utf-8", { fatal: true }).decode(bytes),
        ) as unknown;
      } catch {
        throw upstreamInvalid();
      }
    } else if (!allowEmpty) {
      throw upstreamInvalid();
    }
    if (!response.ok) throw providerFailure(response.status);
    return { status: response.status, value };
  }

  async function authenticate(): Promise<string> {
    if (accessToken) return accessToken;
    const active = requireApiCredentials(options);
    const url = new URL("/services/oauth2/token", active.loginBaseUrl);
    const response = await readJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "client_credentials",
        client_id: active.clientId,
        client_secret: active.clientSecret,
      }),
    });
    if (
      !isRecord(response.value) ||
      !validText(response.value.access_token, 8192) ||
      response.value.token_type !== "Bearer"
    ) {
      throw upstreamInvalid();
    }
    accessToken = response.value.access_token;
    return accessToken;
  }

  async function apiRequest(
    path: string,
    init: RequestInit,
    allowEmpty = false,
  ): Promise<{ status: number; value: unknown }> {
    const active = requireApiCredentials(options);
    if (!path.startsWith("/api/v5/")) {
      throw new ChannelConnectorError(
        "PARDOT_UNAVAILABLE",
        "Account Engagement API requests must use an approved v5 endpoint.",
        502,
      );
    }
    const url = new URL(path, active.apiBaseUrl);
    const requestWithCurrentToken = async () => {
      const headers = new Headers(init.headers);
      headers.set("Accept", "application/json");
      headers.set("Authorization", `Bearer ${await authenticate()}`);
      headers.set("Pardot-Business-Unit-Id", active.businessUnitId);
      return readJson(url, { ...init, headers }, allowEmpty);
    };
    try {
      return await requestWithCurrentToken();
    } catch (error) {
      if (
        error instanceof ChannelConnectorError &&
        error.code === "AUTH_REQUIRED"
      ) {
        accessToken = null;
        return requestWithCurrentToken();
      }
      throw error;
    }
  }

  async function apiProspect(id: number): Promise<PardotProspect> {
    const url = new URL(
      `/api/v5/objects/prospects/${positiveProspectId(id)}`,
      requireApiCredentials(options).apiBaseUrl,
    );
    url.searchParams.set("fields", PROSPECT_FIELDS.join(","));
    const response = await apiRequest(
      `${url.pathname}${url.search}`,
      { method: "GET" },
    );
    return parseProspect(response.value);
  }

  return {
    mode: options.mode,

    async queryCampaigns(afterId = null) {
      if (afterId !== null) positiveCampaignId(afterId);
      if (options.mode === "mock") {
        return {
          mode: "mock",
          campaigns: MOCK_CAMPAIGNS.filter(
            (campaign) => afterId === null || campaign.id > afterId,
          ),
          nextAfterId: null,
        };
      }
      const url = new URL(
        "/api/v5/objects/campaigns",
        requireApiCredentials(options).apiBaseUrl,
      );
      url.searchParams.set("fields", CAMPAIGN_FIELDS.join(","));
      url.searchParams.set("limit", String(CAMPAIGN_PAGE_SIZE));
      url.searchParams.set("orderBy", "id ASC");
      url.searchParams.set("deleted", "false");
      if (afterId !== null) {
        url.searchParams.set("idGreaterThan", String(afterId));
      }
      const response = await apiRequest(
        `${url.pathname}${url.search}`,
        { method: "GET" },
      );
      if (
        !isRecord(response.value) ||
        !Array.isArray(response.value.values) ||
        response.value.values.length > CAMPAIGN_PAGE_SIZE
      ) {
        throw upstreamInvalid();
      }
      const campaigns = response.value.values.map(parseCampaign);
      let previousId = afterId ?? 0;
      for (const campaign of campaigns) {
        if (campaign.id <= previousId) throw upstreamInvalid();
        previousId = campaign.id;
      }
      return {
        mode: "api",
        campaigns,
        nextAfterId:
          campaigns.length === CAMPAIGN_PAGE_SIZE ? previousId : null,
      };
    },

    async getCampaign(rawId) {
      const id = positiveCampaignId(rawId);
      if (options.mode === "mock") {
        const campaign = MOCK_CAMPAIGNS.find((candidate) => candidate.id === id);
        if (!campaign) throw campaignUnavailable();
        return { ...campaign };
      }
      const url = new URL(
        `/api/v5/objects/campaigns/${id}`,
        requireApiCredentials(options).apiBaseUrl,
      );
      url.searchParams.set("fields", CAMPAIGN_FIELDS.join(","));
      let response: { status: number; value: unknown };
      try {
        response = await apiRequest(
          `${url.pathname}${url.search}`,
          { method: "GET" },
        );
      } catch (error) {
        if (
          error instanceof ChannelConnectorError &&
          error.code === "TARGET_NOT_FOUND"
        ) {
          throw campaignUnavailable();
        }
        throw error;
      }
      if (isRecord(response.value) && response.value.isDeleted === true) {
        throw campaignUnavailable();
      }
      const campaign = parseCampaign(response.value);
      if (campaign.id !== id) throw upstreamInvalid();
      return campaign;
    },

    async searchProspects(rawQuery) {
      const query = parseSearchQuery(rawQuery);
      if (options.mode === "mock") {
        const filtered = filterProspects(MOCK_PROSPECTS, query);
        return {
          mode: "mock",
          prospects: filtered,
          truncated: false,
        };
      }
      if (/^\d+$/.test(query)) {
        try {
          return {
            mode: "api",
            prospects: [await apiProspect(Number(query))],
            truncated: false,
          };
        } catch (error) {
          if (
            error instanceof ChannelConnectorError &&
            error.code === "TARGET_NOT_FOUND"
          ) {
            return { mode: "api", prospects: [], truncated: false };
          }
          throw error;
        }
      }
      const url = new URL(
        "/api/v5/objects/prospects",
        requireApiCredentials(options).apiBaseUrl,
      );
      url.searchParams.set("fields", PROSPECT_FIELDS.join(","));
      url.searchParams.set("limit", "1000");
      url.searchParams.set("orderBy", "id DESC");
      const response = await apiRequest(
        `${url.pathname}${url.search}`,
        { method: "GET" },
      );
      if (!isRecord(response.value) || !Array.isArray(response.value.values)) {
        throw upstreamInvalid();
      }
      const all = response.value.values.map(parseProspect);
      const prospects = filterProspects(all, query);
      return {
        mode: "api",
        prospects,
        truncated:
          all.length > prospects.length ||
          typeof response.value.nextPageUrl === "string" ||
          typeof response.value.nextPageToken === "string",
      };
    },

    async getProspects(ids) {
      const uniqueIds = ids.map(positiveProspectId);
      if (new Set(uniqueIds).size !== uniqueIds.length || uniqueIds.length > 10) {
        throw new ChannelConnectorError(
          "INVALID_REQUEST",
          "Select up to 10 unique Account Engagement prospects.",
          400,
        );
      }
      if (options.mode === "mock") {
        return uniqueIds.map((id) => {
          const prospect = MOCK_PROSPECTS.find((candidate) => candidate.id === id);
          if (!prospect) {
            throw new ChannelConnectorError(
              "TARGET_NOT_FOUND",
              "A selected Account Engagement prospect is unavailable.",
              404,
            );
          }
          return prospect;
        });
      }
      const prospects: PardotProspect[] = [];
      for (const id of uniqueIds) {
        prospects.push(await apiProspect(id));
      }
      return prospects;
    },

    async sendOneToOneEmail(input) {
      if (options.mode !== "api") {
        throw new ChannelConnectorError(
          "INVALID_REQUEST",
          "Mock mode cannot perform an external Account Engagement write.",
          400,
        );
      }
      validateEmailInput(input);
      const [prospect] = await this.getProspects([input.prospectId]);
      if (!prospect || prospect.emailStatus !== "eligible") {
        throw new ChannelConnectorError(
          "TARGET_NOT_ELIGIBLE",
          "The selected prospect is opted out or marked Do Not Email.",
          409,
        );
      }
      await this.getCampaign(input.campaignId);
      const active = requireApiCredentials(options);
      const url = new URL(
        "/api/v5/objects/emails",
        active.apiBaseUrl,
      );
      url.searchParams.set("fields", "id,sentAt");
      try {
        const response = await apiRequest(
          `${url.pathname}${url.search}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: `Agentic ${input.planId} ${prospect.id}`.slice(0, 255),
              campaignId: input.campaignId,
              prospectId: prospect.id,
              subject: input.subject,
              textMessage: input.textMessage,
            }),
          },
          true,
        );
        if (response.status === 204) {
          return {
            prospect,
            emailId: null,
            sentAt: null,
            reconciliationRequired: true,
          };
        }
        if (
          response.status !== 201 ||
          !isRecord(response.value) ||
          !Number.isSafeInteger(response.value.id) ||
          Number(response.value.id) <= 0 ||
          (response.value.sentAt !== undefined &&
            response.value.sentAt !== null &&
            !validText(response.value.sentAt, 64))
        ) {
          throw upstreamInvalid();
        }
        return {
          prospect,
          emailId: Number(response.value.id),
          sentAt:
            typeof response.value.sentAt === "string"
              ? response.value.sentAt
              : null,
          reconciliationRequired: false,
        };
      } catch (error) {
        if (
          error instanceof ChannelConnectorError &&
          (error.code === "PARDOT_UNAVAILABLE" ||
            error.code === "UPSTREAM_RESPONSE_INVALID")
        ) {
          throw new ChannelConnectorError(
            "DELIVERY_RECONCILIATION_REQUIRED",
            "The Account Engagement email write returned an ambiguous result. Reconcile it before retrying.",
            409,
          );
        }
        throw error;
      }
    },
  };
}
