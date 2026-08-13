from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
)


class EnterpriseOrganizationRepository(Protocol):
    def create(
        self,
        organization: EnterpriseOrganization,
    ) -> EnterpriseOrganization: ...

    def get(
        self,
        organization_id: str,
    ) -> EnterpriseOrganization | None: ...


class EnterpriseWorkspaceRepository(Protocol):
    def create(
        self,
        workspace: EnterpriseWorkspace,
    ) -> EnterpriseWorkspace: ...

    def get(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspace | None: ...

    def update(
        self,
        workspace: EnterpriseWorkspace,
    ) -> EnterpriseWorkspace: ...


class EnterpriseMembershipRepository(Protocol):
    def create(
        self,
        membership: EnterpriseWorkspaceMembership,
    ) -> EnterpriseWorkspaceMembership: ...

    def get_by_id(
        self,
        membership_id: str,
    ) -> EnterpriseWorkspaceMembership | None: ...

    def get_current(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> EnterpriseWorkspaceMembership | None: ...

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        status: EnterpriseMembershipStatus | None = None,
        limit: int = 200,
    ) -> tuple[EnterpriseWorkspaceMembership, ...]: ...

    def update(
        self,
        membership: EnterpriseWorkspaceMembership,
    ) -> EnterpriseWorkspaceMembership: ...

    def update_many_atomic(
        self,
        memberships: tuple[
            EnterpriseWorkspaceMembership,
            ...,
        ],
    ) -> tuple[
        EnterpriseWorkspaceMembership,
        ...,
    ]: ...


class InMemoryEnterpriseOrganizationRepository:
    def __init__(self) -> None:
        self._organizations: dict[
            str,
            EnterpriseOrganization,
        ] = {}

    def create(
        self,
        organization: EnterpriseOrganization,
    ) -> EnterpriseOrganization:
        if organization.organization_id in self._organizations:
            raise ValueError(
                f"enterprise organization already exists: {organization.organization_id}"
            )

        self._organizations[organization.organization_id] = organization

        return organization

    def get(
        self,
        organization_id: str,
    ) -> EnterpriseOrganization | None:
        return self._organizations.get(organization_id)


class InMemoryEnterpriseWorkspaceRepository:
    def __init__(self) -> None:
        self._workspaces: dict[
            str,
            EnterpriseWorkspace,
        ] = {}

    def create(
        self,
        workspace: EnterpriseWorkspace,
    ) -> EnterpriseWorkspace:
        if workspace.workspace_id in self._workspaces:
            raise ValueError(f"enterprise workspace already exists: {workspace.workspace_id}")

        self._workspaces[workspace.workspace_id] = workspace

        return workspace

    def get(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspace | None:
        return self._workspaces.get(workspace_id)

    def update(
        self,
        workspace: EnterpriseWorkspace,
    ) -> EnterpriseWorkspace:
        existing = self._workspaces.get(workspace.workspace_id)

        if existing is None:
            raise ValueError(f"unknown enterprise workspace: {workspace.workspace_id}")

        _require_workspace_update_integrity(
            existing=existing,
            updated=workspace,
        )

        self._workspaces[workspace.workspace_id] = workspace

        return workspace


class InMemoryEnterpriseMembershipRepository:
    def __init__(self) -> None:
        self._memberships: dict[
            str,
            EnterpriseWorkspaceMembership,
        ] = {}

    def create(
        self,
        membership: EnterpriseWorkspaceMembership,
    ) -> EnterpriseWorkspaceMembership:
        if membership.membership_id in self._memberships:
            raise ValueError(f"enterprise membership already exists: {membership.membership_id}")

        self._memberships[membership.membership_id] = membership

        return membership

    def get_by_id(
        self,
        membership_id: str,
    ) -> EnterpriseWorkspaceMembership | None:
        return self._memberships.get(membership_id)

    def get_current(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> EnterpriseWorkspaceMembership | None:
        memberships = (
            membership
            for membership in self._memberships.values()
            if (membership.workspace_id == workspace_id and membership.user_id == user_id)
        )

        return max(
            memberships,
            key=lambda membership: (
                membership.created_at,
                membership.membership_id,
            ),
            default=None,
        )

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        status: EnterpriseMembershipStatus | None = None,
        limit: int = 200,
    ) -> tuple[EnterpriseWorkspaceMembership, ...]:
        _require_list_limit(limit)

        memberships = (
            membership
            for membership in self._memberships.values()
            if (
                membership.workspace_id == workspace_id
                and (status is None or membership.status is status)
            )
        )

        ordered = sorted(
            memberships,
            key=lambda membership: (
                membership.created_at,
                membership.membership_id,
            ),
            reverse=True,
        )

        return tuple(ordered[:limit])

    def update(
        self,
        membership: EnterpriseWorkspaceMembership,
    ) -> EnterpriseWorkspaceMembership:
        existing = self._memberships.get(membership.membership_id)

        if existing is None:
            raise ValueError(f"unknown enterprise membership: {membership.membership_id}")

        _require_membership_update_integrity(
            existing=existing,
            updated=membership,
        )

        self._memberships[membership.membership_id] = membership

        return membership

    def update_many_atomic(
        self,
        memberships: tuple[
            EnterpriseWorkspaceMembership,
            ...,
        ],
    ) -> tuple[
        EnterpriseWorkspaceMembership,
        ...,
    ]:
        _require_atomic_membership_updates(memberships)

        for membership in memberships:
            existing = self._memberships.get(membership.membership_id)

            if existing is None:
                raise ValueError(f"unknown enterprise membership: {membership.membership_id}")

            _require_membership_update_integrity(
                existing=existing,
                updated=membership,
            )

        candidate = dict(self._memberships)

        for membership in memberships:
            candidate[membership.membership_id] = membership

        self._memberships = candidate

        return memberships


class SQLiteEnterpriseOrganizationRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        _initialize_database(self._database_path)

    def create(
        self,
        organization: EnterpriseOrganization,
    ) -> EnterpriseOrganization:
        try:
            with _connect(self._database_path) as connection:
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
                        organization.organization_id,
                        organization.created_at.isoformat(),
                        organization.model_dump_json(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"enterprise organization already exists: {organization.organization_id}"
            ) from exc

        return organization

    def get(
        self,
        organization_id: str,
    ) -> EnterpriseOrganization | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_organizations
                WHERE organization_id = ?
                """,
                (organization_id,),
            ).fetchone()

        if row is None:
            return None

        return EnterpriseOrganization.model_validate_json(row["payload"])


class SQLiteEnterpriseWorkspaceRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        _initialize_database(self._database_path)

    def create(
        self,
        workspace: EnterpriseWorkspace,
    ) -> EnterpriseWorkspace:
        try:
            with _connect(self._database_path) as connection:
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
                        workspace.workspace_id,
                        workspace.organization_id,
                        workspace.created_by_user_id,
                        workspace.created_at.isoformat(),
                        workspace.updated_at.isoformat(),
                        workspace.model_dump_json(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"enterprise workspace already exists: {workspace.workspace_id}"
            ) from exc

        return workspace

    def get(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspace | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_workspaces
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        if row is None:
            return None

        return EnterpriseWorkspace.model_validate_json(row["payload"])

    def update(
        self,
        workspace: EnterpriseWorkspace,
    ) -> EnterpriseWorkspace:
        existing = self.get(workspace.workspace_id)

        if existing is None:
            raise ValueError(f"unknown enterprise workspace: {workspace.workspace_id}")

        _require_workspace_update_integrity(
            existing=existing,
            updated=workspace,
        )

        with _connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE enterprise_workspaces
                SET
                    organization_id = ?,
                    created_by_user_id = ?,
                    created_at = ?,
                    updated_at = ?,
                    payload = ?
                WHERE workspace_id = ?
                """,
                (
                    workspace.organization_id,
                    workspace.created_by_user_id,
                    workspace.created_at.isoformat(),
                    workspace.updated_at.isoformat(),
                    workspace.model_dump_json(),
                    workspace.workspace_id,
                ),
            )

        if cursor.rowcount != 1:
            raise RuntimeError("enterprise workspace update lost target record")

        return workspace


class SQLiteEnterpriseMembershipRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        _initialize_database(self._database_path)

    def create(
        self,
        membership: EnterpriseWorkspaceMembership,
    ) -> EnterpriseWorkspaceMembership:
        try:
            with _connect(self._database_path) as connection:
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
                        membership.membership_id,
                        membership.organization_id,
                        membership.workspace_id,
                        membership.user_id,
                        membership.status.value,
                        membership.created_at.isoformat(),
                        membership.updated_at.isoformat(),
                        membership.model_dump_json(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"enterprise membership already exists: {membership.membership_id}"
            ) from exc

        return membership

    def get_by_id(
        self,
        membership_id: str,
    ) -> EnterpriseWorkspaceMembership | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_memberships
                WHERE membership_id = ?
                """,
                (membership_id,),
            ).fetchone()

        if row is None:
            return None

        return EnterpriseWorkspaceMembership.model_validate_json(row["payload"])

    def get_current(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> EnterpriseWorkspaceMembership | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_memberships
                WHERE workspace_id = ?
                  AND user_id = ?
                ORDER BY
                    created_at DESC,
                    membership_id DESC
                LIMIT 1
                """,
                (
                    workspace_id,
                    user_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return EnterpriseWorkspaceMembership.model_validate_json(row["payload"])

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        status: EnterpriseMembershipStatus | None = None,
        limit: int = 200,
    ) -> tuple[EnterpriseWorkspaceMembership, ...]:
        _require_list_limit(limit)

        with _connect(self._database_path) as connection:
            if status is None:
                rows = connection.execute(
                    """
                    SELECT payload
                    FROM enterprise_memberships
                    WHERE workspace_id = ?
                    ORDER BY
                        created_at DESC,
                        membership_id DESC
                    LIMIT ?
                    """,
                    (
                        workspace_id,
                        limit,
                    ),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT payload
                    FROM enterprise_memberships
                    WHERE workspace_id = ?
                      AND status = ?
                    ORDER BY
                        created_at DESC,
                        membership_id DESC
                    LIMIT ?
                    """,
                    (
                        workspace_id,
                        status.value,
                        limit,
                    ),
                ).fetchall()

        return tuple(
            EnterpriseWorkspaceMembership.model_validate_json(row["payload"]) for row in rows
        )

    def update(
        self,
        membership: EnterpriseWorkspaceMembership,
    ) -> EnterpriseWorkspaceMembership:
        existing = self.get_by_id(membership.membership_id)

        if existing is None:
            raise ValueError(f"unknown enterprise membership: {membership.membership_id}")

        _require_membership_update_integrity(
            existing=existing,
            updated=membership,
        )

        with _connect(self._database_path) as connection:
            cursor = connection.execute(
                """
                UPDATE enterprise_memberships
                SET
                    organization_id = ?,
                    workspace_id = ?,
                    user_id = ?,
                    status = ?,
                    created_at = ?,
                    updated_at = ?,
                    payload = ?
                WHERE membership_id = ?
                """,
                (
                    membership.organization_id,
                    membership.workspace_id,
                    membership.user_id,
                    membership.status.value,
                    membership.created_at.isoformat(),
                    membership.updated_at.isoformat(),
                    membership.model_dump_json(),
                    membership.membership_id,
                ),
            )

        if cursor.rowcount != 1:
            raise RuntimeError("enterprise membership update lost target record")

        return membership

    def update_many_atomic(
        self,
        memberships: tuple[
            EnterpriseWorkspaceMembership,
            ...,
        ],
    ) -> tuple[
        EnterpriseWorkspaceMembership,
        ...,
    ]:
        _require_atomic_membership_updates(memberships)

        connection = _connect(self._database_path)

        try:
            connection.execute("BEGIN IMMEDIATE")

            for membership in memberships:
                row = connection.execute(
                    """
                    SELECT payload
                    FROM enterprise_memberships
                    WHERE membership_id = ?
                    """,
                    (membership.membership_id,),
                ).fetchone()

                if row is None:
                    raise ValueError(f"unknown enterprise membership: {membership.membership_id}")

                existing = EnterpriseWorkspaceMembership.model_validate_json(row["payload"])

                _require_membership_update_integrity(
                    existing=existing,
                    updated=membership,
                )

            for membership in memberships:
                cursor = connection.execute(
                    """
                    UPDATE enterprise_memberships
                    SET
                        organization_id = ?,
                        workspace_id = ?,
                        user_id = ?,
                        status = ?,
                        created_at = ?,
                        updated_at = ?,
                        payload = ?
                    WHERE membership_id = ?
                    """,
                    (
                        membership.organization_id,
                        membership.workspace_id,
                        membership.user_id,
                        membership.status.value,
                        membership.created_at.isoformat(),
                        membership.updated_at.isoformat(),
                        membership.model_dump_json(),
                        membership.membership_id,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError("enterprise atomic membership update lost target record")

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return memberships


def _connect(
    database_path: str | Path,
) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    return connection


def _initialize_database(
    database_path: str | Path,
) -> None:
    with _connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS
                enterprise_organizations (
                    organization_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

            CREATE TABLE IF NOT EXISTS
                enterprise_workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    created_by_user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

            CREATE INDEX IF NOT EXISTS
                idx_enterprise_workspaces_organization
            ON enterprise_workspaces (
                organization_id,
                created_at DESC,
                workspace_id DESC
            );

            CREATE TABLE IF NOT EXISTS
                enterprise_memberships (
                    membership_id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );

            CREATE INDEX IF NOT EXISTS
                idx_enterprise_memberships_workspace_user
            ON enterprise_memberships (
                workspace_id,
                user_id,
                created_at DESC,
                membership_id DESC
            );

            CREATE INDEX IF NOT EXISTS
                idx_enterprise_memberships_workspace_status
            ON enterprise_memberships (
                workspace_id,
                status,
                created_at DESC,
                membership_id DESC
            );
            """
        )


def _require_atomic_membership_updates(
    memberships: tuple[
        EnterpriseWorkspaceMembership,
        ...,
    ],
) -> None:
    if not memberships:
        raise ValueError("atomic enterprise membership update requires at least one record")

    membership_ids = tuple(membership.membership_id for membership in memberships)

    if len(set(membership_ids)) != len(membership_ids):
        raise ValueError("atomic enterprise membership update requires unique membership ids")


def _require_workspace_update_integrity(
    *,
    existing: EnterpriseWorkspace,
    updated: EnterpriseWorkspace,
) -> None:
    if updated.organization_id != existing.organization_id:
        raise ValueError("enterprise workspace organization cannot be changed")

    if updated.created_by_user_id != existing.created_by_user_id:
        raise ValueError("enterprise workspace creator cannot be changed")

    if updated.created_at != existing.created_at:
        raise ValueError("enterprise workspace created_at cannot be changed")

    if updated.updated_at < existing.updated_at:
        raise ValueError("enterprise workspace updated_at cannot move backward")


def _require_membership_update_integrity(
    *,
    existing: EnterpriseWorkspaceMembership,
    updated: EnterpriseWorkspaceMembership,
) -> None:
    if updated.organization_id != existing.organization_id:
        raise ValueError("enterprise membership organization cannot be changed")

    if updated.workspace_id != existing.workspace_id:
        raise ValueError("enterprise membership workspace cannot be changed")

    if updated.user_id != existing.user_id:
        raise ValueError("enterprise membership user cannot be changed")

    if updated.created_at != existing.created_at:
        raise ValueError("enterprise membership created_at cannot be changed")

    if updated.updated_at < existing.updated_at:
        raise ValueError("enterprise membership updated_at cannot move backward")


def _require_list_limit(
    limit: int,
) -> None:
    if limit < 1 or limit > 1000:
        raise ValueError("enterprise membership list limit must be between 1 and 1000")
