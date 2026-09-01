"""The unified Connector protocol every channel connector implements.

Dry-run must be side-effect free; execute requires an approval token
reference, the approved input hash and an idempotency key; unknown write
outcomes must be reconciled before any retry.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from connector_sdk.dry_run import DryRunResult
from connector_sdk.models import ExternalWriteResult


class Connector(Protocol):
    """Standard lifecycle for all channel connectors."""

    def validate_config(self) -> None:
        """Raise ``ConfigInvalidError`` unless ready for the configured mode."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Report mode/readiness without performing external writes."""
        ...

    def dry_run(self, request: Mapping[str, Any]) -> DryRunResult:
        """Validate a proposal with zero external calls."""
        ...

    def execute(
        self,
        request: Mapping[str, Any],
        *,
        approval_token_ref: str,
        input_hash: str,
        idempotency_key: str,
    ) -> ExternalWriteResult:
        """Perform the approved external write exactly once per key."""
        ...

    def get_status(
        self, *, external_object_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Query the state of a previously created external object."""
        ...

    def reconcile(
        self, *, request: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        """Resolve an UNKNOWN write outcome without creating duplicates."""
        ...

    def collect_metrics(
        self,
        *,
        account_id: str,
        external_object_id: str,
        window: Mapping[str, str],
    ) -> tuple[dict[str, Any], ...]:
        """Fetch raw metric rows (read-only)."""
        ...

    def normalize_error(
        self, *, error: Exception, trace_id: str, occurred_at: str
    ) -> dict[str, Any]:
        """Map an exception to the ``connector-error.v1`` document."""
        ...

    def cancel(self, *, external_object_id: str, idempotency_key: str) -> dict[str, Any]:
        """Cancel a known external object (idempotent)."""
        ...
