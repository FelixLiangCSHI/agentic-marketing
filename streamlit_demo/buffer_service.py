from __future__ import annotations

from datetime import date
from typing import Any

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

    def handoff_payload(self, state: dict[str, Any]) -> dict[str, Any]:
        start = state["buffer_start_date"]
        end = state["buffer_end_date"]
        return {
            "dateRange": {
                "start": start.isoformat() if isinstance(start, date) else str(start),
                "end": end.isoformat() if isinstance(end, date) else str(end),
            },
            "timeZone": state["buffer_timezone"],
            "channels": list(state["buffer_channels"]),
            "selectedItemIds": list(state["buffer_selected_item_ids"]),
            "warningsAcknowledged": bool(
                state["buffer_warnings_acknowledged"]
            ),
            "previousExports": list(state["buffer_export_records"]),
        }
