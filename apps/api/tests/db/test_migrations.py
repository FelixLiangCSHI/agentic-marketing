"""Migration roundtrip: empty -> head -> down one -> head.

Runs against a dedicated database so schema manipulation never disturbs the
data-level integration tests.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import URL, Engine, create_engine, inspect, make_url, text

from alembic import command

from dmt_api.persistence.testing import make_alembic_config

MIGRATION_DB = "dmt_migration_test"

EXPECTED_TABLES = {
    "core": {
        "runs",
        "run_events",
        "tasks",
        "task_dependencies",
        "workflow_journal",
        "outbox",
    },
    "approval": {"requests", "decisions", "tokens"},
    "audit": {"events"},
    "campaign": {
        "connector_operations",
        "compensation_tasks",
        "raw_channel_metrics",
        "normalized_metrics",
    },
}


def _admin_url(url: str) -> URL:
    return make_url(url).set(database="postgres")


def _migration_url(url: str) -> str:
    return make_url(url).set(database=MIGRATION_DB).render_as_string(hide_password=False)


@pytest.fixture()
def migration_engine(database_url: str) -> Iterator[Engine]:
    admin = create_engine(_admin_url(database_url), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {MIGRATION_DB} (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {MIGRATION_DB}"))
    engine = create_engine(_migration_url(database_url))
    yield engine
    engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {MIGRATION_DB} (FORCE)"))
    admin.dispose()


def _tables(engine: Engine) -> dict[str, set[str]]:
    inspector = inspect(engine)
    return {
        schema: set(inspector.get_table_names(schema=schema))
        for schema in EXPECTED_TABLES
        if schema in inspector.get_schema_names()
    }


def test_empty_to_head_to_down_one_to_head(migration_engine: Engine, database_url: str) -> None:
    cfg = make_alembic_config(_migration_url(database_url))

    # empty -> head
    command.upgrade(cfg, "head")
    tables = _tables(migration_engine)
    for schema, expected in EXPECTED_TABLES.items():
        assert expected <= tables.get(schema, set()), f"missing tables in {schema}"

    # head -> base (roundtrip through every revision's downgrade)
    command.downgrade(cfg, "base")
    tables_after_down = _tables(migration_engine)
    for schema, expected in EXPECTED_TABLES.items():
        assert not (expected & tables_after_down.get(schema, set())), (
            f"tables still present in {schema} after downgrade"
        )

    # base -> head again
    command.upgrade(cfg, "head")
    tables_again = _tables(migration_engine)
    for schema, expected in EXPECTED_TABLES.items():
        assert expected <= tables_again.get(schema, set())


def test_append_only_triggers_recreated_after_roundtrip(
    migration_engine: Engine, database_url: str
) -> None:
    cfg = make_alembic_config(_migration_url(database_url))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")
    command.upgrade(cfg, "head")
    with migration_engine.connect() as conn:
        count = conn.execute(
            text(
                "SELECT count(*) FROM information_schema.triggers "
                "WHERE trigger_name IN ('run_events_append_only', 'audit_events_append_only')"
            )
        ).scalar_one()
    # BEFORE UPDATE OR DELETE shows as two rows per trigger.
    assert count == 4
