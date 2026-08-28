"""Persistence layer for the Control API (Phase 01 / Subphase 03).

Authoritative PostgreSQL model for Run, Run Event, Task DAG, Workflow
Journal, Approval, Audit, and the Transactional Outbox.

Design rules (see phase prompt and ADRs):

* Agents and API handlers never see SQLAlchemy sessions or raw SQL —
  repositories return typed, frozen domain objects only.
* ``core.run_events`` and ``audit.events`` are append-only (database
  triggers reject UPDATE/DELETE).
* Every state change writes its run event, audit record, and outbox
  message in the same transaction via :class:`UnitOfWork`.
* Approval tokens are stored as SHA-256 hashes with unique constraints
  and consumed by an atomic conditional update.
* Task leasing uses lease owner + expiry + a version column with
  conditional updates so concurrent claims cannot both win.
"""

from __future__ import annotations

from dmt_api.persistence.uow import UnitOfWork, create_session_factory

__all__ = ["UnitOfWork", "create_session_factory"]
