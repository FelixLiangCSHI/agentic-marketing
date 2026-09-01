"""Deterministic Fake Connector — the only connector implemented in-repo.

It exercises the full :class:`Connector` protocol without any network
access: dry-run performs zero external calls, execute is exactly-once
per idempotency key, timeout-after-create yields UNKNOWN and reconcile
finds the object instead of creating a duplicate. Fault injection covers
HTTP 429 (Retry-After), timeout-after-external-create and auth expiry.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal, Mapping

from infra_core.clock import Clock
from infra_core.secrets import SecretResolver

from campaign_draft import CampaignProposalV1

from connector_sdk.config import ChannelConnectorConfig
from connector_sdk.dry_run import ChannelPolicy, DryRunResult, run_dry_run
from connector_sdk.errors import (
    AuthExpiredError,
    RateLimitedError,
    normalize_error,
)
from connector_sdk.http import HttpClient, ProxyPolicy
from connector_sdk.models import ExternalWriteResult

Fault = Literal["HTTP_429", "TIMEOUT_AFTER_EXTERNAL_CREATE", "AUTH_EXPIRED"]


class FakeConnector:
    """In-memory connector implementing the full protocol deterministically."""

    def __init__(
        self,
        *,
        config: ChannelConnectorConfig,
        policy: ChannelPolicy,
        secret_resolver: SecretResolver,
        clock: Clock,
        http_client: HttpClient | None = None,
        proxy_policy: ProxyPolicy | None = None,
        fault: Fault | None = None,
    ) -> None:
        self.config = config
        self.policy = policy
        self._secret_resolver = secret_resolver
        self._clock = clock
        self.http_client = http_client
        self.proxy_policy = proxy_policy
        self._fault: Fault | None = fault
        self.external_write_calls = 0
        # idempotency_key -> (input_hash, external_object_id | None)
        self._ledger: dict[str, tuple[str, str | None]] = {}
        # external objects actually created "provider-side"
        self._objects: dict[str, dict[str, Any]] = {}

    # -- lifecycle -------------------------------------------------------

    def validate_config(self) -> None:
        self.config.require_ready_for_mode()

    def health_check(self) -> dict[str, Any]:
        return {
            "provider": self.config.provider,
            "mode": self.config.mode,
            "enabled": self.config.enabled,
            "ready": self.config.mode == "mock",
        }

    # -- read-only paths -------------------------------------------------

    def dry_run(self, request: Mapping[str, Any]) -> DryRunResult:
        proposal = CampaignProposalV1.model_validate(dict(request), strict=False)
        return run_dry_run(proposal=proposal, policy=self.policy, as_of=self._now())

    def get_status(
        self, *, external_object_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        obj = self._objects.get(external_object_id)
        if obj is None:
            raise ValueError("unknown external_object_id")
        return {
            "external_object_id": external_object_id,
            "idempotency_key": idempotency_key,
            "state": obj["state"],
        }

    def collect_metrics(
        self,
        *,
        account_id: str,
        external_object_id: str,
        window: Mapping[str, str],
    ) -> tuple[dict[str, Any], ...]:
        if external_object_id not in self._objects:
            raise ValueError("unknown external_object_id")
        seed = self._digest(
            f"{account_id}|{external_object_id}|{window['start']}|{window['end']}"
        )
        return (
            {
                "account_id": account_id,
                "external_object_id": external_object_id,
                "window_start": window["start"],
                "window_end": window["end"],
                "impressions": int(seed[:6], 16) % 10000,
                "clicks": int(seed[6:12], 16) % 500,
                "spend_minor": int(seed[12:18], 16) % 100000,
            },
        )

    # -- side-effecting paths ---------------------------------------------

    def execute(
        self,
        request: Mapping[str, Any],
        *,
        approval_token_ref: str,
        input_hash: str,
        idempotency_key: str,
    ) -> ExternalWriteResult:
        if not approval_token_ref:
            raise ValueError("approval_token_ref is required before any external write")
        if not input_hash.startswith("sha256:"):
            raise ValueError("input_hash must be a sha256: hash of the approved input")
        if not idempotency_key:
            raise ValueError("idempotency_key is required")

        recorded = self._ledger.get(idempotency_key)
        if recorded is not None:
            recorded_hash, object_id = recorded
            if recorded_hash != input_hash:
                raise ValueError(
                    "idempotency_key was already used with a different input_hash"
                )
            if object_id is not None:
                return ExternalWriteResult(
                    outcome="ALREADY_EXISTS",
                    external_object_id=object_id,
                    operation_id=self._operation_id(idempotency_key),
                )

        if self._fault == "HTTP_429":
            raise RateLimitedError(retry_after_seconds=17)
        if self._fault == "AUTH_EXPIRED":
            raise AuthExpiredError("token expired; refresh via approved runbook")

        object_id = "ext-" + self._digest(f"{self.config.mock.seed}|{idempotency_key}")[:24]
        self.external_write_calls += 1
        self._objects[object_id] = {"state": "CREATED", "input_hash": input_hash}

        if self._fault == "TIMEOUT_AFTER_EXTERNAL_CREATE":
            # The write landed provider-side but the response was lost.
            self._ledger[idempotency_key] = (input_hash, None)
            self._pending_object = (idempotency_key, object_id)
            self._fault = None
            return ExternalWriteResult(
                outcome="UNKNOWN",
                external_object_id=None,
                operation_id=self._operation_id(idempotency_key),
            )

        self._ledger[idempotency_key] = (input_hash, object_id)
        return ExternalWriteResult(
            outcome="CREATED",
            external_object_id=object_id,
            operation_id=self._operation_id(idempotency_key),
        )

    def reconcile(
        self, *, request: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        recorded = self._ledger.get(idempotency_key)
        if recorded is not None and recorded[1] is not None:
            return {
                "outcome": "RECONCILED",
                "external_object_id": recorded[1],
                "idempotency_key": idempotency_key,
            }
        pending = getattr(self, "_pending_object", None)
        if pending is not None and pending[0] == idempotency_key:
            input_hash = recorded[0] if recorded is not None else ""
            self._ledger[idempotency_key] = (input_hash, pending[1])
            return {
                "outcome": "RECONCILED",
                "external_object_id": pending[1],
                "idempotency_key": idempotency_key,
            }
        return {
            "outcome": "NOT_FOUND",
            "external_object_id": None,
            "idempotency_key": idempotency_key,
        }

    def cancel(self, *, external_object_id: str, idempotency_key: str) -> dict[str, Any]:
        obj = self._objects.get(external_object_id)
        if obj is None:
            raise ValueError("unknown external_object_id")
        obj["state"] = "CANCELLED"
        return {
            "external_object_id": external_object_id,
            "idempotency_key": idempotency_key,
            "state": "CANCELLED",
        }

    # -- errors ------------------------------------------------------------

    def normalize_error(
        self, *, error: Exception, trace_id: str, occurred_at: str
    ) -> dict[str, Any]:
        return normalize_error(
            connector=self.config.provider,
            error=error,
            trace_id=trace_id,
            occurred_at=occurred_at,
        )

    # -- helpers -----------------------------------------------------------

    _pending_object: tuple[str, str] | None = None

    def _now(self) -> str:
        return self._clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _operation_id(self, idempotency_key: str) -> str:
        return "op-" + self._digest(idempotency_key)[:16]

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
