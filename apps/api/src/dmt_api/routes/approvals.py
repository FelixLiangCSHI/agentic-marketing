"""Approval API: request, list, decide, revoke.

Authentication and RBAC guards run before any persistence access. The
single-use token plaintext is returned exactly once, to the requester, and
never appears in logs or audit payloads.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from dmt_api.approval_service import (
    ApprovalBinding,
    ApprovalService,
    RoleNotAllowedError,
)
from dmt_api.contracts import (
    ID_PATTERN,
    ApprovalType,
    Identifier,
    SemVer,
    Sha256Hash,
)
from dmt_api.errors import error_response
from dmt_api.identity.auth import get_principal, require_roles
from dmt_api.identity.provider import Principal
from dmt_api.identity.roles import APPROVER_ROLES, Role
from dmt_api.persistence import UnitOfWork
from dmt_api.persistence.db import get_session_factory
from dmt_api.persistence.domain import ApprovalRequest
from dmt_api.persistence.errors import (
    ApprovalExpiredError,
    IllegalStateTransitionError,
    NotFoundError,
    SeparationOfDutiesError,
)

router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])

_REQUESTER = require_roles({Role.CONTENT_CREATOR, Role.CAMPAIGN_OPERATOR})
_APPROVER = require_roles({Role.MEDICAL_REVIEWER, Role.CAMPAIGN_APPROVER})
_VIEWER = require_roles(set(Role))
_REVOKER = require_roles({Role.ADMIN})


class PersistenceUnavailableError(Exception):
    """No database is configured in this process (typed 503, never faked)."""


def get_uow(request: Request) -> Iterator[UnitOfWork]:
    factory = get_session_factory(request.app)
    if factory is None:
        raise PersistenceUnavailableError()
    with UnitOfWork(factory) as uow:
        yield uow


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BindingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_artifact_hash: Sha256Hash
    policy_version: SemVer
    prompt_version: SemVer = "0.0.0"
    skill_version: SemVer = "0.0.0"
    workflow_version: SemVer
    scope: str = Field(min_length=1, max_length=256)
    account_id: str = Field(default="", max_length=128)
    budget_limit: str = Field(default="0", max_length=32)
    valid_from: str = Field(default="", max_length=64)
    valid_until: str = Field(default="", max_length=64)
    tool_name: str = Field(default="", max_length=128)
    agent_type: str = Field(default="", max_length=32)

    def to_binding(self) -> ApprovalBinding:
        return ApprovalBinding(**self.model_dump())


class ApprovalCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: Identifier
    approval_type: ApprovalType
    binding: BindingModel
    ttl_seconds: int = Field(default=86400, ge=60, le=7 * 86400)


class ApprovalView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    run_id: str
    approval_type: str
    requester_id: str
    status: str
    input_artifact_hash: str
    policy_version: str
    binding_hash: str
    requested_at: datetime
    decided_at: datetime | None
    expires_at: datetime


def _view(request: ApprovalRequest) -> ApprovalView:
    return ApprovalView(
        approval_id=request.approval_id,
        run_id=request.run_id,
        approval_type=request.approval_type,
        requester_id=request.requester_id,
        status=request.status,
        input_artifact_hash=request.input_artifact_hash,
        policy_version=request.policy_version,
        binding_hash=request.binding_hash,
        requested_at=request.requested_at,
        decided_at=request.decided_at,
        expires_at=request.expires_at,
    )


class ApprovalCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval: ApprovalView
    #: Returned exactly once; delivered out of band to the approver flow.
    approval_token: str


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROVED", "REJECTED"]


class RevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=256)


@router.get("")
def list_approvals(
    run_id: Identifier | None = Query(default=None),
    principal: Principal = Depends(_VIEWER),
    uow: UnitOfWork = Depends(get_uow),
) -> list[ApprovalView]:
    privileged = bool(principal.roles & {Role.ADMIN, Role.AUDITOR})
    approver_types = frozenset(
        approval_type
        for approval_type, roles in APPROVER_ROLES.items()
        if principal.roles & roles
    )
    requests = uow.approvals.list_recent(
        tenant=principal.tenant,
        run_id=run_id,
        requester_id=None if privileged else principal.subject,
        approver_approval_types=frozenset() if privileged else approver_types,
    )
    return [_view(request) for request in requests]


@router.post("", status_code=201, response_model=None)
def create_approval(
    body: ApprovalCreateRequest,
    principal: Principal = Depends(_REQUESTER),
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalCreateResponse | JSONResponse:
    service = ApprovalService(uow, now=_now)
    try:
        run = uow.runs.get(body.run_id)
        if run is None or run.tenant != principal.tenant:
            return error_response(404, "not_found", "run not found", retryable=False)
        request, token = service.create_request(
            run_id=body.run_id,
            approval_type=body.approval_type,
            requester_id=principal.subject,
            requester_roles=principal.roles,
            binding=body.binding.to_binding(),
            expires_at=_now() + timedelta(seconds=body.ttl_seconds),
        )
    except RoleNotAllowedError as exc:
        return error_response(403, "forbidden", str(exc), retryable=False)
    except NotFoundError as exc:
        return error_response(404, "not_found", str(exc), retryable=False)
    return ApprovalCreateResponse(approval=_view(request), approval_token=token)


@router.post("/{approval_id}/decision", response_model=None)
def decide_approval(
    body: DecisionRequest,
    approval_id: str = Path(pattern=r"^[a-z0-9][a-zA-Z0-9_-]{0,127}$"),
    principal: Principal = Depends(_APPROVER),
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalView | JSONResponse:
    service = ApprovalService(uow, now=_now)
    try:
        existing = uow.approvals.get(approval_id)
        if existing is None:
            raise NotFoundError(f"approval {approval_id!r} does not exist")
        run = uow.runs.get(existing.run_id)
        if run is None or run.tenant != principal.tenant:
            return error_response(
                404, "not_found", "approval not found", retryable=False
            )
        request = service.decide(
            approval_id=approval_id,
            approver_id=principal.subject,
            approver_roles=principal.roles,
            decision=body.decision,
        )
    except RoleNotAllowedError as exc:
        return error_response(403, "forbidden", str(exc), retryable=False)
    except SeparationOfDutiesError as exc:
        return error_response(403, "separation_of_duties", str(exc), retryable=False)
    except NotFoundError as exc:
        return error_response(404, "not_found", str(exc), retryable=False)
    except IllegalStateTransitionError as exc:
        return error_response(409, "illegal_state", str(exc), retryable=False)
    except ApprovalExpiredError as exc:
        return error_response(409, "approval_expired", str(exc), retryable=False)
    return _view(request)


@router.post("/{approval_id}/revoke", response_model=None)
def revoke_approval(
    body: RevokeRequest,
    approval_id: str = Path(pattern=r"^[a-z0-9][a-zA-Z0-9_-]{0,127}$"),
    principal: Principal = Depends(_REVOKER),
    uow: UnitOfWork = Depends(get_uow),
) -> ApprovalView | JSONResponse:
    service = ApprovalService(uow, now=_now)
    try:
        existing = uow.approvals.get(approval_id)
        if existing is None:
            raise NotFoundError(f"approval {approval_id!r} does not exist")
        run = uow.runs.get(existing.run_id)
        if run is None or run.tenant != principal.tenant:
            return error_response(
                404, "not_found", "approval not found", retryable=False
            )
        request = service.revoke(
            approval_id, actor_id=principal.subject, reason=body.reason
        )
    except NotFoundError as exc:
        return error_response(404, "not_found", str(exc), retryable=False)
    except IllegalStateTransitionError as exc:
        return error_response(409, "illegal_state", str(exc), retryable=False)
    return _view(request)
