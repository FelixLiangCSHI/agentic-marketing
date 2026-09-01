"""Application-scoped SQLAlchemy engine lifecycle helpers."""

from __future__ import annotations

from threading import Lock

from fastapi import FastAPI
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from dmt_api.persistence import create_session_factory
from dmt_api.settings import Settings


def configure_database(app: FastAPI, database_url: str | None) -> None:
    app.state.database_url = database_url
    app.state.database_engine = None
    app.state.session_factory = None
    app.state.database_engine_error = None
    app.state.database_init_lock = Lock()


def _engine_kwargs(database_url: str, settings: Settings) -> dict[str, object]:
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if not database_url.startswith("sqlite:"):
        kwargs.update(
            {
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
                "pool_timeout": settings.database_pool_timeout_seconds,
            }
        )
    return kwargs


def initialize_database(app: FastAPI) -> Engine | None:
    database_url = getattr(app.state, "database_url", None)
    if not database_url:
        return None
    engine = getattr(app.state, "database_engine", None)
    if isinstance(engine, Engine):
        return engine
    lock = getattr(app.state, "database_init_lock", None)
    if lock is None:
        lock = Lock()
        app.state.database_init_lock = lock
    with lock:
        engine = getattr(app.state, "database_engine", None)
        if isinstance(engine, Engine):
            return engine
        try:
            settings = Settings.from_env()
            engine = create_engine(database_url, **_engine_kwargs(database_url, settings))
        except SQLAlchemyError as exc:
            app.state.database_engine_error = exc
            return None
        app.state.database_engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.database_engine_error = None
        return engine


def get_engine(app: FastAPI) -> Engine | None:
    return initialize_database(app)


def get_session_factory(app: FastAPI) -> sessionmaker[Session] | None:
    initialize_database(app)
    factory = getattr(app.state, "session_factory", None)
    if isinstance(factory, sessionmaker):
        return factory
    return None


def dispose_database(app: FastAPI) -> None:
    engine = getattr(app.state, "database_engine", None)
    if isinstance(engine, Engine):
        engine.dispose()
    app.state.database_engine = None
    app.state.session_factory = None
