export const RUN_STATUSES = [
  "CREATED",
  "PLANNING",
  "RUNNING",
  "WAITING_TOOL",
  "WAITING_APPROVAL",
  "RETRY_SCHEDULED",
  "SUCCEEDED",
  "FAILED",
  "CANCELLED",
  "COMPENSATING",
  "COMPENSATED",
] as const;
export type RunStatus = (typeof RUN_STATUSES)[number];

export const RUN_EVENT_TYPES = [
  "RUN_STATUS_CHANGED",
  "TASK_STATUS_CHANGED",
  "TOOL_CALL_REQUESTED",
  "TOOL_CALL_FINISHED",
  "APPROVAL_REQUESTED",
  "APPROVAL_DECIDED",
  "CHECKPOINT_SAVED",
  "ERROR_RECORDED",
] as const;
export type RunEventType = (typeof RUN_EVENT_TYPES)[number];

export const TASK_STATUSES = [
  "PENDING",
  "READY",
  "LEASED",
  "RUNNING",
  "SUCCEEDED",
  "FAILED",
  "CANCELLED",
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const APPROVAL_STATUSES = [
  "PENDING",
  "APPROVED",
  "REJECTED",
  "EXPIRED",
  "REVOKED",
] as const;
export type ContractApprovalStatus = (typeof APPROVAL_STATUSES)[number];

export const APPROVAL_TYPES = [
  "content_publication",
  "campaign_activation",
  "budget_change",
] as const;
export type ApprovalType = (typeof APPROVAL_TYPES)[number];

export const TOOL_CALL_STATUSES = [
  "REQUESTED",
  "DENIED",
  "RUNNING",
  "SUCCEEDED",
  "FAILED",
] as const;
export type ToolCallStatus = (typeof TOOL_CALL_STATUSES)[number];

export const PERMISSION_LEVELS = ["L0", "L1", "L2", "L3", "L4"] as const;
export type PermissionLevel = (typeof PERMISSION_LEVELS)[number];

export const CHANNELS = ["linkedin", "google_ads"] as const;
export type Channel = (typeof CHANNELS)[number];

export const CONNECTORS = [
  "llm",
  "embedding",
  "jimeng",
  "linkedin",
  "google_ads",
] as const;
export type Connector = (typeof CONNECTORS)[number];

export const AGENT_TYPES = ["content", "campaign"] as const;
export type AgentType = (typeof AGENT_TYPES)[number];

export const ENVIRONMENTS = ["local", "dev", "sit", "uat", "prd"] as const;
export type Environment = (typeof ENVIRONMENTS)[number];

export const ACTIVATION_STATUSES = [
  "DRAFT",
  "PENDING_APPROVAL",
  "APPROVED",
  "DISPATCHED",
  "FAILED",
  "CANCELLED",
] as const;
export type ActivationStatus = (typeof ACTIVATION_STATUSES)[number];

export const PACKAGE_STATUSES = ["APPROVED", "SUPERSEDED", "REVOKED"] as const;
export type PackageStatus = (typeof PACKAGE_STATUSES)[number];

export interface RunV1 {
  schema_version: "1.0";
  run_id: string;
  parent_run_id: string | null;
  agent_type: AgentType;
  workflow_name: string;
  workflow_version: string;
  tenant: string;
  business_unit: string;
  requester_id: string;
  environment: Environment;
  status: RunStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunEventV1 {
  schema_version: "1.0";
  event_id: string;
  run_id: string;
  sequence: number;
  event_type: RunEventType;
  payload: Record<string, unknown>;
  occurred_at: string;
}

export interface TaskV1 {
  schema_version: "1.0";
  task_id: string;
  run_id: string;
  task_type: string;
  status: TaskStatus;
  depends_on: string[];
  attempt: number;
  max_attempts: number;
  lease_owner: string | null;
  lease_expires_at: string | null;
  created_at: string;
}

export interface ApprovalV1 {
  schema_version: "1.0";
  approval_id: string;
  run_id: string;
  approval_type: ApprovalType;
  requester_id: string;
  approver_id: string | null;
  status: ContractApprovalStatus;
  input_artifact_hash: string;
  policy_version: string;
  requested_at: string;
  decided_at: string | null;
  expires_at: string;
  token_consumed: boolean;
}

export interface ToolCallV1 {
  schema_version: "1.0";
  tool_call_id: string;
  run_id: string;
  task_id: string | null;
  tool_name: string;
  permission_level: PermissionLevel;
  status: ToolCallStatus;
  idempotency_key: string;
  requested_at: string;
  finished_at: string | null;
}

export interface ApprovedContentPackageV1 {
  schema_version: "1.0";
  package_id: string;
  run_id: string;
  agent_type: "content";
  channel: Channel;
  locale: string;
  content_hash: string;
  asset_uris: string[];
  approval_id: string;
  approved_at: string;
  status: PackageStatus;
}

export interface ActivationRequestV1 {
  schema_version: "1.0";
  activation_id: string;
  run_id: string;
  package_id: string;
  channel: Channel;
  account_id: string;
  budget: { amount: number; currency: string };
  schedule: { start_at: string; end_at: string | null };
  approval_id: string;
  idempotency_key: string;
  status: ActivationStatus;
  created_at: string;
}

export interface ConnectorErrorV1 {
  schema_version: "1.0";
  connector: Connector;
  code: string;
  message: string;
  trace_id: string;
  retryable: boolean;
  details: Record<string, unknown> | null;
  occurred_at: string;
}
