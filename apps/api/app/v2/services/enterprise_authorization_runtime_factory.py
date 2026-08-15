from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_workspace import (
    EnterpriseMembershipRepository,
    EnterpriseOrganizationRepository,
    EnterpriseWorkspaceRepository,
    InMemoryEnterpriseMembershipRepository,
    InMemoryEnterpriseOrganizationRepository,
    InMemoryEnterpriseWorkspaceRepository,
    SQLiteEnterpriseMembershipRepository,
    SQLiteEnterpriseOrganizationRepository,
    SQLiteEnterpriseWorkspaceRepository,
)
from app.v2.services.enterprise_authorization_resolver import (
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_runtime import (
    EnterpriseAuthorizationRuntime,
)
from app.v2.services.enterprise_authorization_service import (
    EnterpriseAuthorizationService,
)


class ExternalEnterpriseAuthorizationPersistenceUnavailableError(
    RuntimeError
):
    pass


def build_enterprise_authorization_runtime(
    settings: V2PersistenceSettings,
) -> EnterpriseAuthorizationRuntime:
    settings.validate()

    organizations: EnterpriseOrganizationRepository
    workspaces: EnterpriseWorkspaceRepository
    memberships: EnterpriseMembershipRepository

    if settings.backend is PersistenceBackend.MEMORY:
        organizations = (
            InMemoryEnterpriseOrganizationRepository()
        )
        workspaces = InMemoryEnterpriseWorkspaceRepository()
        memberships = InMemoryEnterpriseMembershipRepository()

    elif settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite persistence requires a database path."
            )

        organizations = (
            SQLiteEnterpriseOrganizationRepository(
                database_path=settings.sqlite_path,
            )
        )
        workspaces = SQLiteEnterpriseWorkspaceRepository(
            database_path=settings.sqlite_path,
        )
        memberships = SQLiteEnterpriseMembershipRepository(
            database_path=settings.sqlite_path,
        )

    else:
        raise (
            ExternalEnterpriseAuthorizationPersistenceUnavailableError(
                "External enterprise authorization persistence "
                "is configured but no adapter has been installed."
            )
        )

    authorization_service = EnterpriseAuthorizationService()

    authorization_resolver = EnterpriseAuthorizationResolver(
        workspaces=workspaces,
        memberships=memberships,
        authorization_service=authorization_service,
    )

    return EnterpriseAuthorizationRuntime(
        organizations=organizations,
        workspaces=workspaces,
        memberships=memberships,
        authorization_resolver=authorization_resolver,
    )
