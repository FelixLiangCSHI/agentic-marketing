from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dmt_api.main import create_app


def test_request_body_over_configured_limit_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DMT_REQUEST_MAX_BODY_BYTES", "1024")
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/runs",
            content=b"x" * 1025,
            headers={"content-type": "application/json"},
        )
    assert response.status_code == 413
    body = response.json()
    assert body["code"] == "request_body_too_large"
    assert body["details"] == {"max_body_bytes": 1024}
