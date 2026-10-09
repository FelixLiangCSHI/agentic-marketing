export type ChannelConnectorErrorCode =
  | "LOCAL_ONLY"
  | "INVALID_REQUEST"
  | "INVALID_PERIOD"
  | "CONNECTOR_DISABLED"
  | "CREDENTIALS_MISSING"
  | "CREDENTIALS_INVALID"
  | "CREDENTIALS_UNSAFE"
  | "TOKEN_STORE_UNAVAILABLE"
  | "VERIFICATION_STORE_UNAVAILABLE"
  | "OAUTH_ORIGIN_INVALID"
  | "OAUTH_STATE_INVALID"
  | "OAUTH_STATE_EXPIRED"
  | "AUTH_DENIED"
  | "AUTH_REQUIRED"
  | "AUTH_EXPIRED"
  | "INSUFFICIENT_SCOPE"
  | "IP_NOT_WHITELISTED"
  | "ACCOUNT_UNAVAILABLE"
  | "ACCOUNT_CHANGED"
  | "ANALYTICS_EMPTY"
  | "ANALYTICS_INCOMPLETE"
  | "UPSTREAM_RESPONSE_INVALID"
  | "QUOTA_EXCEEDED"
  | "RATE_LIMITED"
  | "GOOGLE_UNAVAILABLE"
  | "WECHAT_UNAVAILABLE"
  | "PARDOT_UNAVAILABLE"
  | "TARGET_NOT_FOUND"
  | "TARGET_NOT_ELIGIBLE"
  | "APPROVAL_REQUIRED"
  | "DUTY_SEPARATION_REQUIRED"
  | "DELIVERY_AUTHORIZATION_INVALID"
  | "DELIVERY_AUTHORIZATION_EXPIRED"
  | "DELIVERY_RECONCILIATION_REQUIRED"
  | "DELIVERY_LEDGER_UNAVAILABLE";

export interface GoogleDiagnostic {
  provider: "google";
  httpStatus: number;
  reason: string;
}

export class ChannelConnectorError extends Error {
  constructor(
    public readonly code: ChannelConnectorErrorCode,
    message: string,
    public readonly status: number,
    public readonly diagnostics?: GoogleDiagnostic,
  ) {
    super(message);
    this.name = "ChannelConnectorError";
  }
}
