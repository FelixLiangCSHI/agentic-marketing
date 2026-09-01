"""Operation-ledger tests: unique logical write per
(tenant, channel, account, idempotency_key, input_hash), same-key-different-
hash rejection, and monotonic re-entrant status transitions."""

from __future__ import annotations

import pytest

from campaign_activation import (
    DuplicateOperationError,
    FakeOperationStore,
    IllegalTransitionError,
)

from builders import FAKE_NOW, make_key

HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


class TestBegin:
    def test_begin_creates_intent_record(self) -> None:
        store = FakeOperationStore()
        record, created = store.begin(
            key=make_key(), input_hash=HASH_A, approval_id="appr-1", now=FAKE_NOW
        )
        assert created is True
        assert record.status == "INTENT"
        assert record.input_hash == HASH_A
        assert record.approval_id == "appr-1"
        assert record.external_object_id is None

    def test_begin_same_key_same_hash_is_reentrant(self) -> None:
        store = FakeOperationStore()
        first, _ = store.begin(
            key=make_key(), input_hash=HASH_A, approval_id="appr-1", now=FAKE_NOW
        )
        second, created = store.begin(
            key=make_key(), input_hash=HASH_A, approval_id="appr-1", now=FAKE_NOW
        )
        assert created is False
        assert second == first

    def test_begin_same_key_different_hash_rejected(self) -> None:
        store = FakeOperationStore()
        store.begin(key=make_key(), input_hash=HASH_A, approval_id="appr-1", now=FAKE_NOW)
        with pytest.raises(DuplicateOperationError):
            store.begin(
                key=make_key(), input_hash=HASH_B, approval_id="appr-2", now=FAKE_NOW
            )

    def test_different_tenants_do_not_collide(self) -> None:
        store = FakeOperationStore()
        store.begin(key=make_key(), input_hash=HASH_A, approval_id="appr-1", now=FAKE_NOW)
        other = make_key().model_copy(update={"tenant_id": "tenant-other"})
        _, created = store.begin(
            key=other, input_hash=HASH_B, approval_id="appr-2", now=FAKE_NOW
        )
        assert created is True


class TestTransitions:
    def _begun(self) -> FakeOperationStore:
        store = FakeOperationStore()
        store.begin(key=make_key(), input_hash=HASH_A, approval_id="appr-1", now=FAKE_NOW)
        return store

    def test_intent_to_succeeded_records_external_id(self) -> None:
        store = self._begun()
        record = store.transition(
            key=make_key(), to="SUCCEEDED", now=FAKE_NOW, external_object_id="ext-1"
        )
        assert record.status == "SUCCEEDED"
        assert record.external_object_id == "ext-1"

    def test_unknown_then_reconciled(self) -> None:
        store = self._begun()
        store.transition(key=make_key(), to="UNKNOWN", now=FAKE_NOW)
        record = store.transition(
            key=make_key(), to="RECONCILED", now=FAKE_NOW, external_object_id="ext-1"
        )
        assert record.status == "RECONCILED"
        assert record.external_object_id == "ext-1"

    def test_terminal_states_are_monotonic(self) -> None:
        store = self._begun()
        store.transition(key=make_key(), to="SUCCEEDED", now=FAKE_NOW, external_object_id="e")
        for target in ("INTENT", "UNKNOWN", "FAILED"):
            with pytest.raises(IllegalTransitionError):
                store.transition(key=make_key(), to=target, now=FAKE_NOW)

    def test_unknown_cannot_jump_to_failed(self) -> None:
        # UNKNOWN must reconcile first; it never becomes FAILED directly.
        store = self._begun()
        store.transition(key=make_key(), to="UNKNOWN", now=FAKE_NOW)
        with pytest.raises(IllegalTransitionError):
            store.transition(key=make_key(), to="FAILED", now=FAKE_NOW)

    def test_transition_is_idempotent_for_same_state(self) -> None:
        store = self._begun()
        store.transition(key=make_key(), to="SUCCEEDED", now=FAKE_NOW, external_object_id="e")
        record = store.transition(
            key=make_key(), to="SUCCEEDED", now=FAKE_NOW, external_object_id="e"
        )
        assert record.status == "SUCCEEDED"

    def test_waiting_reconciliation_reachable_from_unknown_only(self) -> None:
        store = self._begun()
        with pytest.raises(IllegalTransitionError):
            store.transition(key=make_key(), to="WAITING_RECONCILIATION", now=FAKE_NOW)
        store.transition(key=make_key(), to="UNKNOWN", now=FAKE_NOW)
        record = store.transition(key=make_key(), to="WAITING_RECONCILIATION", now=FAKE_NOW)
        assert record.status == "WAITING_RECONCILIATION"

    def test_unknown_key_transition_rejected(self) -> None:
        store = FakeOperationStore()
        with pytest.raises(KeyError):
            store.transition(key=make_key(), to="SUCCEEDED", now=FAKE_NOW)
