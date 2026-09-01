"""Security tests for the identity layer (Fake provider + RBAC).

RED-first: unauthenticated access, forged roles, expired sessions, and
separation-of-duties conflicts must all be rejected before any handler runs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dmt_api.identity.provider import (
    AuthenticationError,
    FakeIdentityProvider,
)
from dmt_api.identity.roles import (
    Role,
    RoleConflictError,
    resolve_roles,
)

_NOW = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)

GROUP_MAPPING: dict[str, frozenset[Role]] = {
    "grp-content": frozenset({Role.CONTENT_CREATOR, Role.REQUESTER}),
    "grp-medical": frozenset({Role.MEDICAL_REVIEWER}),
    "grp-campaign-approver": frozenset({Role.CAMPAIGN_APPROVER}),
    "grp-audit": frozenset({Role.AUDITOR}),
}


def make_provider() -> FakeIdentityProvider:
    return FakeIdentityProvider(group_mapping=GROUP_MAPPING, clock=lambda: _NOW)


class TestFakeIdentityProvider:
    def test_unknown_bearer_token_is_rejected(self) -> None:
        provider = make_provider()
        with pytest.raises(AuthenticationError):
            provider.authenticate("session-that-was-never-issued")

    def test_valid_session_resolves_roles_from_group_mapping_only(self) -> None:
        provider = make_provider()
        token = provider.issue_session("alice", "Alice", groups=("grp-content",))
        principal = provider.authenticate(token)
        assert principal.subject == "alice"
        assert principal.tenant == "tenant-cshi"
        assert principal.roles == frozenset({Role.CONTENT_CREATOR, Role.REQUESTER})

    def test_client_claimed_roles_are_ignored(self) -> None:
        """Roles come only from server-side group mapping, never the caller."""
        provider = make_provider()
        token = provider.issue_session("mallory", "Mallory", groups=("grp-unknown",))
        principal = provider.authenticate(token)
        assert principal.roles == frozenset()

    def test_expired_session_is_rejected(self) -> None:
        provider = make_provider()
        token = provider.issue_session(
            "alice", "Alice", groups=("grp-content",), ttl=timedelta(minutes=5)
        )
        provider.advance_clock(lambda: _NOW + timedelta(minutes=6))
        with pytest.raises(AuthenticationError):
            provider.authenticate(token)

    def test_revoked_session_is_rejected(self) -> None:
        provider = make_provider()
        token = provider.issue_session("alice", "Alice", groups=("grp-content",))
        provider.revoke_session(token)
        with pytest.raises(AuthenticationError):
            provider.authenticate(token)

    def test_session_tokens_are_opaque_and_unique(self) -> None:
        provider = make_provider()
        t1 = provider.issue_session("alice", "Alice", groups=())
        t2 = provider.issue_session("alice", "Alice", groups=())
        assert t1 != t2
        assert "alice" not in t1


class TestRoleResolution:
    def test_unmapped_groups_grant_nothing(self) -> None:
        assert resolve_roles(("nope",), GROUP_MAPPING) == frozenset()

    def test_medical_and_campaign_approver_are_mutually_exclusive(self) -> None:
        """Separation of duties: one identity may never hold both."""
        with pytest.raises(RoleConflictError):
            resolve_roles(("grp-medical", "grp-campaign-approver"), GROUP_MAPPING)

    def test_all_eight_roles_exist(self) -> None:
        expected = {
            "requester",
            "content_creator",
            "medical_reviewer",
            "marketing_reviewer",
            "campaign_operator",
            "campaign_approver",
            "admin",
            "auditor",
        }
        assert {role.value for role in Role} == expected
