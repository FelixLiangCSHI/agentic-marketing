"""Approval service: role routing, binding, and token lifecycle.

Sits between the API routes / worker and the approval repository. Enforces:

* only the mapped requester roles may open a request for an approval type;
* only the mapped approver roles may decide it (admin has no bypass);
* requester and approver must be different identities (repository-enforced);
* the single-use token only authorizes the exact input binding it was
  minted for — any input change burns the token (fail closed, audited).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from uuid import uuid4

from dmt_api.identity.roles import APPROVER_ROLES, REQUESTER_ROLES, Role
from dmt_api.persistence import UnitOfWork
from dmt_api.persistence.domain import ApprovalRequest, ApprovalToken
from dmt_api.persistence.errors import BindingMismatchError


class RoleNotAllowedError(Exception):
    """The identity's roles do not authorize this approval action."""


class InvalidBindingError(Exception):
    """The approval binding does not uniquely identify one tool call."""


@dataclass(frozen=True, slots=True)
class ApprovalBinding:
    """Everything a decision is bound to; hashed into the token contract."""

    input_artifact_hash: str
    policy_version: str
    prompt_version: str
    skill_version: str
    workflow_version: str
    scope: str
    account_id: str = ""
    budget_limit: str = "0"
    valid_from: str = ""
    valid_until: str = ""
    tool_name: str = ""
    agent_type: str = ""
    tool_call_id: str = ""

    def __post_init__(self) -> None:
        # An approval must be bound to exactly one tool call; empty
        # identifiers would let one token authorize arbitrary calls.
        if not self.tool_call_id.strip():
            raise InvalidBindingError("binding requires a non-empty tool_call_id")
        if not self.tool_name.strip():
            raise InvalidBindingError("binding requires a non-empty tool_name")

    def canonical_hash(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class ApprovalService:
    def __init__(self, uow: UnitOfWork, *, now: Callable[[], datetime]) -> None:
        self._uow = uow
        self._now = now

    def create_request(
        self,
        *,
        run_id: str,
        approval_type: str,
        requester_id: str,
        requester_roles: frozenset[Role],
        binding: ApprovalBinding,
        expires_at: datetime,
    ) -> tuple[ApprovalRequest, str]:
        allowed = REQUESTER_ROLES.get(approval_type, frozenset())
        if not (requester_roles & allowed):
            raise RoleNotAllowedError(
                f"roles do not authorize requesting {approval_type!r} approvals"
            )
        return self._uow.approvals.create_request(
            approval_id=_new_id("apr"),
            run_id=run_id,
            approval_type=approval_type,
            requester_id=requester_id,
            input_artifact_hash=binding.input_artifact_hash,
            policy_version=binding.policy_version,
            requested_at=self._now(),
            expires_at=expires_at,
            token_id=_new_id("tok"),
            binding=asdict(binding),
            binding_hash=binding.canonical_hash(),
            tool_name=binding.tool_name,
            agent_type=binding.agent_type,
        )

    def decide(
        self,
        *,
        approval_id: str,
        approver_id: str,
        approver_roles: frozenset[Role],
        decision: str,
    ) -> ApprovalRequest:
        request = self._uow.approvals.get(approval_id)
        if request is None:
            # let the repository raise the canonical NotFoundError
            return self._uow.approvals.decide(
                approval_id=approval_id,
                decision_id=_new_id("dec"),
                approver_id=approver_id,
                decision=decision,
                decided_at=self._now(),
            )
        allowed = APPROVER_ROLES.get(request.approval_type, frozenset())
        if not (approver_roles & allowed):
            raise RoleNotAllowedError(
                f"roles do not authorize deciding {request.approval_type!r} approvals"
            )
        return self._uow.approvals.decide(
            approval_id=approval_id,
            decision_id=_new_id("dec"),
            approver_id=approver_id,
            decision=decision,
            decided_at=self._now(),
        )

    def consume(
        self, token_plaintext: str, *, consumed_by: str, binding: ApprovalBinding
    ) -> ApprovalToken:
        """Atomically consume the token for exactly this input binding.

        On a binding mismatch the token revocation is committed before the
        typed error propagates, so the burned token survives the rollback of
        the failed operation (fail closed).
        """
        try:
            return self._uow.approvals.consume_token_bound(
                token_plaintext,
                consumed_by=consumed_by,
                now=self._now(),
                expected_binding_hash=binding.canonical_hash(),
                expected_tool_name=binding.tool_name,
                expected_agent_type=binding.agent_type,
            )
        except BindingMismatchError:
            self._uow.commit()
            raise

    def revoke(self, approval_id: str, *, actor_id: str, reason: str) -> ApprovalRequest:
        return self._uow.approvals.revoke_request(
            approval_id, actor_id=actor_id, reason=reason, now=self._now()
        )
