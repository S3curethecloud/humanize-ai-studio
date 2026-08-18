from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
    EnterpriseWorkspaceStatus,
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

NOW = datetime(
    2026,
    8,
    13,
    8,
    0,
    tzinfo=UTC,
)


def _organization(
    **updates: object,
) -> EnterpriseOrganization:
    values: dict[str, object] = {
        "organization_id": "org_test",
        "name": "Test Organization",
        "created_by_user_id": "user_owner",
        "created_at": NOW,
    }

    values.update(updates)

    return EnterpriseOrganization(**values)


def _workspace(
    **updates: object,
) -> EnterpriseWorkspace:
    values: dict[str, object] = {
        "workspace_id": "workspace_test",
        "organization_id": "org_test",
        "name": "Enterprise Workspace",
        "created_by_user_id": "user_owner",
        "status": EnterpriseWorkspaceStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }

    values.update(updates)

    return EnterpriseWorkspace(**values)


def _membership(
    **updates: object,
) -> EnterpriseWorkspaceMembership:
    values: dict[str, object] = {
        "membership_id": "membership_test",
        "organization_id": "org_test",
        "workspace_id": "workspace_test",
        "user_id": "user_member",
        "role": EnterpriseWorkspaceRole.EDITOR,
        "status": EnterpriseMembershipStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }

    values.update(updates)

    return EnterpriseWorkspaceMembership(**values)


def _repositories(
    *,
    backend: str,
    database_path: Path,
) -> tuple[
    EnterpriseOrganizationRepository,
    EnterpriseWorkspaceRepository,
    EnterpriseMembershipRepository,
]:
    if backend == "memory":
        return (
            InMemoryEnterpriseOrganizationRepository(),
            InMemoryEnterpriseWorkspaceRepository(),
            InMemoryEnterpriseMembershipRepository(),
        )

    if backend == "sqlite":
        return (
            SQLiteEnterpriseOrganizationRepository(
                database_path=database_path,
            ),
            SQLiteEnterpriseWorkspaceRepository(
                database_path=database_path,
            ),
            SQLiteEnterpriseMembershipRepository(
                database_path=database_path,
            ),
        )

    raise AssertionError(f"unsupported test backend: {backend}")


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_organization_create_and_get(
    backend: str,
    tmp_path: Path,
) -> None:
    organizations, _, _ = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    organization = _organization()

    assert organizations.create(organization) == organization
    assert organizations.get(organization.organization_id) == organization
    assert organizations.get("org_missing") is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_duplicate_organization_create_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    organizations, _, _ = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    organization = _organization()

    organizations.create(organization)

    with pytest.raises(
        ValueError,
        match="organization already exists",
    ):
        organizations.create(organization)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_workspace_create_get_and_update(
    backend: str,
    tmp_path: Path,
) -> None:
    _, workspaces, _ = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    workspace = _workspace()

    workspaces.create(workspace)

    updated = workspace.model_copy(
        update={
            "name": "Updated Workspace",
            "status": EnterpriseWorkspaceStatus.SUSPENDED,
            "updated_at": NOW + timedelta(minutes=1),
        }
    )

    assert workspaces.update(updated) == updated
    assert workspaces.get(workspace.workspace_id) == updated


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_duplicate_workspace_create_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    _, workspaces, _ = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    workspace = _workspace()

    workspaces.create(workspace)

    with pytest.raises(
        ValueError,
        match="workspace already exists",
    ):
        workspaces.create(workspace)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_unknown_workspace_update_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    _, workspaces, _ = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    with pytest.raises(
        ValueError,
        match="unknown enterprise workspace",
    ):
        workspaces.update(_workspace())


@pytest.mark.parametrize(
    ("field_name", "field_value", "message"),
    (
        (
            "organization_id",
            "org_other",
            "organization cannot be changed",
        ),
        (
            "created_by_user_id",
            "user_other",
            "creator cannot be changed",
        ),
        (
            "created_at",
            NOW + timedelta(seconds=1),
            "created_at cannot be changed",
        ),
    ),
)
@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_workspace_identity_fields_are_immutable_in_repository(
    backend: str,
    field_name: str,
    field_value: object,
    message: str,
    tmp_path: Path,
) -> None:
    _, workspaces, _ = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    workspace = _workspace()

    workspaces.create(workspace)

    changed = workspace.model_copy(
        update={
            field_name: field_value,
            "updated_at": NOW + timedelta(minutes=1),
        }
    )

    with pytest.raises(
        ValueError,
        match=message,
    ):
        workspaces.update(changed)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_workspace_update_timestamp_cannot_move_backward(
    backend: str,
    tmp_path: Path,
) -> None:
    _, workspaces, _ = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    workspace = _workspace(
        created_at=NOW - timedelta(hours=1),
        updated_at=NOW,
    )
    workspaces.create(workspace)

    stale = workspace.model_copy(
        update={
            "name": "Stale Update",
            "updated_at": NOW - timedelta(seconds=1),
        }
    )

    with pytest.raises(
        ValueError,
        match="updated_at cannot move backward",
    ):
        workspaces.update(stale)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_membership_create_get_and_update(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    membership = _membership()

    memberships.create(membership)

    updated = membership.model_copy(
        update={
            "role": EnterpriseWorkspaceRole.REVIEWER,
            "status": EnterpriseMembershipStatus.SUSPENDED,
            "updated_at": NOW + timedelta(minutes=1),
        }
    )

    assert memberships.update(updated) == updated
    assert memberships.get_by_id(membership.membership_id) == updated


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_duplicate_membership_identity_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    membership = _membership()

    memberships.create(membership)

    with pytest.raises(
        ValueError,
        match="membership already exists",
    ):
        memberships.create(membership)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_multiple_historical_memberships_for_same_user_are_preserved(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    removed = _membership(
        membership_id="membership_old",
        status=EnterpriseMembershipStatus.REMOVED,
        created_at=NOW,
        updated_at=NOW + timedelta(minutes=1),
    )
    rejoined = _membership(
        membership_id="membership_new",
        status=EnterpriseMembershipStatus.ACTIVE,
        created_at=NOW + timedelta(hours=1),
        updated_at=NOW + timedelta(hours=1),
    )

    memberships.create(removed)
    memberships.create(rejoined)

    assert memberships.get_by_id("membership_old") == removed
    assert memberships.get_by_id("membership_new") == rejoined
    assert (
        memberships.get_current(
            workspace_id="workspace_test",
            user_id="user_member",
        )
        == rejoined
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_latest_removed_membership_remains_current_authority_record(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    active = _membership(
        membership_id="membership_active",
        created_at=NOW,
        updated_at=NOW,
    )
    removed = _membership(
        membership_id="membership_removed",
        status=EnterpriseMembershipStatus.REMOVED,
        created_at=NOW + timedelta(hours=1),
        updated_at=NOW + timedelta(hours=1),
    )

    memberships.create(active)
    memberships.create(removed)

    assert (
        memberships.get_current(
            workspace_id="workspace_test",
            user_id="user_member",
        )
        == removed
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_current_membership_tie_breaks_by_membership_id(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    membership_a = _membership(
        membership_id="membership_a",
    )
    membership_b = _membership(
        membership_id="membership_b",
    )

    memberships.create(membership_a)
    memberships.create(membership_b)

    assert (
        memberships.get_current(
            workspace_id="workspace_test",
            user_id="user_member",
        )
        == membership_b
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_membership_list_is_workspace_scoped_and_deterministic(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    first = _membership(
        membership_id="membership_a",
        created_at=NOW,
        updated_at=NOW,
    )
    second = _membership(
        membership_id="membership_b",
        user_id="user_second",
        created_at=NOW + timedelta(minutes=1),
        updated_at=NOW + timedelta(minutes=1),
    )
    other_workspace = _membership(
        membership_id="membership_other",
        workspace_id="workspace_other",
        created_at=NOW + timedelta(minutes=2),
        updated_at=NOW + timedelta(minutes=2),
    )

    memberships.create(first)
    memberships.create(second)
    memberships.create(other_workspace)

    assert memberships.list_for_workspace(workspace_id="workspace_test") == (
        second,
        first,
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_membership_list_can_filter_status(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    active = _membership(
        membership_id="membership_active",
    )
    suspended = _membership(
        membership_id="membership_suspended",
        user_id="user_suspended",
        status=EnterpriseMembershipStatus.SUSPENDED,
        created_at=NOW + timedelta(minutes=1),
        updated_at=NOW + timedelta(minutes=1),
    )

    memberships.create(active)
    memberships.create(suspended)

    assert memberships.list_for_workspace(
        workspace_id="workspace_test",
        status=EnterpriseMembershipStatus.SUSPENDED,
    ) == (suspended,)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
@pytest.mark.parametrize(
    "limit",
    (0, 1001),
)
def test_membership_list_rejects_invalid_limit(
    backend: str,
    limit: int,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    with pytest.raises(
        ValueError,
        match="limit must be between 1 and 1000",
    ):
        memberships.list_for_workspace(
            workspace_id="workspace_test",
            limit=limit,
        )


@pytest.mark.parametrize(
    ("field_name", "field_value", "message"),
    (
        (
            "organization_id",
            "org_other",
            "organization cannot be changed",
        ),
        (
            "workspace_id",
            "workspace_other",
            "workspace cannot be changed",
        ),
        (
            "user_id",
            "user_other",
            "user cannot be changed",
        ),
        (
            "created_at",
            NOW + timedelta(seconds=1),
            "created_at cannot be changed",
        ),
    ),
)
@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_membership_identity_fields_are_immutable_in_repository(
    backend: str,
    field_name: str,
    field_value: object,
    message: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )
    membership = _membership()

    memberships.create(membership)

    changed = membership.model_copy(
        update={
            field_name: field_value,
            "updated_at": NOW + timedelta(minutes=1),
        }
    )

    with pytest.raises(
        ValueError,
        match=message,
    ):
        memberships.update(changed)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_membership_update_timestamp_cannot_move_backward(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    membership = _membership(
        created_at=NOW - timedelta(hours=1),
        updated_at=NOW,
    )
    memberships.create(membership)

    stale = membership.model_copy(
        update={
            "role": EnterpriseWorkspaceRole.VIEWER,
            "updated_at": NOW - timedelta(seconds=1),
        }
    )

    with pytest.raises(
        ValueError,
        match="updated_at cannot move backward",
    ):
        memberships.update(stale)


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_unknown_membership_update_is_rejected(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    with pytest.raises(
        ValueError,
        match="unknown enterprise membership",
    ):
        memberships.update(_membership())


def test_sqlite_records_survive_repository_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "enterprise.db"

    organizations = SQLiteEnterpriseOrganizationRepository(
        database_path=database_path,
    )
    workspaces = SQLiteEnterpriseWorkspaceRepository(
        database_path=database_path,
    )
    memberships = SQLiteEnterpriseMembershipRepository(
        database_path=database_path,
    )

    organization = _organization()
    workspace = _workspace()
    membership = _membership()

    organizations.create(organization)
    workspaces.create(workspace)
    memberships.create(membership)

    restarted_organizations = SQLiteEnterpriseOrganizationRepository(
        database_path=database_path,
    )
    restarted_workspaces = SQLiteEnterpriseWorkspaceRepository(
        database_path=database_path,
    )
    restarted_memberships = SQLiteEnterpriseMembershipRepository(
        database_path=database_path,
    )

    assert restarted_organizations.get(organization.organization_id) == organization
    assert restarted_workspaces.get(workspace.workspace_id) == workspace
    assert restarted_memberships.get_by_id(membership.membership_id) == membership


def test_sqlite_enterprise_tables_do_not_replace_legacy_tables(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "enterprise.db"

    SQLiteEnterpriseMembershipRepository(
        database_path=database_path,
    )

    import sqlite3

    with sqlite3.connect(str(database_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

    assert "enterprise_organizations" in tables
    assert "enterprise_workspaces" in tables
    assert "enterprise_memberships" in tables
    assert "memberships" not in tables


def test_repository_protocol_shapes_are_satisfied() -> None:
    organizations: EnterpriseOrganizationRepository = InMemoryEnterpriseOrganizationRepository()
    workspaces: EnterpriseWorkspaceRepository = InMemoryEnterpriseWorkspaceRepository()
    memberships: EnterpriseMembershipRepository = InMemoryEnterpriseMembershipRepository()

    assert organizations.get("org_missing") is None
    assert workspaces.get("workspace_missing") is None
    assert memberships.get_by_id("membership_missing") is None
    assert (
        memberships.get_current(
            workspace_id="workspace_missing",
            user_id="user_missing",
        )
        is None
    )


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_membership_update_commits_all_records(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    first = _membership(
        membership_id="membership_first",
        user_id="user_first",
        role=EnterpriseWorkspaceRole.OWNER,
    )
    second = _membership(
        membership_id="membership_second",
        user_id="user_second",
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    memberships.create(first)
    memberships.create(second)

    updated_at = NOW + timedelta(minutes=1)

    updated_first = first.model_copy(
        update={
            "role": EnterpriseWorkspaceRole.ADMIN,
            "updated_at": updated_at,
        }
    )
    updated_second = second.model_copy(
        update={
            "role": EnterpriseWorkspaceRole.OWNER,
            "updated_at": updated_at,
        }
    )

    result = memberships.update_many_atomic(
        (
            updated_first,
            updated_second,
        )
    )

    assert result == (
        updated_first,
        updated_second,
    )
    assert memberships.get_by_id("membership_first") == updated_first
    assert memberships.get_by_id("membership_second") == updated_second


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_membership_update_rolls_back_every_record(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    existing = _membership(
        membership_id="membership_existing",
        user_id="user_existing",
        role=EnterpriseWorkspaceRole.OWNER,
    )
    memberships.create(existing)

    updated_existing = existing.model_copy(
        update={
            "role": EnterpriseWorkspaceRole.ADMIN,
            "updated_at": NOW + timedelta(minutes=1),
        }
    )
    missing = _membership(
        membership_id="membership_missing",
        user_id="user_missing",
        role=EnterpriseWorkspaceRole.OWNER,
        created_at=NOW + timedelta(minutes=1),
        updated_at=NOW + timedelta(minutes=1),
    )

    with pytest.raises(
        ValueError,
        match="unknown enterprise membership",
    ):
        memberships.update_many_atomic(
            (
                updated_existing,
                missing,
            )
        )

    assert memberships.get_by_id("membership_existing") == existing
    assert memberships.get_by_id("membership_missing") is None


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_membership_update_rejects_duplicate_ids(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    membership = _membership(
        membership_id="membership_duplicate",
    )
    memberships.create(membership)

    updated = membership.model_copy(
        update={
            "updated_at": NOW + timedelta(minutes=1),
        }
    )

    with pytest.raises(
        ValueError,
        match="requires unique membership ids",
    ):
        memberships.update_many_atomic(
            (
                updated,
                updated,
            )
        )

    assert memberships.get_by_id("membership_duplicate") == membership


@pytest.mark.parametrize(
    "backend",
    ("memory", "sqlite"),
)
def test_atomic_membership_update_rejects_empty_batch(
    backend: str,
    tmp_path: Path,
) -> None:
    _, _, memberships = _repositories(
        backend=backend,
        database_path=tmp_path / "enterprise.db",
    )

    with pytest.raises(
        ValueError,
        match="requires at least one record",
    ):
        memberships.update_many_atomic(())
