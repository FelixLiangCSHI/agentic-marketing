"""Typed persistence errors surfaced to callers instead of raw SQL errors."""

from __future__ import annotations


class PersistenceError(Exception):
    """Base class for persistence layer failures."""


class NotFoundError(PersistenceError):
    """The referenced row does not exist."""


class IllegalStateTransitionError(PersistenceError):
    """A state machine transition is not allowed."""


class DependencyCycleError(PersistenceError):
    """Adding the dependency would create a cycle in the task DAG."""


class LeaseConflictError(PersistenceError):
    """The task could not be claimed (wrong status, version, or live lease)."""


class TokenConsumptionError(PersistenceError):
    """The approval token is unknown, expired, or already consumed."""


class SeparationOfDutiesError(PersistenceError):
    """Requester and approver must be different identities."""


class BindingMismatchError(PersistenceError):
    """The approval token was minted for a different input binding."""
