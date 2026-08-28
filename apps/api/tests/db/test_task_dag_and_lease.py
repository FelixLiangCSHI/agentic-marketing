"""Task DAG cycle prevention and lease-based claiming under concurrency."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine

from dmt_api.persistence.errors import (
    DependencyCycleError,
    IllegalStateTransitionError,
    LeaseConflictError,
)

from tests.db.helpers import NOW, create_run, make_uow


def _create_task(engine: Engine, task_id: str, run_id: str = "run-1") -> None:
    with make_uow(engine) as uow:
        uow.tasks.create(
            task_id=task_id,
            run_id=run_id,
            task_type="demo.step",
            max_attempts=3,
            actor_id="system",
            created_at=NOW,
        )


def test_self_dependency_is_rejected(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _create_task(migrated_engine, "t-1")
    with pytest.raises(DependencyCycleError):
        with make_uow(migrated_engine) as uow:
            uow.tasks.add_dependency("t-1", "t-1")


def test_cycle_is_rejected_at_write_time(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    for task_id in ("t-1", "t-2", "t-3"):
        _create_task(migrated_engine, task_id)
    with make_uow(migrated_engine) as uow:
        uow.tasks.add_dependency("t-2", "t-1")
        uow.tasks.add_dependency("t-3", "t-2")
    with pytest.raises(DependencyCycleError):
        with make_uow(migrated_engine) as uow:
            uow.tasks.add_dependency("t-1", "t-3")
    # no partial dependency row was written
    with make_uow(migrated_engine) as uow:
        assert uow.tasks.dependencies("t-1") == []


def test_cross_run_dependency_is_rejected(migrated_engine: Engine) -> None:
    create_run(migrated_engine, run_id="run-1")
    create_run(migrated_engine, run_id="run-2")
    _create_task(migrated_engine, "t-1", run_id="run-1")
    _create_task(migrated_engine, "t-2", run_id="run-2")
    with pytest.raises(DependencyCycleError):
        with make_uow(migrated_engine) as uow:
            uow.tasks.add_dependency("t-1", "t-2")
    with make_uow(migrated_engine) as uow:
        assert uow.tasks.dependencies("t-1") == []


def test_task_status_machine_rejects_illegal_jumps(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _create_task(migrated_engine, "t-1")
    with pytest.raises(IllegalStateTransitionError):
        with make_uow(migrated_engine) as uow:
            uow.tasks.transition("t-1", "SUCCEEDED", actor_id="system", occurred_at=NOW)


def test_claim_requires_ready_status(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _create_task(migrated_engine, "t-1")
    with pytest.raises(LeaseConflictError):
        with make_uow(migrated_engine) as uow:
            uow.tasks.claim(
                "t-1", owner_id="worker-a", now=NOW, lease_seconds=30, expected_version=0
            )


def test_claim_sets_lease_and_bumps_version(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _create_task(migrated_engine, "t-1")
    with make_uow(migrated_engine) as uow:
        uow.tasks.transition("t-1", "READY", actor_id="system", occurred_at=NOW)
    with make_uow(migrated_engine) as uow:
        task = uow.tasks.claim(
            "t-1", owner_id="worker-a", now=NOW, lease_seconds=30, expected_version=1
        )
    assert task.status == "LEASED"
    assert task.lease_owner == "worker-a"
    assert task.attempt == 1
    assert task.lease_expires_at is not None
    assert task.version == 2


def test_concurrent_claims_only_one_wins(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    _create_task(migrated_engine, "t-1")
    with make_uow(migrated_engine) as uow:
        ready = uow.tasks.transition("t-1", "READY", actor_id="system", occurred_at=NOW)

    def attempt(owner: str) -> str | None:
        try:
            with make_uow(migrated_engine) as uow:
                uow.tasks.claim(
                    "t-1",
                    owner_id=owner,
                    now=NOW,
                    lease_seconds=30,
                    expected_version=ready.version,
                )
            return owner
        except LeaseConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["worker-a", "worker-b"]))

    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    with make_uow(migrated_engine) as uow:
        task = uow.tasks.get("t-1")
        assert task is not None
        assert task.lease_owner == winners[0]
        assert task.status == "LEASED"


def test_expired_lease_can_be_reclaimed_by_other_worker(migrated_engine: Engine) -> None:
    from datetime import timedelta

    create_run(migrated_engine)
    _create_task(migrated_engine, "t-1")
    with make_uow(migrated_engine) as uow:
        uow.tasks.transition("t-1", "READY", actor_id="system", occurred_at=NOW)
    with make_uow(migrated_engine) as uow:
        leased = uow.tasks.claim(
            "t-1", owner_id="worker-a", now=NOW, lease_seconds=30, expected_version=1
        )
    later = NOW + timedelta(seconds=120)
    with make_uow(migrated_engine) as uow:
        task = uow.tasks.reclaim_expired(
            "t-1", owner_id="worker-b", now=later, lease_seconds=30, expected_version=leased.version
        )
    assert task.lease_owner == "worker-b"
    assert task.attempt == 2
