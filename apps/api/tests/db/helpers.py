"""Shared helpers for the PostgreSQL integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine

from dmt_api.persistence import UnitOfWork, create_session_factory
from dmt_api.persistence.domain import Run

NOW = datetime(2026, 8, 28, 0, 0, 0, tzinfo=UTC)


def make_uow(engine: Engine) -> UnitOfWork:
    return UnitOfWork(create_session_factory(engine))


def create_run(engine: Engine, run_id: str = "run-1", requester_id: str = "alice") -> Run:
    with make_uow(engine) as uow:
        return uow.runs.create(
            run_id=run_id,
            parent_run_id=None,
            agent_type="content",
            workflow_name="wf.demo",
            workflow_version="1.0.0",
            tenant="tenant-a",
            business_unit="bu-a",
            requester_id=requester_id,
            environment="local",
            actor_id=requester_id,
            created_at=NOW,
        )
