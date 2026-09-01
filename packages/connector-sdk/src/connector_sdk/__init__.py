"""Connector SDK: unified protocol, config, errors, retry and dry-run.

Phase 03 / Subphase 02. All connectors share this contract; the only
implementation in-repo is the deterministic :class:`FakeConnector`.
"""

from connector_sdk.config import ChannelConnectorConfig
from connector_sdk.connector import Connector
from connector_sdk.dry_run import ChannelPolicy, DryRunError, DryRunResult, run_dry_run
from connector_sdk.errors import (
    AuthExpiredError,
    ConfigInvalidError,
    ConnectorSdkError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    RateLimitedError,
    SchemaInvalidError,
    VerificationRequiredError,
    normalize_error,
    sanitize_message,
)
from connector_sdk.fake import FakeConnector
from connector_sdk.http import (
    FakeHttpClient,
    HttpClient,
    HttpRequest,
    HttpResponse,
    ProxyPolicy,
    RetryPolicy,
)
from connector_sdk.models import ExternalWriteResult, WriteOutcome

__all__ = [
    "AuthExpiredError",
    "ChannelConnectorConfig",
    "ChannelPolicy",
    "ConfigInvalidError",
    "Connector",
    "ConnectorSdkError",
    "DryRunError",
    "DryRunResult",
    "ExternalWriteResult",
    "FakeConnector",
    "FakeHttpClient",
    "HttpClient",
    "HttpRequest",
    "HttpResponse",
    "ProviderRequestError",
    "ProviderServerError",
    "ProviderTimeoutError",
    "ProxyPolicy",
    "RateLimitedError",
    "RetryPolicy",
    "SchemaInvalidError",
    "VerificationRequiredError",
    "WriteOutcome",
    "normalize_error",
    "run_dry_run",
    "sanitize_message",
]
