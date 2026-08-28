"""Security tests for the ApprovalService (requires PostgreSQL).

Covers role routing, self-approval, token lifecycle (single-use, expiry,
revocation, reuse), input-change invalidation, and audit fail-closed.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import Engine

from dmt_api.approval_service import (
    ApprovalBinding,
    ApprovalService,
    BindingMismatchError,
    RoleNotAllowedError,
)
from dmt_api.identity.roles import Role
from dmt_api.persistence.errors import (
    SeparationOfDutiesError,
    TokenConsumptionError,
)

from tests.db.helpers import create_run, make_uow

_NOW = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
_LATER = _NOW + timedelta(hours=1)

_MEDICAL = frozenset({Role.MEDICAL_REVIEWER})
_CREATOR = frozenset({Role.CONTENT_CREATOR})


def binding(**overrides: Any) -> ApprovalBinding:
    values: dict[str, Any] = {
        "input_artifact_hash": "a" * 64,
        "policy_version": "1.0.0",
        "prompt_version": "1.0.0",
        "skill_version": "1.0.0",
        "workflow_version": "1.0.0",
        "scope": "content/post-1",
        "account_id": "acct-sandbox-1",
        "budget_limit": "0",
        "valid_from": _NOW.isoformat(),
        "valid_until": _LATER.isoformat(),
        "tool_name": "content.publish",
        "agent_type": "content",
    }
    values.update(overrides)
    return ApprovalBinding(**values)


def create_request(
    engine: Engine,
    *,
    run_id: str = "run-1",
    approval_type: str = "content_publication",
    requester_id: str = "alice",
    requester_roles: frozenset[Role] = _CREATOR,
    the_binding: ApprovalBinding | None = None,
) -> tuple[str, str]:
    create_run(engine, run_id=run_id, requester_id=requester_id)
    with make_uow(engine) as uow:
        request, token = ApprovalService(uow, now=lambda: _NOW).create_request(
            run_id=run_id,
            approval_type=approval_type,
            requester_id=requester_id,
            requester_roles=requester_roles,
            binding=the_binding or binding(),
            expires_at=_LATER,
        )
        return request.approval_id, token


def decide(
    engine: Engine,
    approval_id: str,
    *,
    approver_id: str = "mona",
    approver_roles: frozenset[Role] = _MEDICAL,
    decision: str = "APPROVED",
    now: datetime = _NOW,
) -> Any:
    with make_uow(engine) as uow:
        return ApprovalService(uow, now=lambda: now).decide(
            approval_id=approval_id,
            approver_id=approver_id,
            approver_roles=approver_roles,
            decision=decision,
        )


def consume(
    engine: Engine,
    token: str,
    *,
    consumed_by: str = "worker-1",
    the_binding: ApprovalBinding | None = None,
    now: datetime = _NOW,
) -> Any:
    with make_uow(engine) as uow:
        return ApprovalService(uow, now=lambda: now).consume(
            token, consumed_by=consumed_by, binding=the_binding or binding()
        )


class TestRoleRouting:
    def test_requester_without_creator_or_operator_role_cannot_request(
        self, migrated_engine: Engine
    ) -> None:
        create_run(migrated_engine)
        with make_uow(migrated_engine) as uow:
            with pytest.raises(RoleNotAllowedError):
                ApprovalService(uow, now=lambda: _NOW).create_request(
                    run_id="run-1",
                    approval_type="content_publication",
                    requester_id="carol",
                    requester_roles=frozenset({Role.AUDITOR}),
                    binding=binding(),
                    expires_at=_LATER,
                )

    def test_content_publication_requires_medical_reviewer(
        self, migrated_engine: Engine
    ) -> None:
        approval_id, _ = create_request(migrated_engine)
        with pytest.raises(RoleNotAllowedError):
            decide(
                migrated_engine,
                approval_id,
                approver_id="oscar",
                approver_roles=frozenset({Role.CAMPAIGN_APPROVER}),
            )

    def test_campaign_activation_requires_campaign_approver(
        self, migrated_engine: Engine
    ) -> None:
        approval_id, _ = create_request(
            migrated_engine,
            approval_type="campaign_activation",
            requester_roles=frozenset({Role.CAMPAIGN_OPERATOR}),
        )
        with pytest.raises(RoleNotAllowedError):
            decide(migrated_engine, approval_id)  # medical reviewer must not approve

    def test_admin_role_cannot_bypass_approver_roles(
        self, migrated_engine: Engine
    ) -> None:
        approval_id, _ = create_request(migrated_engine)
        with pytest.raises(RoleNotAllowedError):
            decide(
                migrated_engine,
                approval_id,
                approver_id="root",
                approver_roles=frozenset({Role.ADMIN}),
            )

    def test_self_approval_is_denied_even_with_the_right_role(
        self, migrated_engine: Engine
    ) -> None:
        approval_id, _ = create_request(migrated_engine, requester_id="alice")
        with pytest.raises(SeparationOfDutiesError):
            decide(migrated_engine, approval_id, approver_id="alice")

    def test_correct_role_can_approve(self, migrated_engine: Engine) -> None:
        approval_id, _ = create_request(migrated_engine)
        request = decide(migrated_engine, approval_id)
        assert request.status == "APPROVED"


class TestTokenLifecycle:
    def _approved_token(self, engine: Engine) -> tuple[str, str]:
        approval_id, token = create_request(engine)
        decide(engine, approval_id)
        return approval_id, token

    def test_token_without_approval_decision_cannot_be_consumed(
        self, migrated_engine: Engine
    ) -> None:
        _, token = create_request(migrated_engine)
        with pytest.raises(TokenConsumptionError):
            consume(migrated_engine, token)

    def test_token_is_single_use(self, migrated_engine: Engine) -> None:
        _, token = self._approved_token(migrated_engine)
        consume(migrated_engine, token, consumed_by="worker-1")
        with pytest.raises(TokenConsumptionError):
            consume(migrated_engine, token, consumed_by="worker-2")

    def test_expired_token_is_rejected(self, migrated_engine: Engine) -> None:
        _, token = self._approved_token(migrated_engine)
        with pytest.raises(TokenConsumptionError):
            consume(migrated_engine, token, now=_LATER + timedelta(seconds=1))

    def test_revoked_token_is_rejected(self, migrated_engine: Engine) -> None:
        approval_id, token = self._approved_token(migrated_engine)
        with make_uow(migrated_engine) as uow:
            ApprovalService(uow, now=lambda: _NOW).revoke(
                approval_id, actor_id="root", reason="incident"
            )
        with pytest.raises(TokenConsumptionError):
            consume(migrated_engine, token)

    def test_rejected_request_token_cannot_be_consumed(
        self, migrated_engine: Engine
    ) -> None:
        approval_id, token = create_request(migrated_engine)
        decide(migrated_engine, approval_id, decision="REJECTED")
        with pytest.raises(TokenConsumptionError):
            consume(migrated_engine, token)

    def test_input_change_invalidates_the_old_token(
        self, migrated_engine: Engine
    ) -> None:
        """A token minted for one artifact must not authorize another."""
        _, token = self._approved_token(migrated_engine)
        changed = binding(input_artifact_hash="b" * 64)
        with pytest.raises(BindingMismatchError):
            consume(migrated_engine, token, the_binding=changed)
        # the failed attempt burned the token: even the original input is rejected
        with pytest.raises(TokenConsumptionError):
            consume(migrated_engine, token)

    def test_tool_or_agent_change_invalidates_the_old_token(
        self, migrated_engine: Engine
    ) -> None:
        _, token = self._approved_token(migrated_engine)
        changed = binding(tool_name="content.schedule")
        with pytest.raises(BindingMismatchError):
            consume(migrated_engine, token, the_binding=changed)
        with pytest.raises(TokenConsumptionError):
            consume(migrated_engine, token)


class TestConcurrentConsumption:
    def test_exactly_one_concurrent_consumer_wins(
        self, migrated_engine: Engine
    ) -> None:
        approval_id, token = create_request(migrated_engine)
        decide(migrated_engine, approval_id)

        def attempt(worker: str) -> bool:
            try:
                consume(migrated_engine, token, consumed_by=worker)
                return True
            except TokenConsumptionError:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, [f"worker-{i}" for i in range(8)]))
        assert results.count(True) == 1


class TestAuditFailClosed:
    def test_decision_is_rolled_back_when_audit_write_fails(
        self, migrated_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        approval_id, _ = create_request(migrated_engine)

        from dmt_api.persistence import repositories

        def broken_audit(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("audit sink unavailable")

        monkeypatch.setattr(
            repositories._BaseRepository, "_append_audit", broken_audit
        )
        with pytest.raises(RuntimeError):
            decide(migrated_engine, approval_id)
        monkeypatch.undo()

        with make_uow(migrated_engine) as uow:
            request = uow.approvals.get(approval_id)
            assert request is not None
            assert request.status == "PENDING"
