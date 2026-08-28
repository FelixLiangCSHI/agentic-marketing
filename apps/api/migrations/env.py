"""Alembic environment: offline and online migration entry points."""

from __future__ import annotations

import os

from sqlalchemy import engine_from_config, pool

from alembic import context

from dmt_api.persistence.orm import Base

config = context.config

target_metadata = Base.metadata

_url = config.get_main_option("sqlalchemy.url") or os.environ.get("DMT_TEST_DATABASE_URL", "")
if not _url:
    raise RuntimeError(
        "No database URL configured. Set sqlalchemy.url programmatically or "
        "export DMT_TEST_DATABASE_URL (local/CI throwaway database only)."
    )
config.set_main_option("sqlalchemy.url", _url)


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    if type_ == "schema":
        return name in {"core", "approval", "audit"}
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_name=include_name,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
