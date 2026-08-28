"""Server-side identity: roles, providers, and FastAPI guards.

Roles are resolved exclusively from server-controlled group mappings.
Client-supplied role claims are never trusted.
"""

from dmt_api.identity.provider import (
    AuthenticationError,
    FakeIdentityProvider,
    IdentityProvider,
    Principal,
)
from dmt_api.identity.roles import Role, RoleConflictError, resolve_roles

__all__ = [
    "AuthenticationError",
    "FakeIdentityProvider",
    "IdentityProvider",
    "Principal",
    "Role",
    "RoleConflictError",
    "resolve_roles",
]
