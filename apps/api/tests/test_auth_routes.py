"""AuthN/AuthZ tests for /api/v1/me and the approval routes.

These run without a database: authentication and role checks must reject
the request before any persistence access happens.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from dmt_api.identity.provider import FakeIdentityProvider
from dmt_api.identity.roles import Role
from dmt_api.main import create_app

GROUP_MAPPING: dict[str, frozenset[Role]] = {
    "grp-content": frozenset({Role.CONTENT_CREATOR, Role.REQUESTER}),
    "grp-medical": frozenset({Role.MEDICAL_REVIEWER}),
    "grp-audit": frozenset({Role.AUDITOR}),
}


@pytest.fixture()
def idp() -> FakeIdentityProvider:
    return FakeIdentityProvider(group_mapping=GROUP_MAPPING)


@pytest.fixture()
def client(idp: FakeIdentityProvider) -> Iterator[TestClient]:
    app = create_app(identity_provider=idp)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


DECISION_BODY = {"decision": "APPROVED"}


class TestMe:
    def test_me_requires_authentication(self, client: TestClient) -> None:
        response = client.get("/api/v1/me")
        assert response.status_code == 401
        assert response.json()["code"] == "unauthenticated"

    def test_me_rejects_garbage_bearer(self, client: TestClient) -> None:
        response = client.get("/api/v1/me", headers=bearer("not-a-session"))
        assert response.status_code == 401

    def test_me_returns_identity_and_roles(
        self, client: TestClient, idp: FakeIdentityProvider
    ) -> None:
        token = idp.issue_session("alice", "Alice", groups=("grp-content",))
        response = client.get("/api/v1/me", headers=bearer(token))
        assert response.status_code == 200
        body = response.json()
        assert body["subject"] == "alice"
        assert body["tenant"] == "tenant-cshi"
        assert sorted(body["roles"]) == ["content_creator", "requester"]

    def test_me_never_echoes_the_session_token(
        self, client: TestClient, idp: FakeIdentityProvider
    ) -> None:
        token = idp.issue_session("alice", "Alice", groups=("grp-content",))
        response = client.get("/api/v1/me", headers=bearer(token))
        assert token not in response.text


class TestApprovalRouteGuards:
    def test_list_requires_authentication(self, client: TestClient) -> None:
        assert client.get("/api/v1/approvals").status_code == 401

    def test_decision_requires_authentication(self, client: TestClient) -> None:
        response = client.post("/api/v1/approvals/apr-1/decision", json=DECISION_BODY)
        assert response.status_code == 401

    def test_decision_rejects_role_without_approval_authority(
        self, client: TestClient, idp: FakeIdentityProvider
    ) -> None:
        token = idp.issue_session("carol", "Carol", groups=("grp-audit",))
        response = client.post(
            "/api/v1/approvals/apr-1/decision",
            json=DECISION_BODY,
            headers=bearer(token),
        )
        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"

    def test_create_rejects_reviewer_roles(
        self, client: TestClient, idp: FakeIdentityProvider
    ) -> None:
        token = idp.issue_session("mona", "Mona", groups=("grp-medical",))
        response = client.post(
            "/api/v1/approvals",
            json={
                "run_id": "run-1",
                "approval_type": "content_publication",
                "binding": {
                    "input_artifact_hash": "sha256:" + "a" * 64,
                    "policy_version": "1.0.0",
                    "workflow_version": "1.0.0",
                    "scope": "content/post-1",
                },
            },
            headers=bearer(token),
        )
        assert response.status_code == 403

    def test_database_unavailable_is_typed_not_fake_success(
        self, client: TestClient, idp: FakeIdentityProvider
    ) -> None:
        """Authorized call without persistence must fail typed, never fake."""
        token = idp.issue_session("carol", "Carol", groups=("grp-audit",))
        response = client.get("/api/v1/approvals", headers=bearer(token))
        assert response.status_code == 503
        assert response.json()["code"] == "persistence_unavailable"
