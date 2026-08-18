from __future__ import annotations

from dataclasses import dataclass

from app.v2.repositories.enterprise_workspace import (
    EnterpriseMembershipRepository,
    EnterpriseOrganizationRepository,
    EnterpriseWorkspaceRepository,
)
from app.v2.services.enterprise_authorization_resolver import (
    EnterpriseAuthorizationResolver,
)


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseAuthorizationRuntime:
    organizations: EnterpriseOrganizationRepository
    workspaces: EnterpriseWorkspaceRepository
    memberships: EnterpriseMembershipRepository
    authorization_resolver: EnterpriseAuthorizationResolver
