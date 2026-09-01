"""HTTP middleware shared by the API application."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dmt_api.errors import error_response


class RequestBodyTooLargeError(Exception):
    """The request body exceeds the configured maximum size."""


class RequestSizeLimitMiddleware:
    """Reject HTTP request bodies that exceed a fixed byte limit."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                too_large = int(content_length) > self.max_body_bytes
            except ValueError:
                too_large = False
            if too_large:
                await self._send_rejection(scope, receive, send)
                return

        seen = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if isinstance(body, bytes):
                    seen += len(body)
                    if seen > self.max_body_bytes:
                        raise RequestBodyTooLargeError()
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except RequestBodyTooLargeError:
            if response_started:
                raise
            await self._send_rejection(scope, receive, send)

    async def _send_rejection(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        response = error_response(
            413,
            "request_body_too_large",
            "request body exceeds the configured maximum size",
            retryable=False,
            details={"max_body_bytes": self.max_body_bytes},
        )
        await response(scope, receive, send)
