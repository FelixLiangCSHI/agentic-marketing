"""Queue client protocol and in-memory fake.

Semantics (mirrored by the enterprise broker binding in later phases):

* at-least-once delivery with producer-side idempotency keys;
* visibility leases with heartbeats; expired leases redeliver the message;
* bounded retries with exponential backoff plus deterministic jitter;
* a dead-letter queue with explicit replay;
* cooperative cancellation by idempotency key.

Consumers must still deduplicate side effects by idempotency key: delivery
may repeat, side effects must not.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from infra_core.clock import Clock


class QueueError(Exception):
    """Base class for queue failures."""


class LeaseExpiredError(QueueError):
    """The worker no longer owns the message lease."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int
    base_delay_seconds: float
    max_delay_seconds: float
    jitter_ratio: float

    def delay_seconds(self, *, attempt: int, salt: str) -> float:
        """Exponential backoff with deterministic, bounded jitter."""
        raw = self.base_delay_seconds * float(2 ** max(attempt - 1, 0))
        capped = min(raw, self.max_delay_seconds)
        digest = hashlib.sha256(f"{salt}:{attempt}".encode("utf-8")).digest()
        fraction = digest[0] / 255.0  # deterministic 0..1
        return capped * (1.0 + self.jitter_ratio * fraction)


@dataclass(frozen=True, slots=True)
class Message:
    """A leased delivery. ``delivery_id`` changes on every redelivery."""

    topic: str
    idempotency_key: str
    payload: dict[str, Any]
    attempt: int
    delivery_id: int


@dataclass(frozen=True, slots=True)
class DeadMessage:
    topic: str
    idempotency_key: str
    payload: dict[str, Any]
    attempt: int
    last_error: str


class QueueClient(Protocol):
    def enqueue(
        self, topic: str, payload: dict[str, Any], *, idempotency_key: str
    ) -> None: ...

    def receive(self, topic: str, *, worker_id: str) -> Message | None: ...

    def ack(self, message: Message) -> None: ...

    def nack(self, message: Message, *, reason: str) -> None: ...

    def heartbeat(self, message: Message) -> None: ...

    def cancel(self, topic: str, *, idempotency_key: str) -> None: ...

    def is_cancelled(self, message: Message) -> bool: ...


@dataclass(slots=True)
class _Entry:
    idempotency_key: str
    payload: dict[str, Any]
    attempt: int = 0
    visible_at: datetime | None = None  # None -> immediately visible
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    delivery_id: int = 0
    cancelled: bool = False
    done: bool = False


@dataclass
class FakeQueueClient:
    """In-memory queue with real broker semantics for tests and local dev."""

    clock: Clock
    retry_policy: RetryPolicy
    lease_seconds: int
    _topics: dict[str, dict[str, _Entry]] = field(default_factory=dict)
    _dlq: dict[str, list[DeadMessage]] = field(default_factory=dict)
    _delivery_counter: itertools.count[int] = field(
        default_factory=lambda: itertools.count(1)
    )

    def _entries(self, topic: str) -> dict[str, _Entry]:
        return self._topics.setdefault(topic, {})

    def enqueue(
        self, topic: str, payload: dict[str, Any], *, idempotency_key: str
    ) -> None:
        entries = self._entries(topic)
        if idempotency_key in entries:
            return  # duplicate producer enqueue: deduplicated
        entries[idempotency_key] = _Entry(
            idempotency_key=idempotency_key, payload=dict(payload)
        )

    def pending_count(self, topic: str) -> int:
        return sum(
            1
            for entry in self._entries(topic).values()
            if not entry.done and not entry.cancelled
        )

    def receive(self, topic: str, *, worker_id: str) -> Message | None:
        now = self.clock.now()
        for entry in self._entries(topic).values():
            if entry.done or entry.cancelled:
                continue
            if entry.visible_at is not None and now < entry.visible_at:
                continue
            if entry.lease_expires_at is not None and now < entry.lease_expires_at:
                continue
            entry.attempt += 1
            entry.lease_owner = worker_id
            entry.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            entry.delivery_id = next(self._delivery_counter)
            return Message(
                topic=topic,
                idempotency_key=entry.idempotency_key,
                payload=dict(entry.payload),
                attempt=entry.attempt,
                delivery_id=entry.delivery_id,
            )
        return None

    def _owned_entry(self, message: Message) -> _Entry:
        entry = self._entries(message.topic).get(message.idempotency_key)
        if (
            entry is None
            or entry.done
            or entry.delivery_id != message.delivery_id
            or entry.lease_expires_at is None
            or self.clock.now() >= entry.lease_expires_at
        ):
            raise LeaseExpiredError(
                "message lease is no longer owned by this delivery"
            )
        return entry

    def ack(self, message: Message) -> None:
        entry = self._owned_entry(message)
        entry.done = True
        entry.lease_owner = None
        entry.lease_expires_at = None

    def nack(self, message: Message, *, reason: str) -> None:
        entry = self._owned_entry(message)
        entry.lease_owner = None
        entry.lease_expires_at = None
        if entry.attempt >= self.retry_policy.max_attempts:
            entry.done = True
            self._dlq.setdefault(message.topic, []).append(
                DeadMessage(
                    topic=message.topic,
                    idempotency_key=entry.idempotency_key,
                    payload=dict(entry.payload),
                    attempt=entry.attempt,
                    last_error=reason,
                )
            )
            return
        delay = self.retry_policy.delay_seconds(
            attempt=entry.attempt, salt=entry.idempotency_key
        )
        entry.visible_at = self.clock.now() + timedelta(seconds=delay)

    def heartbeat(self, message: Message) -> None:
        entry = self._owned_entry(message)
        entry.lease_expires_at = self.clock.now() + timedelta(
            seconds=self.lease_seconds
        )

    def cancel(self, topic: str, *, idempotency_key: str) -> None:
        entry = self._entries(topic).get(idempotency_key)
        if entry is not None:
            entry.cancelled = True

    def is_cancelled(self, message: Message) -> bool:
        entry = self._entries(message.topic).get(message.idempotency_key)
        return entry is not None and entry.cancelled

    def dlq(self, topic: str) -> list[DeadMessage]:
        return list(self._dlq.get(topic, []))

    def replay_dlq(self, topic: str) -> int:
        """Move every dead message back onto the queue with a fresh attempt budget."""
        dead = self._dlq.pop(topic, [])
        entries = self._entries(topic)
        for message in dead:
            entries[message.idempotency_key] = _Entry(
                idempotency_key=message.idempotency_key,
                payload=dict(message.payload),
            )
        return len(dead)
