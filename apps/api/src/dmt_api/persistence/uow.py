"""Unit of Work: one transaction per business operation.

State changes plus their run events, audit records, and outbox messages are
committed atomically. On any error the whole transaction rolls back, so no
partial state (e.g. a status change without its audit trail) can persist.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from dmt_api.persistence.repositories import (
    ApprovalRepository,
    AuditRepository,
    JournalRepository,
    OutboxRepository,
    RunEventRepository,
    RunRepository,
    TaskRepository,
)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


class UnitOfWork:
    """Context manager owning a single database transaction.

    Repositories are only reachable through an active unit of work; the
    session itself is never exposed to callers.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        session = self._session_factory()
        self._session = session
        self.runs = RunRepository(session)
        self.run_events = RunEventRepository(session)
        self.tasks = TaskRepository(session)
        self.journal = JournalRepository(session)
        self.approvals = ApprovalRepository(session)
        self.audit = AuditRepository(session)
        self.outbox = OutboxRepository(session)
        return self

    def commit(self) -> None:
        """Explicitly commit the current transaction.

        Used for fail-closed security events (e.g. burning a token on a
        binding mismatch) that must persist even though the operation itself
        finishes by raising a typed error.
        """
        session = self._session
        assert session is not None
        session.commit()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._session
        assert session is not None
        try:
            if exc_type is None:
                session.commit()
            else:
                session.rollback()
        finally:
            session.close()
            self._session = None
