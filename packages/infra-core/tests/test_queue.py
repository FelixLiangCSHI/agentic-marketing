"""Queue security/recovery tests: at-least-once with zero duplicate side effects.

RED-first: duplicate delivery, poison messages, worker crash (lease expiry),
cancellation, heartbeat, and DLQ replay.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from infra_core.clock import FakeClock
from infra_core.queue import (
    FakeQueueClient,
    LeaseExpiredError,
    Message,
    RetryPolicy,
)

_T0 = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)


def make_queue(
    *,
    max_attempts: int = 3,
    lease_seconds: int = 30,
) -> tuple[FakeQueueClient, FakeClock]:
    clock = FakeClock(_T0)
    queue = FakeQueueClient(
        clock=clock,
        retry_policy=RetryPolicy(
            max_attempts=max_attempts,
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
            jitter_ratio=0.1,
        ),
        lease_seconds=lease_seconds,
    )
    return queue, clock


class TestIdempotentEnqueue:
    def test_100_duplicate_enqueues_yield_one_message(self) -> None:
        queue, _ = make_queue()
        for _ in range(100):
            queue.enqueue("tasks", {"task_id": "t-1"}, idempotency_key="task-t-1")
        assert queue.pending_count("tasks") == 1

    def test_duplicate_enqueue_after_completion_is_still_deduplicated(self) -> None:
        queue, _ = make_queue()
        queue.enqueue("tasks", {"task_id": "t-1"}, idempotency_key="task-t-1")
        message = queue.receive("tasks", worker_id="w1")
        assert message is not None
        queue.ack(message)
        queue.enqueue("tasks", {"task_id": "t-1"}, idempotency_key="task-t-1")
        assert queue.pending_count("tasks") == 0

    def test_different_idempotency_keys_are_independent(self) -> None:
        queue, _ = make_queue()
        queue.enqueue("tasks", {"task_id": "t-1"}, idempotency_key="k1")
        queue.enqueue("tasks", {"task_id": "t-2"}, idempotency_key="k2")
        assert queue.pending_count("tasks") == 2


class TestLeaseAndCrashRecovery:
    def test_message_is_invisible_while_leased(self) -> None:
        queue, _ = make_queue()
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        first = queue.receive("tasks", worker_id="w1")
        assert first is not None
        assert queue.receive("tasks", worker_id="w2") is None

    def test_crashed_worker_lease_expires_and_message_is_redelivered(self) -> None:
        queue, clock = make_queue(lease_seconds=30)
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        first = queue.receive("tasks", worker_id="w1")
        assert first is not None
        clock.advance(timedelta(seconds=31))
        second = queue.receive("tasks", worker_id="w2")
        assert second is not None
        assert second.payload == {"n": 1}
        assert second.attempt == first.attempt + 1

    def test_heartbeat_extends_the_lease(self) -> None:
        queue, clock = make_queue(lease_seconds=30)
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        message = queue.receive("tasks", worker_id="w1")
        assert message is not None
        clock.advance(timedelta(seconds=25))
        queue.heartbeat(message)
        clock.advance(timedelta(seconds=25))
        assert queue.receive("tasks", worker_id="w2") is None
        queue.ack(message)

    def test_ack_after_lease_expiry_is_rejected(self) -> None:
        """A zombie worker must not complete work someone else now owns."""
        queue, clock = make_queue(lease_seconds=30)
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        message = queue.receive("tasks", worker_id="w1")
        assert message is not None
        clock.advance(timedelta(seconds=31))
        redelivered = queue.receive("tasks", worker_id="w2")
        assert redelivered is not None
        with pytest.raises(LeaseExpiredError):
            queue.ack(message)

    def test_heartbeat_after_lease_expiry_is_rejected(self) -> None:
        queue, clock = make_queue(lease_seconds=30)
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        message = queue.receive("tasks", worker_id="w1")
        assert message is not None
        clock.advance(timedelta(seconds=31))
        assert queue.receive("tasks", worker_id="w2") is not None
        with pytest.raises(LeaseExpiredError):
            queue.heartbeat(message)


class TestRetryAndDlq:
    def _drain_to_dlq(self, queue: FakeQueueClient, clock: FakeClock) -> None:
        while True:
            clock.advance(timedelta(seconds=120))
            message = queue.receive("tasks", worker_id="w1")
            if message is None:
                break
            queue.nack(message, reason="poison")

    def test_poison_message_lands_in_dlq_after_max_attempts(self) -> None:
        queue, clock = make_queue(max_attempts=3)
        queue.enqueue("tasks", {"bad": True}, idempotency_key="k1")
        self._drain_to_dlq(queue, clock)
        assert queue.pending_count("tasks") == 0
        dead = queue.dlq("tasks")
        assert len(dead) == 1
        assert dead[0].attempt == 3
        assert dead[0].last_error == "poison"

    def test_retry_uses_exponential_backoff_with_jitter(self) -> None:
        queue, clock = make_queue(max_attempts=5)
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        message = queue.receive("tasks", worker_id="w1")
        assert message is not None
        queue.nack(message, reason="transient")
        # not yet visible: backoff for attempt 1 is ~1s
        assert queue.receive("tasks", worker_id="w1") is None
        clock.advance(timedelta(seconds=2))
        second = queue.receive("tasks", worker_id="w1")
        assert second is not None
        queue.nack(second, reason="transient")
        # attempt 2 backoff ~2s (+jitter); 1s later it must still be hidden
        clock.advance(timedelta(seconds=1))
        assert queue.receive("tasks", worker_id="w1") is None

    def test_backoff_is_capped_at_max_delay(self) -> None:
        policy = RetryPolicy(
            max_attempts=99,
            base_delay_seconds=1.0,
            max_delay_seconds=60.0,
            jitter_ratio=0.1,
        )
        assert policy.delay_seconds(attempt=30, salt="x") <= 60.0 * 1.1

    def test_dlq_replay_returns_message_to_the_queue(self) -> None:
        queue, clock = make_queue(max_attempts=2)
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        self._drain_to_dlq(queue, clock)
        assert len(queue.dlq("tasks")) == 1
        queue.replay_dlq("tasks")
        assert queue.dlq("tasks") == []
        clock.advance(timedelta(seconds=120))
        replayed = queue.receive("tasks", worker_id="w1")
        assert replayed is not None
        assert replayed.payload == {"n": 1}
        queue.ack(replayed)


class TestCancellation:
    def test_cancelled_message_is_never_delivered(self) -> None:
        queue, _ = make_queue()
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        queue.cancel("tasks", idempotency_key="k1")
        assert queue.receive("tasks", worker_id="w1") is None

    def test_cancellation_flag_is_visible_to_a_running_worker(self) -> None:
        queue, _ = make_queue()
        queue.enqueue("tasks", {"n": 1}, idempotency_key="k1")
        message = queue.receive("tasks", worker_id="w1")
        assert message is not None
        queue.cancel("tasks", idempotency_key="k1")
        assert queue.is_cancelled(message) is True


class TestAtLeastOnceSideEffects:
    def test_duplicate_deliveries_cause_zero_duplicate_side_effects(self) -> None:
        """Consumer-side idempotency: process each idempotency key once."""
        queue, clock = make_queue(lease_seconds=10)
        for i in range(5):
            queue.enqueue("tasks", {"n": i}, idempotency_key=f"k{i}")
        processed: dict[str, int] = {}
        seen: set[str] = set()

        def handle(message: Message) -> None:
            if message.idempotency_key in seen:
                return  # duplicate delivery: no side effect
            seen.add(message.idempotency_key)
            processed[message.idempotency_key] = processed.get(message.idempotency_key, 0) + 1

        # simulate crashy workers: every message is delivered at least twice
        for _ in range(100):
            message = queue.receive("tasks", worker_id="w1")
            if message is None:
                clock.advance(timedelta(seconds=11))
                message = queue.receive("tasks", worker_id="w1")
            if message is None:
                break
            handle(message)
            if message.attempt == 1:
                clock.advance(timedelta(seconds=11))  # crash: lease expires
            else:
                queue.ack(message)
        assert all(count == 1 for count in processed.values())
        assert len(processed) == 5
