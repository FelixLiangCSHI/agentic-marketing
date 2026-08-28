"""FastAPI authentication and authorization guards.

Guards run before any persistence access. Failures raise typed exceptions
that ``main.create_app`` converts into the versioned error envelope; the
bearer credential is never echoed or logged.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import Depends, Request

from dmt_api.identity.provider import (
    AuthenticationError,
    IdentityProvider,
    Principal,
)
from dmt_api.identity.roles import Role, RoleConflictError


class UnauthenticatedError(Exception):
    """No valid credential was presented (HTTP 401)."""


class ForbiddenError(Exception):
    """The verified identity lacks the required role (HTTP 403)."""


def get_identity_provider(request: Request) -> IdentityProvider:
    provider: IdentityProvider | None = getattr(
        request.app.state, "identity_provider", None
    )
    if provider is None:
        raise UnauthenticatedError("no identity provider is configured")
    return provider


def get_principal(
    request: Request,
    provider: IdentityProvider = Depends(get_identity_provider),
) -> Principal:
    header = request.headers.get("Authorization", "")
    scheme, _, credential = header.partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        raise UnauthenticatedError("missing bearer credential")
    try:
        return provider.authenticate(credential.strip())
    except (AuthenticationError, RoleConflictError) as exc:
        raise UnauthenticatedError(str(exc)) from None


class require_roles:  # noqa: N801 - dependency factory, used like a function
    """Dependency: the principal must hold at least one of ``roles``."""

    def __init__(self, roles: Iterable[Role]) -> None:
        self._roles = frozenset(roles)

    def __call__(
        self, principal: Principal = Depends(get_principal)
    ) -> Principal:
        if not (principal.roles & self._roles):
            needed = ", ".join(sorted(role.value for role in self._roles))
            raise ForbiddenError(f"requires one of the roles: {needed}")
        return principal
