from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
)
from app.v2.domain.models import (
    WorkspaceMembership,
    WorkspaceRecord,
)
from app.v2.repositories.enterprise_workspace import (
    EnterpriseMembershipRepository,
    EnterpriseOrganizationRepository,
    EnterpriseWorkspaceRepository,
)
from app.v2.repositories.interfaces import (
    MembershipRepository,
    WorkspaceRepository,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.repositories.enterprise_workspace import (
    InMemoryEnterpriseMembershipRepository,
    InMemoryEnterpriseOrganizationRepository,
    InMemoryEnterpriseWorkspaceRepository,
)


class AtomicWorkspaceAuthorityProvisioner(Protocol):
    def provision(
        self,
        *,
        legacy_workspace: WorkspaceRecord,
        legacy_membership: WorkspaceMembership,
        enterprise_organization: EnterpriseOrganization,
        enterprise_workspace: EnterpriseWorkspace,
        enterprise_membership: EnterpriseWorkspaceMembership,
    ) -> None: ...


class InMemoryAtomicWorkspaceAuthorityProvisioner:
    def __init__(
        self,
        *,
        legacy_workspaces: InMemoryWorkspaceRepository,
        legacy_memberships: InMemoryMembershipRepository,
        enterprise_organizations: InMemoryEnterpriseOrganizationRepository,
        enterprise_workspaces: InMemoryEnterpriseWorkspaceRepository,
        enterprise_memberships: InMemoryEnterpriseMembershipRepository,
    ) -> None:
        self._legacy_workspaces = legacy_workspaces
        self._legacy_memberships = legacy_memberships
        self._enterprise_organizations = enterprise_organizations
        self._enterprise_workspaces = enterprise_workspaces
        self._enterprise_memberships = enterprise_memberships

    def provision(
        self,
        *,
        legacy_workspace: WorkspaceRecord,
        legacy_membership: WorkspaceMembership,
        enterprise_organization: EnterpriseOrganization,
        enterprise_workspace: EnterpriseWorkspace,
        enterprise_membership: EnterpriseWorkspaceMembership,
    ) -> None:
        legacy_workspaces_snapshot = dict(
            self._legacy_workspaces._workspaces
        )
        legacy_memberships_snapshot = dict(
            self._legacy_memberships._memberships
        )
        enterprise_organizations_snapshot = dict(
            self._enterprise_organizations._organizations
        )
        enterprise_workspaces_snapshot = dict(
            self._enterprise_workspaces._workspaces
        )
        enterprise_memberships_snapshot = dict(
            self._enterprise_memberships._memberships
        )

        try:
            self._legacy_workspaces.create(
                legacy_workspace
            )
            self._legacy_memberships.create(
                legacy_membership
            )
            self._enterprise_organizations.create(
                enterprise_organization
            )
            self._enterprise_workspaces.create(
                enterprise_workspace
            )
            self._enterprise_memberships.create(
                enterprise_membership
            )
        except Exception:
            self._legacy_workspaces._workspaces = (
                legacy_workspaces_snapshot
            )
            self._legacy_memberships._memberships = (
                legacy_memberships_snapshot
            )
            self._enterprise_organizations._organizations = (
                enterprise_organizations_snapshot
            )
            self._enterprise_workspaces._workspaces = (
                enterprise_workspaces_snapshot
            )
            self._enterprise_memberships._memberships = (
                enterprise_memberships_snapshot
            )
            raise


class SQLiteAtomicWorkspaceAuthorityProvisioner:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(
            database_path
        )

    def provision(
        self,
        *,
        legacy_workspace: WorkspaceRecord,
        legacy_membership: WorkspaceMembership,
        enterprise_organization: EnterpriseOrganization,
        enterprise_workspace: EnterpriseWorkspace,
        enterprise_membership: EnterpriseWorkspaceMembership,
    ) -> None:
        connection = sqlite3.connect(
            str(self._database_path)
        )

        try:
            connection.execute(
                "PRAGMA foreign_keys = ON"
            )
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            connection.execute(
                """
                INSERT INTO workspaces (
                    workspace_id,
                    name,
                    created_by_user_id,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    legacy_workspace.workspace_id,
                    legacy_workspace.name,
                    legacy_workspace.created_by_user_id,
                    legacy_workspace.created_at.isoformat(),
                ),
            )

            connection.execute(
                """
                INSERT INTO memberships (
                    workspace_id,
                    user_id,
                    role,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    legacy_membership.workspace_id,
                    legacy_membership.user_id,
                    legacy_membership.role.value,
                    legacy_membership.created_at.isoformat(),
                ),
            )

            connection.execute(
                """
                INSERT INTO enterprise_organizations (
                    organization_id,
                    created_at,
                    payload
                )
                VALUES (?, ?, ?)
                """,
                (
                    enterprise_organization.organization_id,
                    enterprise_organization.created_at.isoformat(),
                    enterprise_organization.model_dump_json(),
                ),
            )

            connection.execute(
                """
                INSERT INTO enterprise_workspaces (
                    workspace_id,
                    organization_id,
                    created_by_user_id,
                    created_at,
                    updated_at,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    enterprise_workspace.workspace_id,
                    enterprise_workspace.organization_id,
                    enterprise_workspace.created_by_user_id,
                    enterprise_workspace.created_at.isoformat(),
                    enterprise_workspace.updated_at.isoformat(),
                    enterprise_workspace.model_dump_json(),
                ),
            )

            connection.execute(
                """
                INSERT INTO enterprise_memberships (
                    membership_id,
                    organization_id,
                    workspace_id,
                    user_id,
                    status,
                    created_at,
                    updated_at,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    enterprise_membership.membership_id,
                    enterprise_membership.organization_id,
                    enterprise_membership.workspace_id,
                    enterprise_membership.user_id,
                    enterprise_membership.status.value,
                    enterprise_membership.created_at.isoformat(),
                    enterprise_membership.updated_at.isoformat(),
                    enterprise_membership.model_dump_json(),
                ),
            )

            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise ValueError(
                "workspace authority provisioning conflict"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def build_atomic_workspace_authority_provisioner(
    *,
    persistence_settings: V2PersistenceSettings,
    legacy_workspaces: WorkspaceRepository,
    legacy_memberships: MembershipRepository,
    enterprise_organizations: EnterpriseOrganizationRepository,
    enterprise_workspaces: EnterpriseWorkspaceRepository,
    enterprise_memberships: EnterpriseMembershipRepository,
) -> AtomicWorkspaceAuthorityProvisioner:
    if (
        persistence_settings.backend
        is PersistenceBackend.MEMORY
    ):
        if not isinstance(
            legacy_workspaces,
            InMemoryWorkspaceRepository,
        ):
            raise TypeError(
                "memory workspace authority provisioning requires "
                "InMemoryWorkspaceRepository"
            )

        if not isinstance(
            legacy_memberships,
            InMemoryMembershipRepository,
        ):
            raise TypeError(
                "memory workspace authority provisioning requires "
                "InMemoryMembershipRepository"
            )

        if not isinstance(
            enterprise_organizations,
            InMemoryEnterpriseOrganizationRepository,
        ):
            raise TypeError(
                "memory workspace authority provisioning requires "
                "InMemoryEnterpriseOrganizationRepository"
            )

        if not isinstance(
            enterprise_workspaces,
            InMemoryEnterpriseWorkspaceRepository,
        ):
            raise TypeError(
                "memory workspace authority provisioning requires "
                "InMemoryEnterpriseWorkspaceRepository"
            )

        if not isinstance(
            enterprise_memberships,
            InMemoryEnterpriseMembershipRepository,
        ):
            raise TypeError(
                "memory workspace authority provisioning requires "
                "InMemoryEnterpriseMembershipRepository"
            )

        return (
            InMemoryAtomicWorkspaceAuthorityProvisioner(
                legacy_workspaces=legacy_workspaces,
                legacy_memberships=legacy_memberships,
                enterprise_organizations=enterprise_organizations,
                enterprise_workspaces=enterprise_workspaces,
                enterprise_memberships=enterprise_memberships,
            )
        )

    if (
        persistence_settings.backend
        is PersistenceBackend.SQLITE
    ):
        if persistence_settings.sqlite_path is None:
            raise ValueError(
                "SQLite persistence requires a database path."
            )

        return SQLiteAtomicWorkspaceAuthorityProvisioner(
            database_path=persistence_settings.sqlite_path,
        )

    raise RuntimeError(
        "workspace authority convergence requires "
        "memory or SQLite persistence"
    )
