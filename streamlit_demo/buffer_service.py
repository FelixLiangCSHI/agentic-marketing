from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
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

    def schedule_posts(
        self,
        configuration: ServiceConfiguration,
        posts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        endpoint = configuration.endpoint.strip()
        if not valid_service_endpoint(endpoint):
            return {
                "success": False,
                "message": "Use an HTTPS, localhost, or mock Buffer endpoint.",
                "results": [],
            }
        if not configuration.credential.strip():
            return {
                "success": False,
                "message": "A Buffer access token is required.",
                "results": [],
            }
        if not posts:
            return {
                "success": False,
                "message": "No exportable posts were selected.",
                "results": [],
            }
        if endpoint.startswith("mock:"):
            results = [
                {
                    "itemId": post["itemId"],
                    "success": True,
                    "message": "Scheduled in the mock Buffer queue.",
                    "updateId": f"mock-update-{index + 1}",
                }
                for index, post in enumerate(posts)
            ]
            return {
                "success": True,
                "message": f"Scheduled {len(results)} posts via the mock Buffer API.",
                "results": results,
            }
        return self._schedule_via_api(endpoint, configuration.credential, posts)

    def _schedule_via_api(
        self,
        endpoint: str,
        credential: str,
        posts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        base = endpoint.rstrip("/")
        token = credential.strip()
        try:
            profiles = self._request_json(
                f"{base}/1/profiles.json", token, data=None
            )
        except (urllib.error.URLError, OSError, ValueError) as error:
            return {
                "success": False,
                "message": f"Could not load Buffer profiles: {error}",
                "results": [],
            }
        if not isinstance(profiles, list):
            return {
                "success": False,
                "message": "The Buffer profiles response was not a list.",
                "results": [],
            }
        profile_ids = [
            str(profile["id"])
            for profile in profiles
            if isinstance(profile, dict)
            and profile.get("id")
            and str(profile.get("service", "")).lower() == "linkedin"
        ]
        if not profile_ids:
            profile_ids = [
                str(profile["id"])
                for profile in profiles
                if isinstance(profile, dict) and profile.get("id")
            ]
        if not profile_ids:
            return {
                "success": False,
                "message": (
                    "No Buffer profiles are connected to the configured "
                    "account. Connect a LinkedIn channel in Buffer first."
                ),
                "results": [],
            }
        results: list[dict[str, Any]] = []
        for post in posts:
            fields: list[tuple[str, str]] = [
                ("profile_ids[]", profile_id) for profile_id in profile_ids
            ]
            fields.append(("text", str(post.get("text", ""))))
            fields.append(("shorten", "false"))
            scheduled_at = post.get("scheduledAt")
            if scheduled_at:
                fields.append(("scheduled_at", str(scheduled_at)))
            else:
                fields.append(("now", "false"))
            link_url = post.get("linkUrl")
            if link_url:
                fields.append(("media[link]", str(link_url)))
            media_urls = post.get("mediaUrls") or []
            if media_urls:
                fields.append(("media[photo]", str(media_urls[0])))
            try:
                response = self._request_json(
                    f"{base}/1/updates/create.json",
                    token,
                    data=urllib.parse.urlencode(fields).encode("utf-8"),
                )
            except (urllib.error.URLError, OSError, ValueError) as error:
                results.append(
                    {
                        "itemId": post["itemId"],
                        "success": False,
                        "message": f"Buffer API request failed: {error}",
                        "updateId": None,
                    }
                )
                continue
            success = bool(
                isinstance(response, dict) and response.get("success")
            )
            updates = (
                response.get("updates", [])
                if isinstance(response, dict)
                else []
            )
            update_id = None
            if updates and isinstance(updates[0], dict):
                update_id = updates[0].get("id")
            message = (
                "Scheduled in the Buffer queue."
                if success
                else str(
                    response.get("message", "Buffer rejected the update.")
                    if isinstance(response, dict)
                    else "Buffer rejected the update."
                )
            )
            results.append(
                {
                    "itemId": post["itemId"],
                    "success": success,
                    "message": message,
                    "updateId": update_id,
                }
            )
        scheduled = sum(1 for result in results if result["success"])
        return {
            "success": scheduled == len(results),
            "message": (
                f"Scheduled {scheduled} of {len(results)} posts via the "
                "Buffer API."
            ),
            "results": results,
        }

    @staticmethod
    def _request_json(
        url: str,
        token: str,
        *,
        data: bytes | None,
    ) -> Any:
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
            },
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                raise ValueError(
                    f"HTTP {error.code} from Buffer: {body[:200]}"
                ) from error
        return json.loads(body)
