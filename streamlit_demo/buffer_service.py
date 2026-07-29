from __future__ import annotations

import json
import urllib.error
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
        url = endpoint.rstrip("/")
        token = credential.strip()
        try:
            channel_ids = self._load_channel_ids(url, token)
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
                    "No Buffer channels are connected to the configured "
                    "account. Connect a LinkedIn channel in Buffer first."
                ),
                "results": [],
            }
        results: list[dict[str, Any]] = []
        for post in posts:
            results.append(self._create_post(url, token, post, channel_ids))
        scheduled = sum(1 for result in results if result["success"])
        return {
            "success": scheduled == len(results),
            "message": (
                f"Scheduled {scheduled} of {len(results)} posts via the "
                "Buffer API."
            ),
            "results": results,
        }

    def _load_channel_ids(self, url: str, token: str) -> list[str]:
        account = self._graphql_request(
            url,
            token,
            "query { account { currentOrganization { id } "
            "organizations { id } } }",
        )
        account_data = account.get("account") or {}
        current = account_data.get("currentOrganization") or {}
        organization_id = current.get("id")
        if not organization_id:
            organizations = account_data.get("organizations") or []
            if organizations and isinstance(organizations[0], dict):
                organization_id = organizations[0].get("id")
        if not organization_id:
            raise ValueError(
                "No Buffer organization is available for this access token."
            )
        channels_data = self._graphql_request(
            url,
            token,
            "query Channels($input: ChannelsInput!) { "
            "channels(input: $input) { id name service } }",
            {"input": {"organizationId": str(organization_id)}},
        )
        channels = channels_data.get("channels") or []
        channel_ids = [
            str(channel["id"])
            for channel in channels
            if isinstance(channel, dict)
            and channel.get("id")
            and str(channel.get("service", "")).lower() == "linkedin"
        ]
        if not channel_ids:
            channel_ids = [
                str(channel["id"])
                for channel in channels
                if isinstance(channel, dict) and channel.get("id")
            ]
        return channel_ids

    def _create_post(
        self,
        url: str,
        token: str,
        post: dict[str, Any],
        channel_ids: list[str],
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
        post_ids: list[str] = []
        errors: list[str] = []
        for channel_id in channel_ids:
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
            if media_urls:
                post_input["assets"] = {
                    "images": [{"url": str(media_urls[0])}]
                }
            try:
                data = self._graphql_request(
                    url, token, mutation, {"input": post_input}
                )
            except (urllib.error.URLError, OSError, ValueError) as error:
                errors.append(f"Buffer API request failed: {error}")
                continue
            result = data.get("createPost") or {}
            created = result.get("post") if isinstance(result, dict) else None
            if isinstance(created, dict) and created.get("id"):
                post_ids.append(str(created["id"]))
            else:
                detail = (
                    result.get("message")
                    if isinstance(result, dict)
                    else None
                )
                errors.append(str(detail or "Buffer rejected the post."))
        success = bool(post_ids) and not errors
        message = (
            "Scheduled in the Buffer queue." if success else "; ".join(errors)
        )
        return {
            "itemId": post["itemId"],
            "success": success,
            "message": message or "Buffer rejected the post.",
            "updateId": post_ids[0] if post_ids else None,
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
            if messages:
                return "; ".join(messages)
            return "Buffer returned a GraphQL error."
        return None
