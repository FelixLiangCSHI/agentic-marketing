"""Typed harness errors. Model output never maps to untyped exceptions."""

from __future__ import annotations


class HarnessError(Exception):
    """Base class for harness failures."""


class ToolRegistrationError(HarnessError):
    """Invalid or duplicate tool registration, or registry already frozen."""


class ToolValidationError(HarnessError):
    """Tool parameters failed schema validation."""


class ToolExecutionError(HarnessError):
    """Tool handler raised during execution."""


class HookOrderError(HarnessError):
    """A hook was fired outside the frozen hook order."""


class AuditUnavailableError(HarnessError):
    """The audit sink failed; high-risk actions must fail closed."""


class MemoryPolicyError(HarnessError):
    """Memory write rejected: not a stable preference or wrong namespace."""


class ModelOutputError(HarnessError):
    """Model output could not be parsed into a typed action."""
