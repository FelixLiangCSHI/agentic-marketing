"""End-to-end approval flow over HTTP with Fake identity + PostgreSQL."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from dmt_api.identity.provider import FakeIdentityProvider
from dmt_api.identity.roles import Role
from dmt_api.main import create_app

from tests.db.helpers import create_run

GROUP_MAPPING: dict[str, frozenset[Role]] = {
    "grp-content": frozenset({Role.CONTENT_CREATOR, Role.REQUESTER}),
    "grp-medical": frozenset({Role.MEDICAL_REVIEWER}),
    "grp-campaign": frozenset({Role.CAMPAIGN_OPERATOR}),
    "grp-campaign-approver": frozenset({Role.CAMPAIGN_APPROVER}),
    "grp-audit": frozenset({Role.AUDITOR}),
}


@pytest.fixture()
def idp() -> FakeIdentityProvider:
    return FakeIdentityProvider(group_mapping=GROUP_MAPPING)


@pytest.fixture()
def client(
    idp: FakeIdentityProvider, migrated_engine: Engine, database_url: str
) -> Iterator[TestClient]:
    app = create_app(identity_provider=idp, database_url=database_url)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


CREATE_BODY = {
    "run_id": "run-1",
    "approval_type": "content_publication",
    "binding": {
        "input_artifact_hash": "sha256:" + "a" * 64,
        "policy_version": "1.0.0",
        "workflow_version": "1.0.0",
        "scope": "content/post-1",
    },
}


def test_full_flow_request_decide_and_deny_matrix(
    client: TestClient,
    idp: FakeIdentityProvider,
    migrated_engine: Engine,
) -> None:
    create_run(migrated_engine)
    alice = idp.issue_session("alice", "Alice", tenant="tenant-a", groups=("grp-content",))
    mona = idp.issue_session("mona", "Mona", tenant="tenant-a", groups=("grp-medical",))
    alice_reviewer = idp.issue_session(
        "alice", "Alice", tenant="tenant-a", groups=("grp-medical",)
    )

    created = client.post("/api/v1/approvals", json=CREATE_BODY, headers=bearer(alice))
    assert created.status_code == 201
    body = created.json()
    approval_id = body["approval"]["approval_id"]
    assert body["approval"]["status"] == "PENDING"
    assert body["approval_token"]  # returned exactly once, to the requester

    # a medical reviewer cannot create requests
    denied_create = client.post(
        "/api/v1/approvals", json=CREATE_BODY, headers=bearer(mona)
    )
    assert denied_create.status_code == 403

    # self-approval is denied even when the requester somehow holds the role
    self_approve = client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "APPROVED"},
        headers=bearer(alice_reviewer),
    )
    assert self_approve.status_code == 403
    assert self_approve.json()["code"] == "separation_of_duties"

    # the proper reviewer approves
    approved = client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "APPROVED"},
        headers=bearer(mona),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    # double decision hits the state machine
    again = client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "REJECTED"},
        headers=bearer(mona),
    )
    assert again.status_code == 409

    # the list endpoint shows the request but never the token
    listing = client.get("/api/v1/approvals", headers=bearer(mona))
    assert listing.status_code == 200
    assert body["approval_token"] not in listing.text
    assert [item["approval_id"] for item in listing.json()] == [approval_id]


def test_list_approvals_is_scoped_to_requester_or_approver_role(
    client: TestClient,
    idp: FakeIdentityProvider,
    migrated_engine: Engine,
) -> None:
    create_run(migrated_engine, run_id="run-1", requester_id="alice")
    create_run(migrated_engine, run_id="run-2", requester_id="carl")
    alice = idp.issue_session("alice", "Alice", tenant="tenant-a", groups=("grp-content",))
    carl = idp.issue_session("carl", "Carl", tenant="tenant-a", groups=("grp-campaign",))
    mona = idp.issue_session("mona", "Mona", tenant="tenant-a", groups=("grp-medical",))
    auditor = idp.issue_session("audrey", "Audrey", tenant="tenant-a", groups=("grp-audit",))

    content = client.post("/api/v1/approvals", json=CREATE_BODY, headers=bearer(alice))
    campaign_body = {
        **CREATE_BODY,
        "run_id": "run-2",
        "approval_type": "campaign_activation",
        "binding": {**CREATE_BODY["binding"], "scope": "campaign/c-1"},
    }
    campaign = client.post("/api/v1/approvals", json=campaign_body, headers=bearer(carl))
    assert content.status_code == 201
    assert campaign.status_code == 201
    content_id = content.json()["approval"]["approval_id"]
    campaign_id = campaign.json()["approval"]["approval_id"]

    medical_listing = client.get("/api/v1/approvals", headers=bearer(mona))
    assert medical_listing.status_code == 200
    assert [item["approval_id"] for item in medical_listing.json()] == [content_id]

    requester_listing = client.get("/api/v1/approvals", headers=bearer(carl))
    assert requester_listing.status_code == 200
    assert [item["approval_id"] for item in requester_listing.json()] == [campaign_id]

    run_listing = client.get("/api/v1/approvals?run_id=run-1", headers=bearer(auditor))
    assert run_listing.status_code == 200
    assert [item["approval_id"] for item in run_listing.json()] == [content_id]


def test_list_approvals_is_tenant_scoped(
    client: TestClient,
    idp: FakeIdentityProvider,
    migrated_engine: Engine,
) -> None:
    create_run(migrated_engine, run_id="run-1", requester_id="alice", tenant="tenant-a")
    create_run(migrated_engine, run_id="run-2", requester_id="bob", tenant="tenant-b")
    alice = idp.issue_session("alice", "Alice", tenant="tenant-a", groups=("grp-content",))
    bob = idp.issue_session("bob", "Bob", tenant="tenant-b", groups=("grp-content",))
    mona = idp.issue_session("mona", "Mona", tenant="tenant-a", groups=("grp-medical",))

    tenant_a = client.post("/api/v1/approvals", json=CREATE_BODY, headers=bearer(alice))
    tenant_b_body = {**CREATE_BODY, "run_id": "run-2"}
    tenant_b = client.post("/api/v1/approvals", json=tenant_b_body, headers=bearer(bob))
    assert tenant_a.status_code == 201
    assert tenant_b.status_code == 201

    listing = client.get("/api/v1/approvals", headers=bearer(mona))
    assert listing.status_code == 200
    assert [item["approval_id"] for item in listing.json()] == [
        tenant_a.json()["approval"]["approval_id"]
    ]

    hidden = client.get("/api/v1/approvals?run_id=run-2", headers=bearer(mona))
    assert hidden.status_code == 200
    assert hidden.json() == []
