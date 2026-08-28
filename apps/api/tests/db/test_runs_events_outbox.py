"""Run state machine, append-only events, and transactional guarantees."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DatabaseError

from dmt_api.persistence.errors import IllegalStateTransitionError

from tests.db.helpers import NOW, create_run, make_uow


def test_create_run_writes_event_audit_and_outbox(migrated_engine: Engine) -> None:
    run = create_run(migrated_engine)
    assert run.status == "CREATED"
    assert run.version == 0

    with make_uow(migrated_engine) as uow:
        events = uow.run_events.for_run("run-1")
        audit = uow.audit.for_run("run-1")
        outbox = uow.outbox.pending()
    assert [e.event_type for e in events] == ["RUN_STATUS_CHANGED"]
    assert events[0].sequence == 0
    assert len(audit) == 1
    assert audit[0].action == "run.created"
    assert len(outbox) == 1


def test_legal_transition_appends_event_with_next_sequence(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    with make_uow(migrated_engine) as uow:
        run = uow.runs.transition("run-1", "PLANNING", actor_id="system", occurred_at=NOW)
        assert run.status == "PLANNING"
        assert run.version == 1
    with make_uow(migrated_engine) as uow:
        events = uow.run_events.for_run("run-1")
    assert [e.sequence for e in events] == [0, 1]
    assert events[1].payload["to_status"] == "PLANNING"


def test_concurrent_run_event_appends_have_unique_sequences(
    migrated_engine: Engine,
) -> None:
    create_run(migrated_engine)

    def create_task(task_id: str) -> None:
        with make_uow(migrated_engine) as uow:
            uow.tasks.create(
                task_id=task_id,
                run_id="run-1",
                task_type="demo.step",
                max_attempts=3,
                actor_id="system",
                created_at=NOW,
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(create_task, [f"t-{i}" for i in range(8)]))

    with make_uow(migrated_engine) as uow:
        events = uow.run_events.for_run("run-1")
    assert [event.sequence for event in events] == list(range(9))


@pytest.mark.parametrize(
    ("path", "bad_target"),
    [
        (["PLANNING", "RUNNING", "SUCCEEDED"], "RUNNING"),  # terminal
        (["PLANNING", "RUNNING", "FAILED"], "SUCCEEDED"),  # terminal
        ([], "SUCCEEDED"),  # CREATED cannot jump to SUCCEEDED
        (["PLANNING"], "COMPENSATED"),
        (["PLANNING", "RUNNING", "CANCELLED"], "RUNNING"),
    ],
)
def test_illegal_transitions_are_rejected(
    migrated_engine: Engine, path: list[str], bad_target: str
) -> None:
    create_run(migrated_engine)
    for step in path:
        with make_uow(migrated_engine) as uow:
            uow.runs.transition("run-1", step, actor_id="system", occurred_at=NOW)
    with pytest.raises(IllegalStateTransitionError):
        with make_uow(migrated_engine) as uow:
            uow.runs.transition("run-1", bad_target, actor_id="system", occurred_at=NOW)
    # nothing was persisted for the illegal attempt
    with make_uow(migrated_engine) as uow:
        events = uow.run_events.for_run("run-1")
    assert len(events) == 1 + len(path)


def test_failed_transition_rolls_back_event_audit_and_outbox(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    with make_uow(migrated_engine) as uow:
        before_outbox = len(uow.outbox.pending())
        before_audit = len(uow.audit.for_run("run-1"))
    with pytest.raises(IllegalStateTransitionError):
        with make_uow(migrated_engine) as uow:
            uow.runs.transition("run-1", "COMPENSATED", actor_id="system", occurred_at=NOW)
    with make_uow(migrated_engine) as uow:
        assert len(uow.outbox.pending()) == before_outbox
        assert len(uow.audit.for_run("run-1")) == before_audit


def test_uow_rollback_discards_all_writes(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    with pytest.raises(RuntimeError, match="boom"):
        with make_uow(migrated_engine) as uow:
            uow.runs.transition("run-1", "PLANNING", actor_id="system", occurred_at=NOW)
            raise RuntimeError("boom")
    with make_uow(migrated_engine) as uow:
        run = uow.runs.get("run-1")
        assert run is not None
        assert run.status == "CREATED"
        assert len(uow.run_events.for_run("run-1")) == 1


def test_run_events_are_append_only(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    with migrated_engine.connect() as conn:
        with pytest.raises(DatabaseError, match="append-only"):
            conn.execute(text("UPDATE core.run_events SET sequence = 99"))
        conn.rollback()
        with pytest.raises(DatabaseError, match="append-only"):
            conn.execute(text("DELETE FROM core.run_events"))
        conn.rollback()


def test_audit_events_are_append_only(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    with migrated_engine.connect() as conn:
        with pytest.raises(DatabaseError, match="append-only"):
            conn.execute(text("UPDATE audit.events SET action = 'tampered'"))
        conn.rollback()
        with pytest.raises(DatabaseError, match="append-only"):
            conn.execute(text("DELETE FROM audit.events"))
        conn.rollback()


def test_outbox_mark_dispatched(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    with make_uow(migrated_engine) as uow:
        pending = uow.outbox.pending()
        assert len(pending) == 1
        uow.outbox.mark_dispatched(pending[0].outbox_id, dispatched_at=NOW + timedelta(seconds=1))
    with make_uow(migrated_engine) as uow:
        assert uow.outbox.pending() == []


def test_workflow_journal_appends_in_sequence(migrated_engine: Engine) -> None:
    create_run(migrated_engine)
    with make_uow(migrated_engine) as uow:
        uow.journal.append(
            journal_id="j-1", run_id="run-1", node_name="plan", payload={"step": 1}, recorded_at=NOW
        )
        uow.journal.append(
            journal_id="j-2", run_id="run-1", node_name="act", payload={"step": 2}, recorded_at=NOW
        )
    with make_uow(migrated_engine) as uow:
        entries = uow.journal.for_run("run-1")
    assert [e.sequence for e in entries] == [0, 1]
    assert [e.node_name for e in entries] == ["plan", "act"]
