"""Pydantic runtime validation for the v1 cross-language domain contracts.

These models mirror ``packages/domain-contracts/schemas/*.v1.schema.json``
exactly. CI validates Python and TypeScript against the same golden/invalid
fixtures; results must be 100% identical. Do not loosen a model here without
updating the JSON Schema (and vice versa) — contract changes require major
version bumps when they break compatibility.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
)

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
NAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,63}$"
SEMVER_PATTERN = r"^\d+\.\d+\.\d+$"
DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$"
HASH_PATTERN = r"^sha256:[a-f0-9]{64}$"
URI_PATTERN = r"^[a-z][a-z0-9+.-]*://[^\s]+$"
IDEMPOTENCY_PATTERN = r"^[A-Za-z0-9_-]{8,128}$"
LOCALE_PATTERN = r"^[a-z]{2}(-[A-Z]{2})?$"
CODE_PATTERN = r"^[a-z0-9][a-z0-9_]{1,63}$"
TRACE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"

Identifier = Annotated[StrictStr, Field(pattern=ID_PATTERN)]
Name = Annotated[StrictStr, Field(pattern=NAME_PATTERN)]
SemVer = Annotated[StrictStr, Field(pattern=SEMVER_PATTERN)]
DateTimeUtc = Annotated[StrictStr, Field(pattern=DATETIME_PATTERN)]
Sha256Hash = Annotated[StrictStr, Field(pattern=HASH_PATTERN)]
Uri = Annotated[StrictStr, Field(pattern=URI_PATTERN)]
IdempotencyKey = Annotated[StrictStr, Field(pattern=IDEMPOTENCY_PATTERN)]
Locale = Annotated[StrictStr, Field(pattern=LOCALE_PATTERN)]
ErrorCode = Annotated[StrictStr, Field(pattern=CODE_PATTERN)]
TraceId = Annotated[StrictStr, Field(pattern=TRACE_ID_PATTERN)]

RunStatus = Literal[
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
]
RunEventType = Literal[
    "RUN_STATUS_CHANGED",
    "TASK_STATUS_CHANGED",
    "TOOL_CALL_REQUESTED",
    "TOOL_CALL_FINISHED",
    "APPROVAL_REQUESTED",
    "APPROVAL_DECIDED",
    "CHECKPOINT_SAVED",
    "ERROR_RECORDED",
]
TaskStatus = Literal[
    "PENDING", "READY", "LEASED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"
]
ApprovalType = Literal["content_publication", "campaign_activation", "budget_change"]
ApprovalStatus = Literal["PENDING", "APPROVED", "REJECTED", "EXPIRED", "REVOKED"]
ToolCallStatus = Literal["REQUESTED", "DENIED", "RUNNING", "SUCCEEDED", "FAILED"]
PermissionLevel = Literal["L0", "L1", "L2", "L3", "L4"]
Channel = Literal["linkedin", "google_ads"]
Connector = Literal["llm", "embedding", "jimeng", "linkedin", "google_ads"]
AgentType = Literal["content", "campaign"]
Environment = Literal["local", "dev", "sit", "uat", "prd"]
ActivationStatus = Literal[
    "DRAFT", "PENDING_APPROVAL", "APPROVED", "DISPATCHED", "FAILED", "CANCELLED"
]
PackageStatus = Literal["APPROVED", "SUPERSEDED", "REVOKED"]
Market = Literal["US", "CN"]
MediaType = Literal["image"]
ProductApprovalStatus = Literal["APPROVED", "DRAFT", "REVOKED"]
Classification = Literal["internal", "confidential-approved-for-provider"]
ProductChangeType = Literal["CREATED", "UPDATED", "REVOKED", "DELETED"]
ProductEntityType = Literal["document", "claim"]


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"]


class RunV1(_ContractModel):
    run_id: Identifier
    parent_run_id: Identifier | None
    agent_type: AgentType
    workflow_name: Name
    workflow_version: SemVer
    tenant: Identifier
    business_unit: Identifier
    requester_id: Identifier
    environment: Environment
    status: RunStatus
    created_at: DateTimeUtc
    started_at: DateTimeUtc | None
    finished_at: DateTimeUtc | None


class RunEventV1(_ContractModel):
    event_id: Identifier
    run_id: Identifier
    sequence: Annotated[StrictInt, Field(ge=0)]
    event_type: RunEventType
    payload: dict[str, Any]
    occurred_at: DateTimeUtc


class TaskV1(_ContractModel):
    task_id: Identifier
    run_id: Identifier
    task_type: Name
    status: TaskStatus
    depends_on: list[Identifier]
    attempt: Annotated[StrictInt, Field(ge=0)]
    max_attempts: Annotated[StrictInt, Field(ge=1)]
    lease_owner: Identifier | None
    lease_expires_at: DateTimeUtc | None
    created_at: DateTimeUtc

    @field_validator("depends_on")
    @classmethod
    def _unique_depends_on(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("depends_on entries must be unique")
        return value


class ApprovalV1(_ContractModel):
    approval_id: Identifier
    run_id: Identifier
    approval_type: ApprovalType
    requester_id: Identifier
    approver_id: Identifier | None
    status: ApprovalStatus
    input_artifact_hash: Sha256Hash
    policy_version: SemVer
    requested_at: DateTimeUtc
    decided_at: DateTimeUtc | None
    expires_at: DateTimeUtc
    token_consumed: StrictBool


class ToolCallV1(_ContractModel):
    tool_call_id: Identifier
    run_id: Identifier
    task_id: Identifier | None
    tool_name: Name
    permission_level: PermissionLevel
    status: ToolCallStatus
    idempotency_key: IdempotencyKey
    requested_at: DateTimeUtc
    finished_at: DateTimeUtc | None


class ApprovedContentPackageV1(_ContractModel):
    package_id: Identifier
    run_id: Identifier
    agent_type: Literal["content"]
    channel: Channel
    locale: Locale
    content_hash: Sha256Hash
    asset_uris: list[Uri]
    approval_id: Identifier
    approved_at: DateTimeUtc
    status: PackageStatus

    @field_validator("asset_uris")
    @classmethod
    def _unique_asset_uris(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("asset_uris entries must be unique")
        return value


class BudgetV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    amount: Union[StrictInt, StrictFloat]
    currency: Annotated[StrictStr, Field(pattern=r"^[A-Z]{3}$")]

    @field_validator("amount")
    @classmethod
    def _non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("amount must be >= 0")
        return value


class ScheduleV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    start_at: DateTimeUtc
    end_at: DateTimeUtc | None


class ActivationRequestV1(_ContractModel):
    activation_id: Identifier
    run_id: Identifier
    package_id: Identifier
    channel: Channel
    account_id: Identifier
    budget: BudgetV1
    schedule: ScheduleV1
    approval_id: Identifier
    idempotency_key: IdempotencyKey
    status: ActivationStatus
    created_at: DateTimeUtc


class ConnectorErrorV1(_ContractModel):
    connector: Connector
    code: ErrorCode
    message: Annotated[StrictStr, Field(min_length=1, max_length=2000)]
    trace_id: TraceId
    retryable: StrictBool
    details: dict[str, Any] | None
    occurred_at: DateTimeUtc


def _require_unique(field_name: str, value: list[str]) -> list[str]:
    if len(set(value)) != len(value):
        raise ValueError(f"{field_name} entries must be unique")
    return value


class ContentRequestV1(_ContractModel):
    """Frozen Content Agent input contract (Phase 02 / Subphase 01).

    ``user_prompt``, ``campaign_context`` and attachment references are
    untrusted data: they are validated for shape only and must never be
    executed as instructions. The Content Agent receives no campaign
    account, budget or channel write credential fields by design.
    """

    request_id: Identifier
    tenant: Identifier
    business_unit: Identifier
    product_ids: Annotated[list[Identifier], Field(min_length=1, max_length=16)]
    market: Market
    locale: Locale
    target_audience: Annotated[
        list[Annotated[StrictStr, Field(min_length=1, max_length=200)]],
        Field(min_length=1, max_length=16),
    ]
    target_channels: Annotated[list[Channel], Field(min_length=1)]
    objective: Annotated[StrictStr, Field(min_length=1, max_length=2000)]
    campaign_context: Annotated[StrictStr, Field(max_length=4000)] | None = None
    user_prompt: Annotated[StrictStr, Field(max_length=8000)] | None = None
    attachment_artifact_ids: Annotated[
        list[Identifier], Field(max_length=16)
    ] = Field(default_factory=list)
    requested_media_types: list[MediaType]
    deadline: DateTimeUtc | None = None
    created_at: DateTimeUtc

    @field_validator(
        "product_ids",
        "target_audience",
        "target_channels",
        "attachment_artifact_ids",
        "requested_media_types",
    )
    @classmethod
    def _unique_lists(cls, value: list[str], info: Any) -> list[str]:
        return _require_unique(str(info.field_name), value)


class ProductDocumentV1(_ContractModel):
    """Approved product source document. ``content`` is untrusted free text."""

    source_id: Identifier
    source_version: SemVer
    product_id: Identifier
    tenant: Identifier
    market: Market
    locale: Locale
    approval_status: ProductApprovalStatus
    approved_by: Identifier | None
    effective_from: DateTimeUtc
    expires_at: DateTimeUtc | None
    revoked_at: DateTimeUtc | None
    classification: Classification
    content_hash: Sha256Hash
    content: Annotated[StrictStr, Field(max_length=100000)]
    updated_at: DateTimeUtc


class ProductClaimV1(_ContractModel):
    """Approved product claim bound to its source document."""

    claim_id: Identifier
    product_id: Identifier
    tenant: Identifier
    market: Market
    locale: Locale
    claim_text: Annotated[StrictStr, Field(min_length=1, max_length=4000)]
    source_id: Identifier
    source_version: SemVer
    approval_status: ProductApprovalStatus
    approved_by: Identifier | None
    effective_from: DateTimeUtc
    expires_at: DateTimeUtc | None
    revoked_at: DateTimeUtc | None
    classification: Classification
    content_hash: Sha256Hash
    updated_at: DateTimeUtc


class ProductChangeV1(_ContractModel):
    """Single incremental product change feed event."""

    change_id: Identifier
    cursor: Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
    change_type: ProductChangeType
    entity_type: ProductEntityType
    entity_id: Identifier
    product_id: Identifier
    tenant: Identifier
    source_version: SemVer
    content_hash: Sha256Hash | None
    occurred_at: DateTimeUtc


CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "run.v1": RunV1,
    "run-event.v1": RunEventV1,
    "task.v1": TaskV1,
    "approval.v1": ApprovalV1,
    "tool-call.v1": ToolCallV1,
    "approved-content-package.v1": ApprovedContentPackageV1,
    "activation-request.v1": ActivationRequestV1,
    "connector-error.v1": ConnectorErrorV1,
    "content-request.v1": ContentRequestV1,
    "product-document.v1": ProductDocumentV1,
    "product-claim.v1": ProductClaimV1,
    "product-change.v1": ProductChangeV1,
}


def validate_contract(name: str, document: object) -> tuple[bool, list[str]]:
    """Validate a document against a named v1 contract.

    Returns ``(valid, errors)`` where ``errors`` is a list of human-readable
    messages. Unknown contract names raise ``KeyError``.
    """
    model = CONTRACT_MODELS[name]
    try:
        model.model_validate(document)
    except ValidationError as exc:
        return False, [
            f"{'/'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        ]
    return True, []
