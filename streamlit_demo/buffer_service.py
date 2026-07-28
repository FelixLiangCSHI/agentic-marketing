from __future__ import annotations

from streamlit_demo.data_models import ConnectionResult, ServiceConfiguration
from streamlit_demo.mock_ai_service import valid_service_endpoint


class BufferService:
    def validate_connection(
        self,
        configuration: ServiceConfiguration,
    ) -> ConnectionResult:
        if not valid_service_endpoint(configuration.endpoint):
            return ConnectionResult(
                "buffer",
                False,
                "Use an HTTPS, localhost, or mock Buffer endpoint.",
            )
        if not configuration.credential.strip():
            return ConnectionResult(
                "buffer",
                False,
                "A Buffer access token is required.",
            )
        return ConnectionResult("buffer", True, "Connection validated.")

