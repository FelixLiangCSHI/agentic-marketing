"""Test-support helpers for the persistence layer.

Only ever used with local/CI throwaway PostgreSQL instances. Real database
credentials are never present here or in configuration — only the
``DMT_TEST_DATABASE_URL`` environment variable injected by the developer or
the CI service container.
"""

from __future__ import annotations

import os
from pathlib import Path

from alembic.config import Config

_API_ROOT = Path(__file__).resolve().parents[3]


def database_url_from_env() -> str | None:
    """Return the local/CI test database URL, or ``None`` when unset."""
    return os.environ.get("DMT_TEST_DATABASE_URL") or None


def make_alembic_config(url: str) -> Config:
    cfg = Config(str(_API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg
