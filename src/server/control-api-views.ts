/**
 * Runtime validation for Control API (Python) responses consumed by the
 * Next.js portal. 契约对象必须经运行时校验：这两个页面是 TS→Python 的边界，
 * 不允许对 `response.json()` 盲转型。
 */

export interface TrackView {
  status: string;
  decided_by: string | null;
}

export interface ReviewView {
  review_id: string;
  run_id: string;
  status: string;
  revision: number;
  automated_status: string;
  policy_version: string;
  artifact_hash: string;
  created_by: string;
  created_at: string;
  medical: TrackView;
  marketing: TrackView;
}

export interface ApprovalView {
  approval_id: string;
  run_id: string;
  approval_type: string;
  requester_id: string;
  status: string;
  requested_at: string;
  expires_at: string;
}

export class ControlApiShapeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ControlApiShapeError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireString(
  record: Record<string, unknown>,
  key: string,
  context: string,
): string {
  const value = record[key];
  if (typeof value !== "string") {
    throw new ControlApiShapeError(`${context}.${key} 不是字符串`);
  }
  return value;
}

function requireNumber(
  record: Record<string, unknown>,
  key: string,
  context: string,
): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ControlApiShapeError(`${context}.${key} 不是数字`);
  }
  return value;
}

function parseTrack(value: unknown, context: string): TrackView {
  if (!isRecord(value)) {
    throw new ControlApiShapeError(`${context} 不是对象`);
  }
  const decidedBy = value["decided_by"];
  if (decidedBy !== null && typeof decidedBy !== "string") {
    throw new ControlApiShapeError(`${context}.decided_by 不是字符串或 null`);
  }
  return {
    status: requireString(value, "status", context),
    decided_by: decidedBy ?? null,
  };
}

function parseReview(value: unknown, index: number): ReviewView {
  const context = `reviews[${index}]`;
  if (!isRecord(value)) {
    throw new ControlApiShapeError(`${context} 不是对象`);
  }
  return {
    review_id: requireString(value, "review_id", context),
    run_id: requireString(value, "run_id", context),
    status: requireString(value, "status", context),
    revision: requireNumber(value, "revision", context),
    automated_status: requireString(value, "automated_status", context),
    policy_version: requireString(value, "policy_version", context),
    artifact_hash: requireString(value, "artifact_hash", context),
    created_by: requireString(value, "created_by", context),
    created_at: requireString(value, "created_at", context),
    medical: parseTrack(value["medical"], `${context}.medical`),
    marketing: parseTrack(value["marketing"], `${context}.marketing`),
  };
}

function parseApproval(value: unknown, index: number): ApprovalView {
  const context = `approvals[${index}]`;
  if (!isRecord(value)) {
    throw new ControlApiShapeError(`${context} 不是对象`);
  }
  return {
    approval_id: requireString(value, "approval_id", context),
    run_id: requireString(value, "run_id", context),
    approval_type: requireString(value, "approval_type", context),
    requester_id: requireString(value, "requester_id", context),
    status: requireString(value, "status", context),
    requested_at: requireString(value, "requested_at", context),
    expires_at: requireString(value, "expires_at", context),
  };
}

export function parseReviewViews(data: unknown): ReviewView[] {
  if (!Array.isArray(data)) {
    throw new ControlApiShapeError("reviews 响应不是数组");
  }
  return data.map(parseReview);
}

export function parseApprovalViews(data: unknown): ApprovalView[] {
  if (!Array.isArray(data)) {
    throw new ControlApiShapeError("approvals 响应不是数组");
  }
  return data.map(parseApproval);
}
