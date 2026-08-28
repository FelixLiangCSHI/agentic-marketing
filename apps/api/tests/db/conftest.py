"""Shared fixtures for PostgreSQL integration tests.

These tests require a local PostgreSQL 16 instance and are skipped when
``DMT_TEST_DATABASE_URL`` is not set. They never connect to DEV/SIT/UAT/PRD;
CI provides an ephemeral ``postgres:16`` service container.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from alembic import command

from dmt_api.persistence.testing import database_url_from_env, make_alembic_config

_ALL_TABLES = (
    "core.run_events",
    "core.task_dependencies",
    "core.tasks",
    "core.workflow_journal",
    "core.outbox",
    "approval.tokens",
    "approval.decisions",
    "approval.requests",
    "audit.events",
    "core.runs",
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if database_url_from_env() is not None:
        return
    skip = pytest.mark.skip(reason="DMT_TEST_DATABASE_URL is not set; PostgreSQL tests skipped")
    db_dir = Path(__file__).parent
    for item in items:
        if db_dir in Path(str(item.fspath)).parents:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def database_url() -> str:
    url = database_url_from_env()
    assert url is not None
    return url


@pytest.fixture(scope="session")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS core CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS approval CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS audit CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()
    command.upgrade(make_alembic_config(database_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(migrated_engine: Engine) -> Iterator[None]:
    with migrated_engine.connect() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(_ALL_TABLES)} CASCADE"))
        conn.commit()
    yield


@pytest.fixture()
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    with Session(migrated_engine) as session:
        yield session
