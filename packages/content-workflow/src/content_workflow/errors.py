"""Typed content-workflow errors. Nodes never fake success with defaults."""

from __future__ import annotations


class ContentWorkflowError(Exception):
    """Base class for content workflow failures."""


class SkillNotFoundError(ContentWorkflowError):
    """No skill satisfies the requested agent/market/locale/channel scope."""


class SkillExpiredError(ContentWorkflowError):
    """A required skill is expired at the requested as_of."""


class SkillRevokedError(ContentWorkflowError):
    """A required skill has been revoked."""


class SkillFixtureError(ContentWorkflowError):
    """Skill fixture file violates the skill metadata contract."""


class InvalidNodeOutputError(ContentWorkflowError):
    """A node (fake model/media) produced output violating its schema."""


class WorkflowStateError(ContentWorkflowError):
    """Operation not valid for the workflow's current state."""


class WorkflowCancelledError(ContentWorkflowError):
    """The workflow run was cancelled; it cannot be resumed."""
