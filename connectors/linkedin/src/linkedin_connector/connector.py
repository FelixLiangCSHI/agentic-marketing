"""LinkedIn Advertising Connector (mock/contract implementation).

Implements the shared :class:`connector_sdk.Connector` protocol. Every
external write requires an approval token reference, the approved input
hash and an idempotency key; duplicate delivery never creates a second
object; timeout-after-create yields ``UNKNOWN`` and reconcile finds the
object instead of recreating it; partial hierarchy success stops further
writes and records the created IDs. The only transport in this repo is
the deterministic :class:`MockLinkedInTransport` — real API calls run
only in protected DEV/SIT jobs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol

from infra_core.clock import Clock
from infra_core.secrets import SecretResolver

from campaign_draft import CampaignProposalV1

from connector_sdk import ChannelPolicy, DryRunResult, run_dry_run, verify_approved_input
from connector_sdk.errors import (
    AuthExpiredError,
    ConnectorSdkError,
    ProviderTimeoutError,
    RateLimitedError,
    normalize_error,
)
from connector_sdk.models import ExternalWriteResult

from linkedin_connector.config import LinkedInConnectorConfig
from linkedin_connector.mappers import map_campaign_request, response_digest
from linkedin_connector.metrics import fetch_metrics_page

Fault = Literal[
    "HTTP_429",
    "AUTH_EXPIRED",
    "TIMEOUT_AFTER_EXTERNAL_CREATE",
    "DUPLICATE_DELIVERY",
    "PARTIAL_HIERARCHY_SUCCESS",
]


class PartialHierarchyError(ConnectorSdkError):
    """Some hierarchy levels were created before a failure; stop writing."""

    code = "partial_hierarchy_success"
    retryable = False
    reconcile_required = True

    def __init__(self, *, created_object_ids: tuple[str, ...], message: str = "") -> None:
        super().__init__(message or "partial hierarchy success; created IDs recorded, writes stopped")
        self.created_object_ids = created_object_ids


class LinkedInTransport(Protocol):
    """Provider transport; real implementations exist only in protected jobs."""

    write_calls: int
    read_calls: int

    def create_campaign(
        self, *, resource: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]: ...

    def find_campaign(self, *, idempotency_key: str) -> dict[str, Any] | None: ...

    def get_campaign(self, *, external_object_id: str) -> dict[str, Any] | None: ...

    def cancel_campaign(self, *, external_object_id: str) -> dict[str, Any]: ...


@dataclass
class MockLinkedInTransport:
    """Deterministic in-memory provider with scripted fault injection."""

    fault: str | None = None
    seed: int = 31014
    write_calls: int = 0
    read_calls: int = 0
    _objects: dict[str, dict[str, Any]] = field(default_factory=dict)
    _by_key: dict[str, str] = field(default_factory=dict)

    def _external_id(self, idempotency_key: str) -> str:
        digest = hashlib.sha256(f"{self.seed}|{idempotency_key}".encode("utf-8")).hexdigest()
        return f"urn:li:sponsoredCampaign:{int(digest[:12], 16)}"

    def create_campaign(
        self, *, resource: Mapping[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        if self.fault == "HTTP_429":
            raise RateLimitedError(retry_after_seconds=19)
        if self.fault == "AUTH_EXPIRED":
            raise AuthExpiredError("provider rejected the request: token expired or revoked")

        if self.fault == "DUPLICATE_DELIVERY":
            # An earlier delivery already landed provider-side.
            external_id = self._external_id(idempotency_key)
            self._objects.setdefault(external_id, {"state": "DRAFT"})
            self._by_key[idempotency_key] = external_id
            self.fault = None
            return {"id": external_id, "status": "DRAFT", "already_exists": True}

        existing = self._by_key.get(idempotency_key)
        if existing is not None:
            return {"id": existing, "status": self._objects[existing]["state"], "already_exists": True}

        external_id = self._external_id(idempotency_key)
        self.write_calls += 1
        self._objects[external_id] = {"state": "DRAFT"}
        self._by_key[idempotency_key] = external_id

        if self.fault == "TIMEOUT_AFTER_EXTERNAL_CREATE":
            self.fault = None
            raise ProviderTimeoutError("response lost after external create; outcome unknown")
        if self.fault == "PARTIAL_HIERARCHY_SUCCESS":
            self.fault = None
            raise PartialHierarchyError(created_object_ids=(external_id,))

        return {"id": external_id, "status": "DRAFT", "already_exists": False}

    def find_campaign(self, *, idempotency_key: str) -> dict[str, Any] | None:
        self.read_calls += 1
        external_id = self._by_key.get(idempotency_key)
        if external_id is None:
            return None
        return {"id": external_id, "status": self._objects[external_id]["state"]}

    def get_campaign(self, *, external_object_id: str) -> dict[str, Any] | None:
        self.read_calls += 1
        obj = self._objects.get(external_object_id)
        if obj is None:
            return None
        return {"id": external_object_id, "status": obj["state"]}

    def cancel_campaign(self, *, external_object_id: str) -> dict[str, Any]:
        obj = self._objects.get(external_object_id)
        if obj is None:
            raise ValueError("unknown external_object_id")
        obj["state"] = "CANCELLED"
        return {"id": external_object_id, "status": "CANCELLED"}


class LinkedInAdvertisingConnector:
    """Mock/contract LinkedIn connector on the shared protocol."""

    def __init__(
        self,
        *,
        config: LinkedInConnectorConfig,
        policy: ChannelPolicy,
        secret_resolver: SecretResolver,
        clock: Clock,
        transport: LinkedInTransport,
    ) -> None:
        self.config = config
        self.policy = policy
        self._resolver = secret_resolver
        self._clock = clock
        self.transport = transport
        # idempotency_key -> (input_hash, external_object_id | None)
        self._ledger: dict[str, tuple[str, str | None]] = {}
        # audit binding: idempotency_key -> (request_hash, response_hash | None)
        self._audit_hashes: dict[str, tuple[str, str | None]] = {}

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
        response = self.transport.get_campaign(external_object_id=external_object_id)
        if response is None:
            raise ValueError("unknown external_object_id")
        return {
            "external_object_id": external_object_id,
            "idempotency_key": idempotency_key,
            "state": response["status"],
            "source_response_hash": response_digest(response),
        }

    def collect_metrics(
        self,
        *,
        account_id: str,
        external_object_id: str,
        window: Mapping[str, str],
    ) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            page = fetch_metrics_page(
                config=self.config,
                account_id=account_id,
                external_object_id=external_object_id,
                window=window,
                cursor=cursor,
                retrieved_at=self._now(),
            )
            self.transport.read_calls += 1
            for row in page.rows:
                rows.append(
                    {
                        "provider_field_name": row.provider_field_name,
                        "provider_value": row.provider_value,
                        "provider_value_type": row.provider_value_type,
                        "period_start": row.period_start,
                        "period_end": row.period_end,
                        "retrieved_at": row.retrieved_at,
                        "source_response_hash": row.source_response_hash,
                    }
                )
            cursor = page.next_cursor
            if cursor is None:
                break
        return tuple(rows)

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
                raise ValueError("idempotency_key was already used with a different input_hash")
            if object_id is not None:
                return ExternalWriteResult(
                    outcome="ALREADY_EXISTS",
                    external_object_id=object_id,
                    operation_id=self._operation_id(idempotency_key),
                )

        proposal = CampaignProposalV1.model_validate(dict(request), strict=False)
        # Defence in depth: recompute the approved hash from the bound
        # fields before any external write (never trust the caller).
        verify_approved_input(proposal, input_hash=input_hash)
        mapped = map_campaign_request(
            proposal=proposal, api_version=self.config.endpoint.api_version_ref
        )

        try:
            response = self.transport.create_campaign(
                resource=mapped.resource, idempotency_key=idempotency_key
            )
        except ProviderTimeoutError:
            # The write may have landed; never create a second object.
            self._ledger[idempotency_key] = (input_hash, None)
            self._audit_hashes[idempotency_key] = (mapped.request_hash, None)
            return ExternalWriteResult(
                outcome="UNKNOWN",
                external_object_id=None,
                operation_id=self._operation_id(idempotency_key),
            )

        external_id = str(response["id"])
        self._ledger[idempotency_key] = (input_hash, external_id)
        self._audit_hashes[idempotency_key] = (mapped.request_hash, response_digest(response))
        outcome: Literal["CREATED", "ALREADY_EXISTS"] = (
            "ALREADY_EXISTS" if response.get("already_exists") else "CREATED"
        )
        return ExternalWriteResult(
            outcome=outcome,
            external_object_id=external_id,
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
        response = self.transport.find_campaign(idempotency_key=idempotency_key)
        if response is not None:
            external_id = str(response["id"])
            input_hash = recorded[0] if recorded is not None else ""
            self._ledger[idempotency_key] = (input_hash, external_id)
            return {
                "outcome": "RECONCILED",
                "external_object_id": external_id,
                "idempotency_key": idempotency_key,
            }
        return {
            "outcome": "NOT_FOUND",
            "external_object_id": None,
            "idempotency_key": idempotency_key,
        }

    def cancel(self, *, external_object_id: str, idempotency_key: str) -> dict[str, Any]:
        response = self.transport.cancel_campaign(external_object_id=external_object_id)
        return {
            "external_object_id": external_object_id,
            "idempotency_key": idempotency_key,
            "state": response["status"],
        }

    # -- errors ------------------------------------------------------------

    def normalize_error(
        self, *, error: Exception, trace_id: str, occurred_at: str
    ) -> dict[str, Any]:
        document = normalize_error(
            connector="linkedin", error=error, trace_id=trace_id, occurred_at=occurred_at
        )
        if isinstance(error, PartialHierarchyError):
            details = dict(document["details"] or {})
            details["created_object_ids"] = list(error.created_object_ids)
            document["details"] = details
        return document

    # -- helpers -----------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _operation_id(self, idempotency_key: str) -> str:
        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return "op-li-" + digest[:16]
