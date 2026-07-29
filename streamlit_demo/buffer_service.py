from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date
from typing import Any
from urllib.parse import urlparse

from streamlit_demo.data_models import ConnectionResult, ServiceConfiguration
from streamlit_demo.mock_ai_service import valid_service_endpoint


BUFFER_API_URL = "https://api.buffer.com"
BUFFER_API_KEY_ENV = "BUFFER_API_KEY"


def resolve_buffer_api_key(configured_credential: str = "") -> str:
    """Return the Buffer API key, preferring Streamlit secrets, then the
    environment, then the credential configured in the workspace wizard.

    The returned key is normalized with ``str(...).strip()`` and must never
    be logged, displayed, serialized, or echoed back to the caller UI.
    """
    key = ""
    try:
        import streamlit as st

        try:
            key = str(st.secrets.get(BUFFER_API_KEY_ENV, "") or "")
        except Exception:
            key = ""
    except Exception:
        key = ""
    if not key.strip():
        key = str(os.environ.get(BUFFER_API_KEY_ENV, "") or "")
    if not key.strip():
        key = str(configured_credential or "")
    return key.strip()


def resolve_buffer_endpoint(endpoint: str) -> str:
    """Normalize the Buffer endpoint to the official GraphQL API.

    Any Buffer-owned host (including the legacy ``api.bufferapp.com`` REST
    host) is rewritten to ``https://api.buffer.com``. Mock and localhost
    endpoints are preserved for testing.
    """
    cleaned = str(endpoint or "").strip()
    if not cleaned:
        return BUFFER_API_URL
    host = (urlparse(cleaned).hostname or "").lower()
    if host == "buffer.com" or host.endswith(".buffer.com") or (
        host == "bufferapp.com" or host.endswith(".bufferapp.com")
    ):
        return BUFFER_API_URL
    return cleaned


class BufferService:
    def validate_connection(
        self,
        configuration: ServiceConfiguration,
    ) -> ConnectionResult:
        endpoint = resolve_buffer_endpoint(configuration.endpoint)
        if not valid_service_endpoint(endpoint):
            return ConnectionResult(
                "buffer",
                False,
                "Use an HTTPS, localhost, or mock Buffer endpoint.",
            )
        if not resolve_buffer_api_key(configuration.credential):
            return ConnectionResult(
                "buffer",
                False,
                "A Buffer access token is required. Provide it here, in "
                'st.secrets["BUFFER_API_KEY"], or in the BUFFER_API_KEY '
                "environment variable.",
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
        endpoint = resolve_buffer_endpoint(configuration.endpoint)
        if not valid_service_endpoint(endpoint):
            return {
                "success": False,
                "message": "Use an HTTPS, localhost, or mock Buffer endpoint.",
                "results": [],
            }
        api_key = resolve_buffer_api_key(configuration.credential)
        if not api_key:
            return {
                "success": False,
                "message": (
                    "A Buffer access token is required. Provide it in "
                    'st.secrets["BUFFER_API_KEY"], the BUFFER_API_KEY '
                    "environment variable, or the workspace configuration."
                ),
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
        return self._schedule_via_api(endpoint, api_key, posts)

    def _schedule_via_api(
        self,
        endpoint: str,
        credential: str,
        posts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        url = endpoint.rstrip("/")
        token = credential.strip()
        try:
            channel_ids = self._load_linkedin_channel_ids(url, token)
        except (urllib.error.URLError, OSError, ValueError) as error:
            return {
                "success": False,
                "message": f"Could not load Buffer channels: {error}",
                "results": [],
            }
        if not channel_ids:
            return {
                "success": False,
                "message": (
                    "No Buffer channels are connected to the organizations "
                    "this API key can access. Connect a LinkedIn channel in "
                    "Buffer first."
                ),
                "results": [],
            }
        selected_channel_id = channel_ids[0]
        results: list[dict[str, Any]] = []
        for post in posts:
            results.append(
                self._create_post(url, token, post, selected_channel_id)
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

    def _load_linkedin_channel_ids(self, url: str, token: str) -> list[str]:
        organizations = self._load_organizations(url, token)
        channels: list[dict[str, Any]] = []
        failures: list[str] = []
        for organization in organizations:
            organization_id = str(organization["id"])
            label = str(organization.get("name") or organization_id)
            try:
                data = self._graphql_request(
                    url,
                    token,
                    "query GetChannels($input: ChannelsInput!) { "
                    "channels(input: $input) { id name service } }",
                    {"input": {"organizationId": organization_id}},
                )
            except (urllib.error.URLError, OSError, ValueError) as error:
                failures.append(f"organization {label}: {error}")
                continue
            channels.extend(
                channel
                for channel in (data.get("channels") or [])
                if isinstance(channel, dict) and channel.get("id")
            )
        if not channels:
            if failures:
                raise ValueError(
                    "Buffer denied channel access for every organization "
                    "available to this API key ("
                    + "; ".join(failures)
                    + "). Generate a new API key from the Buffer account "
                    "that owns the LinkedIn channel and update "
                    "BUFFER_API_KEY."
                )
            return []
        linkedin_channel_ids = [
            str(channel["id"])
            for channel in channels
            if str(channel.get("service", "")).lower() == "linkedin"
        ]
        if not linkedin_channel_ids:
            services = sorted(
                {
                    str(channel.get("service") or "unknown").lower()
                    for channel in channels
                }
            )
            raise ValueError(
                "No LinkedIn channel is connected to the organizations this "
                "API key can access (connected services: "
                + ", ".join(services)
                + "). Connect a LinkedIn channel in Buffer, then retry."
            )
        return linkedin_channel_ids

    def _load_organizations(
        self, url: str, token: str
    ) -> list[dict[str, Any]]:
        account = self._graphql_request(
            url,
            token,
            "query GetOrganizations { account { organizations { id name } } }",
        )
        account_data = account.get("account") or {}
        organizations = [
            organization
            for organization in (account_data.get("organizations") or [])
            if isinstance(organization, dict) and organization.get("id")
        ]
        if not organizations:
            raise ValueError(
                "Buffer accepted the API key but returned no organizations "
                "for this account. Confirm the API key was generated in the "
                "Buffer workspace that owns the LinkedIn channel."
            )
        return organizations

    def _create_post(
        self,
        url: str,
        token: str,
        post: dict[str, Any],
        channel_id: str,
    ) -> dict[str, Any]:
        text = str(post.get("text", ""))
        link_url = post.get("linkUrl")
        if link_url and str(link_url) not in text:
            text = f"{text}\n\n{link_url}" if text else str(link_url)
        scheduled_at = post.get("scheduledAt")
        media_urls = post.get("mediaUrls") or []
        mutation = (
            "mutation CreatePost($input: CreatePostInput!) { "
            "createPost(input: $input) { "
            "... on PostActionSuccess { post { id } } "
            "... on MutationError { message } } }"
        )
        post_input: dict[str, Any] = {
            "channelId": channel_id,
            "text": text,
            "schedulingType": "automatic",
        }
        if scheduled_at:
            post_input["mode"] = "customScheduled"
            post_input["dueAt"] = str(scheduled_at)
        else:
            post_input["mode"] = "shareNext"
            post_input["saveToDraft"] = True
        if media_urls:
            post_input["assets"] = {
                "images": [{"url": str(media_urls[0])}]
            }
        try:
            data = self._graphql_request(
                url, token, mutation, {"input": post_input}
            )
        except (urllib.error.URLError, OSError, ValueError) as error:
            return {
                "itemId": post["itemId"],
                "success": False,
                "message": f"Buffer API request failed: {error}",
                "updateId": None,
            }
        result = data.get("createPost") or {}
        created = result.get("post") if isinstance(result, dict) else None
        if isinstance(created, dict) and created.get("id"):
            return {
                "itemId": post["itemId"],
                "success": True,
                "message": "Scheduled in the Buffer queue.",
                "updateId": str(created["id"]),
            }
        detail = result.get("message") if isinstance(result, dict) else None
        return {
            "itemId": post["itemId"],
            "success": False,
            "message": str(detail or "Buffer rejected the post."),
            "updateId": None,
        }

    @staticmethod
    def _graphql_request(
        url: str,
        token: str,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise ValueError(
                    BufferService._authorization_hint(error.code)
                ) from error
            body = error.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                raise ValueError(
                    f"HTTP {error.code} from Buffer: {body[:200]}"
                ) from error
            raise ValueError(
                BufferService._graphql_error_message(parsed)
                or f"HTTP {error.code} from Buffer."
            )
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError("Unexpected Buffer GraphQL response.")
        error_message = BufferService._graphql_error_message(parsed)
        if error_message:
            raise ValueError(error_message)
        data = parsed.get("data")
        if not isinstance(data, dict):
            raise ValueError("Unexpected Buffer GraphQL response.")
        return data

    @staticmethod
    def _authorization_hint(code: int | None = None) -> str:
        prefix = (
            f"Buffer rejected the request (HTTP {code})."
            if code
            else "Buffer reported the request is not authorized."
        )
        return (
            f"{prefix} The API key is invalid, revoked, or belongs to a "
            "different Buffer workspace. Generate a new API key in Buffer "
            "(Account > Integrations > Buffer API) for the workspace that "
            "owns the LinkedIn channel and update BUFFER_API_KEY."
        )

    @staticmethod
    def _graphql_error_message(parsed: Any) -> str | None:
        if not isinstance(parsed, dict):
            return None
        errors = parsed.get("errors")
        if isinstance(errors, list) and errors:
            messages = [
                str(error.get("message"))
                for error in errors
                if isinstance(error, dict) and error.get("message")
            ]
            if not messages:
                return "Buffer returned a GraphQL error."
            combined = "; ".join(messages)
            lowered = combined.lower()
            if "not authorized" in lowered or "unauthenticated" in lowered:
                return f"{combined}. {BufferService._authorization_hint()}"
            return combined
        return None
