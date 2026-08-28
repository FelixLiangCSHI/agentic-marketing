"""Approval requests, decisions, and single-use token consumption."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import Engine

from dmt_api.persistence.domain import ApprovalRequest
from dmt_api.persistence.errors import (
    IllegalStateTransitionError,
    SeparationOfDutiesError,
    TokenConsumptionError,
)

from tests.db.helpers import NOW, create_run, make_uow

HASH = "sha256:" + "a" * 64
EXPIRES = NOW + timedelta(hours=1)


def _create_request(engine: Engine, approval_id: str = "ap-1") -> tuple[ApprovalRequest, str]:
    with make_uow(engine) as uow:
        return uow.approvals.create_request(
            approval_id=approval_id,
            run_id="run-1",
            approval_type="content_publication",
            requester_id="alice",
            input_artifact_hash=HASH,
            policy_version="1.0.0",
            requested_at=NOW,
            expires_at=EXPIRES,
            token_id="tok-1" if approval_id == "ap-1" else f"tok-{approval_id}",
        )


def test_create_request_issues_opaque_token(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    request, token = _create_request(migrated_engine)
    assert request.status == "PENDING"
    assert len(token) >= 32
    assert token not in (HASH,)
    # plaintext token is never stored — only its hash
    with make_uow(migrated_engine) as uow:
        stored = uow.approvals.get_token("tok-1")
        assert stored is not None
        assert token not in stored.token_hash
        assert stored.token_hash.startswith("sha256:")


def test_decide_enforces_separation_of_duties(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _create_request(migrated_engine)
    with pytest.raises(SeparationOfDutiesError):
        with make_uow(migrated_engine) as uow:
            uow.approvals.decide(
                approval_id="ap-1",
                decision_id="d-1",
                approver_id="alice",
                decision="APPROVED",
                decided_at=NOW,
            )


def test_decide_approves_once_and_only_once(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _create_request(migrated_engine)
    with make_uow(migrated_engine) as uow:
        request = uow.approvals.decide(
            approval_id="ap-1",
            decision_id="d-1",
            approver_id="bob",
            decision="APPROVED",
            decided_at=NOW,
        )
    assert request.status == "APPROVED"
    with pytest.raises(IllegalStateTransitionError):
        with make_uow(migrated_engine) as uow:
            uow.approvals.decide(
                approval_id="ap-1",
                decision_id="d-2",
                approver_id="carol",
                decision="REJECTED",
                decided_at=NOW,
            )


def test_token_double_consumption_is_rejected(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _, token = _create_request(migrated_engine)
    with make_uow(migrated_engine) as uow:
        consumed = uow.approvals.consume_token(token, consumed_by="worker-a", now=NOW)
    assert consumed.consumed_by == "worker-a"
    with pytest.raises(TokenConsumptionError):
        with make_uow(migrated_engine) as uow:
            uow.approvals.consume_token(token, consumed_by="worker-b", now=NOW)


def test_unknown_token_is_rejected(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _create_request(migrated_engine)
    with pytest.raises(TokenConsumptionError):
        with make_uow(migrated_engine) as uow:
            uow.approvals.consume_token("not-a-real-token", consumed_by="worker-a", now=NOW)


def test_expired_token_is_rejected(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _, token = _create_request(migrated_engine)
    with pytest.raises(TokenConsumptionError):
        with make_uow(migrated_engine) as uow:
            uow.approvals.consume_token(
                token, consumed_by="worker-a", now=EXPIRES + timedelta(seconds=1)
            )


def test_concurrent_token_consumption_only_one_wins(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _, token = _create_request(migrated_engine)

    def attempt(consumer: str) -> str | None:
        try:
            with make_uow(migrated_engine) as uow:
                uow.approvals.consume_token(token, consumed_by=consumer, now=NOW)
            return consumer
        except TokenConsumptionError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["worker-a", "worker-b"]))

    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    with make_uow(migrated_engine) as uow:
        stored = uow.approvals.get_token("tok-1")
        assert stored is not None
        assert stored.consumed_by == winners[0]
