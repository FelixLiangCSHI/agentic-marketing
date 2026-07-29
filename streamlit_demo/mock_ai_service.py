from __future__ import annotations

from urllib.parse import urlparse

from streamlit_demo.data_models import ConnectionResult, ServiceConfiguration, ServiceKind
from streamlit_demo.prompt_templates import PROMPT_TEMPLATES


def valid_service_endpoint(endpoint: str) -> bool:
    parsed = urlparse(endpoint.strip())
    if parsed.scheme == "mock":
        return bool(parsed.netloc or parsed.path)
    if parsed.scheme == "https":
        return bool(parsed.netloc)
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    )


class MockAIService:
    def validate_connection(
        self,
        kind: ServiceKind,
        configuration: ServiceConfiguration,
    ) -> ConnectionResult:
        if kind not in PROMPT_TEMPLATES:
            return ConnectionResult(kind, False, "Unsupported AI service.")
        if not valid_service_endpoint(configuration.endpoint):
            return ConnectionResult(
                kind,
                False,
                "Use an HTTPS, localhost, or mock service endpoint.",
            )
        if not configuration.credential.strip():
            return ConnectionResult(kind, False, "An API credential is required.")
        return ConnectionResult(kind, True, "Connection validated.")

