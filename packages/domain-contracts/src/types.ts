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

export const CAMPAIGN_OBJECTIVES = [
  "LEAD_GENERATION",
  "BRAND_AWARENESS",
  "WEBSITE_VISITS",
  "ENGAGEMENT",
  "CONVERSIONS",
] as const;
export type CampaignObjective = (typeof CAMPAIGN_OBJECTIVES)[number];

export const PROPOSAL_STATUSES = [
  "DRAFT",
  "SUPERSEDED",
  "INVALIDATED",
] as const;
export type ProposalStatus = (typeof PROPOSAL_STATUSES)[number];

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
  content_package_hash?: string | null;
  input_hash?: string | null;
  policy_version?: string | null;
}

export interface CampaignProposalV1 {
  schema_version: "1.0";
  proposal_id: string;
  version: number;
  status: ProposalStatus;
  tenant_id: string;
  run_id: string;
  content_package_id: string;
  content_package_hash: string;
  channel: Channel;
  account_id: string;
  objective: CampaignObjective;
  campaign_name: string;
  budget: {
    currency: string;
    total_limit_minor: number;
    daily_limit_minor: number | null;
  };
  schedule: { timezone: string; start_at: string; end_at: string };
  audience: { markets: Market[]; excluded_segments: string[] };
  channel_variant_refs: string[];
  asset_hashes: string[];
  policy_version: string;
  workflow_version: string;
  input_hash: string;
  warnings: string[];
  created_by: string;
  created_at: string;
}

export interface CampaignDryRunV1 {
  schema_version: "1.0";
  proposal_id: string;
  policy_version: string;
  valid: boolean;
  request_fingerprint: string;
  errors: { code: string; message: string; field: string }[];
  warnings: string[];
  evaluated_at: string;
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

export const MARKETS = ["US", "CN"] as const;
export type Market = (typeof MARKETS)[number];

export const MEDIA_TYPES = ["image"] as const;
export type MediaType = (typeof MEDIA_TYPES)[number];

export const PRODUCT_APPROVAL_STATUSES = [
  "APPROVED",
  "DRAFT",
  "REVOKED",
] as const;
export type ProductApprovalStatus =
  (typeof PRODUCT_APPROVAL_STATUSES)[number];

export const CLASSIFICATIONS = [
  "internal",
  "confidential-approved-for-provider",
] as const;
export type Classification = (typeof CLASSIFICATIONS)[number];

export const PRODUCT_CHANGE_TYPES = [
  "CREATED",
  "UPDATED",
  "REVOKED",
  "DELETED",
] as const;
export type ProductChangeType = (typeof PRODUCT_CHANGE_TYPES)[number];

export const PRODUCT_ENTITY_TYPES = ["document", "claim"] as const;
export type ProductEntityType = (typeof PRODUCT_ENTITY_TYPES)[number];

export interface ContentRequestV1 {
  schema_version: "1.0";
  request_id: string;
  tenant: string;
  business_unit: string;
  product_ids: string[];
  market: Market;
  locale: string;
  target_audience: string[];
  target_channels: Channel[];
  objective: string;
  campaign_context?: string | null;
  user_prompt?: string | null;
  attachment_artifact_ids?: string[];
  requested_media_types: MediaType[];
  deadline?: string | null;
  created_at: string;
}

export interface ProductDocumentV1 {
  schema_version: "1.0";
  source_id: string;
  source_version: string;
  product_id: string;
  tenant: string;
  market: Market;
  locale: string;
  approval_status: ProductApprovalStatus;
  approved_by: string | null;
  effective_from: string;
  expires_at: string | null;
  revoked_at: string | null;
  classification: Classification;
  content_hash: string;
  /** Untrusted free text: data only, never instructions. */
  content: string;
  updated_at: string;
}

export interface ProductClaimV1 {
  schema_version: "1.0";
  claim_id: string;
  product_id: string;
  tenant: string;
  market: Market;
  locale: string;
  /** Untrusted free text: data only, never instructions. */
  claim_text: string;
  source_id: string;
  source_version: string;
  approval_status: ProductApprovalStatus;
  approved_by: string | null;
  effective_from: string;
  expires_at: string | null;
  revoked_at: string | null;
  classification: Classification;
  content_hash: string;
  updated_at: string;
}

export interface ProductChangeV1 {
  schema_version: "1.0";
  change_id: string;
  cursor: string;
  change_type: ProductChangeType;
  entity_type: ProductEntityType;
  entity_id: string;
  product_id: string;
  tenant: string;
  source_version: string;
  content_hash: string | null;
  occurred_at: string;
}
