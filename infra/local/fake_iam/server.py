"""Minimal Fake OIDC provider for the local dev stack.

Serves synthetic discovery metadata, a static JWKS placeholder, and a token
endpoint that returns opaque synthetic tokens. No real SSO, no real
credentials — local development only. Stdlib only so it runs in a bare
python:3.12 container.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

ISSUER = "http://fake-iam:8080"

USERS = {
    "content-author": ["content:author"],
    "content-approver": ["content:approver"],
    "campaign-operator": ["campaign:operator"],
    "campaign-approver": ["campaign:approver"],
    "auditor": ["auditor"],
}


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        if self.path == "/healthz":
            self._json(200, {"status": "ok"})
        elif self.path == "/.well-known/openid-configuration":
            self._json(
                200,
                {
                    "issuer": ISSUER,
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                    "response_types_supported": ["token"],
                },
            )
        elif self.path == "/jwks":
            # Placeholder JWKS: local fake tokens are opaque, not signed JWTs.
            self._json(200, {"keys": []})
        elif self.path == "/users":
            self._json(200, {"users": {u: {"roles": r} for u, r in USERS.items()}})
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        if self.path == "/token":
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length else ""
            params = dict(
                pair.split("=", 1) for pair in raw.split("&") if "=" in pair
            )
            subject = params.get("subject", "")
            if subject not in USERS:
                self._json(400, {"error": "unknown_subject"})
                return
            self._json(
                200,
                {
                    "access_token": f"fake-local-{subject}",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "roles": USERS[subject],
                },
            )
        else:
            self._json(404, {"error": "not_found"})

    def log_message(self, format: str, *args: object) -> None:
        pass  # keep container logs quiet


def main() -> None:
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
