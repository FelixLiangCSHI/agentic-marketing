"""The campaign placeholder routes must never fake success (Phase 03/01)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_proposal_draft_is_explicitly_not_implemented(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/campaigns/proposals", json={})
    assert response.status_code == 501
    body = response.json()
    assert body["code"] == "not_implemented"
    assert body["retryable"] is False
    assert body["trace_id"]


def test_get_proposal_is_explicitly_not_implemented(client: TestClient) -> None:
    response = client.get("/api/v1/campaigns/proposals/cpr-0001")
    assert response.status_code == 501
    assert response.json()["code"] == "not_implemented"
