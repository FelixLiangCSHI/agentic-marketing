"""RBAC roles and server-controlled group-to-role mapping.

Separation of duties: the same identity must never hold both the Medical
Reviewer and Campaign Approver roles (conflicting approval authorities).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import Enum


class Role(str, Enum):
    REQUESTER = "requester"
    CONTENT_CREATOR = "content_creator"
    MEDICAL_REVIEWER = "medical_reviewer"
    MARKETING_REVIEWER = "marketing_reviewer"
    CAMPAIGN_OPERATOR = "campaign_operator"
    CAMPAIGN_APPROVER = "campaign_approver"
    ADMIN = "admin"
    AUDITOR = "auditor"


class RoleConflictError(Exception):
    """The resolved role set violates separation of duties."""


#: Role pairs that a single identity may never hold at the same time.
CONFLICTING_ROLE_PAIRS: frozenset[frozenset[Role]] = frozenset(
    {frozenset({Role.MEDICAL_REVIEWER, Role.CAMPAIGN_APPROVER})}
)

#: Roles allowed to *request* an approval, per approval type.
REQUESTER_ROLES: Mapping[str, frozenset[Role]] = {
    "content_publication": frozenset({Role.CONTENT_CREATOR}),
    "campaign_activation": frozenset({Role.CAMPAIGN_OPERATOR}),
    "budget_change": frozenset({Role.CAMPAIGN_OPERATOR}),
}

#: Roles allowed to *decide* an approval, per approval type. Admin has no
#: bypass: administration is not approval authority.
APPROVER_ROLES: Mapping[str, frozenset[Role]] = {
    "content_publication": frozenset({Role.MEDICAL_REVIEWER}),
    "campaign_activation": frozenset({Role.CAMPAIGN_APPROVER}),
    "budget_change": frozenset({Role.CAMPAIGN_APPROVER}),
}


def resolve_roles(
    groups: Iterable[str], group_mapping: Mapping[str, frozenset[Role]]
) -> frozenset[Role]:
    """Map directory groups to roles; unknown groups grant nothing.

    Raises :class:`RoleConflictError` when the resulting set contains a
    conflicting role pair. Roles never come from client-supplied claims.
    """
    roles: set[Role] = set()
    for group in groups:
        roles.update(group_mapping.get(group, frozenset()))
    for pair in CONFLICTING_ROLE_PAIRS:
        if pair <= roles:
            names = ", ".join(sorted(role.value for role in pair))
            raise RoleConflictError(
                f"separation of duties violation: identity resolves to conflicting roles ({names})"
            )
    return frozenset(roles)
