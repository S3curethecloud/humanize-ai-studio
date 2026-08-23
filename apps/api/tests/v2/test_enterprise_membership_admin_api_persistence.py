from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _sqlite_settings(
    database_path: Path,
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )


def _services(
    database_path: Path,
) -> V2Services:
    return V2Services(
        persistence_settings=_sqlite_settings(
            database_path
        ),
    )


def _install_services(
    monkeypatch: pytest.MonkeyPatch,
    services: V2Services,
) -> None:
    monkeypatch.setattr(
        v2_routes,
        "services",
        services,
    )


def _seed_workspace(
    services: V2Services,
    *,
    workspace_id: str = "workspace_members_persist",
    organization_id: str = "org_members_persist",
    owner_user_id: str = "user_owner_persist",
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
]:
    runtime = services.enterprise_authorization

    organization = EnterpriseOrganization(
        organization_id=organization_id,
        name="Persistent Membership Organization",
        created_by_user_id=owner_user_id,
    )

    workspace = EnterpriseWorkspace(
        workspace_id=workspace_id,
        organization_id=organization.organization_id,
        name="Persistent Membership Workspace",
        created_by_user_id=owner_user_id,
    )

    owner = EnterpriseWorkspaceMembership(
        membership_id="membership_owner_persist",
        organization_id=organization.organization_id,
        workspace_id=workspace.workspace_id,
        user_id=owner_user_id,
        role=EnterpriseWorkspaceRole.OWNER,
    )

    runtime.organizations.create(organization)
    runtime.workspaces.create(workspace)
    runtime.memberships.create(owner)

    return workspace, owner


def _seed_member(
    services: V2Services,
    *,
    workspace: EnterpriseWorkspace,
    membership_id: str,
    user_id: str,
    role: EnterpriseWorkspaceRole,
) -> EnterpriseWorkspaceMembership:
    membership = EnterpriseWorkspaceMembership(
        membership_id=membership_id,
        organization_id=workspace.organization_id,
        workspace_id=workspace.workspace_id,
        user_id=user_id,
        role=role,
    )

    services.enterprise_authorization.memberships.create(
        membership
    )

    return membership


def test_http_added_member_survives_sqlite_runtime_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "membership-add.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    _install_services(
        monkeypatch,
        initial,
    )

    created = client.post(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        json={
            "actor_user_id": owner.user_id,
            "membership_id": "membership_added_persist",
            "user_id": "user_added_persist",
            "role": "editor",
        },
    )

    assert created.status_code == 201
    assert created.json()["membership"]["role"] == "editor"

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    response = client.get(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            "/members/user_added_persist"
        ),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["membership"]["membership_id"] == (
        "membership_added_persist"
    )
    assert payload["membership"]["user_id"] == (
        "user_added_persist"
    )
    assert payload["membership"]["role"] == "editor"
    assert payload["membership"]["status"] == "active"


def test_role_change_survives_sqlite_runtime_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "membership-role.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    target = _seed_member(
        initial,
        workspace=workspace,
        membership_id="membership_role_persist",
        user_id="user_role_persist",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    _install_services(
        monkeypatch,
        initial,
    )

    changed = client.patch(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            f"/members/{target.user_id}/role"
        ),
        json={
            "actor_user_id": owner.user_id,
            "role": "reviewer",
        },
    )

    assert changed.status_code == 200
    assert changed.json()["membership"]["role"] == "reviewer"

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    response = client.get(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            f"/members/{target.user_id}"
        ),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert response.status_code == 200
    assert response.json()["membership"]["role"] == (
        "reviewer"
    )


def test_lifecycle_transitions_survive_each_sqlite_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "membership-lifecycle.db"

    current = _services(database_path)
    workspace, owner = _seed_workspace(current)

    target = _seed_member(
        current,
        workspace=workspace,
        membership_id="membership_lifecycle_persist",
        user_id="user_lifecycle_persist",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    base_url = (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        f"/members/{target.user_id}"
    )

    _install_services(
        monkeypatch,
        current,
    )

    suspended = client.post(
        f"{base_url}/suspend",
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert suspended.status_code == 200
    assert suspended.json()["membership"]["status"] == (
        "suspended"
    )

    current = _services(database_path)

    _install_services(
        monkeypatch,
        current,
    )

    after_suspend = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert after_suspend.status_code == 200
    assert after_suspend.json()["membership"]["status"] == (
        "suspended"
    )

    reactivated = client.post(
        f"{base_url}/reactivate",
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert reactivated.status_code == 200
    assert reactivated.json()["membership"]["status"] == (
        "active"
    )

    current = _services(database_path)

    _install_services(
        monkeypatch,
        current,
    )

    after_reactivate = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert after_reactivate.status_code == 200
    assert after_reactivate.json()["membership"]["status"] == (
        "active"
    )

    removed = client.request(
        "DELETE",
        base_url,
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert removed.status_code == 200
    assert removed.json()["membership"]["status"] == (
        "removed"
    )

    current = _services(database_path)

    _install_services(
        monkeypatch,
        current,
    )

    after_remove = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert after_remove.status_code == 200
    assert after_remove.json()["membership"]["status"] == (
        "removed"
    )


def test_removed_member_requires_new_membership_id_after_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "membership-rejoin.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    target = _seed_member(
        initial,
        workspace=workspace,
        membership_id="membership_original",
        user_id="user_rejoin",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    base_url = (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        f"/members/{target.user_id}"
    )

    _install_services(
        monkeypatch,
        initial,
    )

    removed = client.request(
        "DELETE",
        base_url,
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert removed.status_code == 200
    assert removed.json()["membership"]["status"] == (
        "removed"
    )

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    same_id = client.post(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        json={
            "actor_user_id": owner.user_id,
            "membership_id": "membership_original",
            "user_id": target.user_id,
            "role": "editor",
        },
    )

    assert same_id.status_code == 409
    assert same_id.json()["detail"] == (
        "new_membership_id_required"
    )

    new_id = client.post(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        json={
            "actor_user_id": owner.user_id,
            "membership_id": "membership_rejoined",
            "user_id": target.user_id,
            "role": "editor",
        },
    )

    assert new_id.status_code == 201

    payload = new_id.json()

    assert payload["membership"]["membership_id"] == (
        "membership_rejoined"
    )
    assert payload["membership"]["status"] == "active"
    assert payload["membership"]["role"] == "editor"

    restarted_again = _services(database_path)

    current = (
        restarted_again.enterprise_authorization
        .memberships.get_current(
            workspace_id=workspace.workspace_id,
            user_id=target.user_id,
        )
    )

    assert current is not None
    assert current.membership_id == "membership_rejoined"
    assert current.status.value == "active"

    historical = (
        restarted_again.enterprise_authorization
        .memberships.get_by_id(
            "membership_original"
        )
    )

    assert historical is not None
    assert historical.status.value == "removed"


def test_ownership_transfer_survives_sqlite_runtime_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "ownership-transfer.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    target = _seed_member(
        initial,
        workspace=workspace,
        membership_id="membership_new_owner_persist",
        user_id="user_new_owner_persist",
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    _install_services(
        monkeypatch,
        initial,
    )

    transferred = client.post(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            "/ownership-transfer"
        ),
        json={
            "actor_user_id": owner.user_id,
            "target_user_id": target.user_id,
        },
    )

    assert transferred.status_code == 200

    transfer_payload = transferred.json()

    assert transfer_payload["previous_owner"]["role"] == (
        "admin"
    )
    assert transfer_payload["new_owner"]["role"] == "owner"

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    response = client.get(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        params={
            "actor_user_id": target.user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    members_by_user = {
        item["membership"]["user_id"]: item["membership"]
        for item in payload["members"]
    }

    assert members_by_user[owner.user_id]["role"] == "admin"
    assert members_by_user[target.user_id]["role"] == "owner"

    owners = [
        membership
        for membership in members_by_user.values()
        if membership["role"] == "owner"
        and membership["status"] == "active"
    ]

    assert len(owners) == 1
    assert owners[0]["user_id"] == target.user_id

def test_repeat_suspend_returns_conflict_and_preserves_suspended_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "membership-repeat-suspend.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    target = _seed_member(
        initial,
        workspace=workspace,
        membership_id="membership_repeat_suspend",
        user_id="user_repeat_suspend",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    base_url = (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        f"/members/{target.user_id}"
    )

    _install_services(
        monkeypatch,
        initial,
    )

    first = client.post(
        f"{base_url}/suspend",
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert first.status_code == 200
    assert first.json()["membership"]["status"] == (
        "suspended"
    )

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    repeated = client.post(
        f"{base_url}/suspend",
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert repeated.status_code == 409
    assert repeated.json()["detail"] == (
        "membership_not_active"
    )

    persisted = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert persisted.status_code == 200
    assert persisted.json()["membership"]["status"] == (
        "suspended"
    )


def test_reactivate_active_member_returns_conflict_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "membership-reactivate-active.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    target = _seed_member(
        initial,
        workspace=workspace,
        membership_id="membership_active_reactivate",
        user_id="user_active_reactivate",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    base_url = (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        f"/members/{target.user_id}"
    )

    _install_services(
        monkeypatch,
        initial,
    )

    response = client.post(
        f"{base_url}/reactivate",
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "membership_not_suspended"
    )

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    persisted = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert persisted.status_code == 200
    assert persisted.json()["membership"]["status"] == (
        "active"
    )


def test_removed_member_rejects_reactivate_role_change_and_repeat_remove(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "membership-removed-errors.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    target = _seed_member(
        initial,
        workspace=workspace,
        membership_id="membership_removed_errors",
        user_id="user_removed_errors",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    base_url = (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        f"/members/{target.user_id}"
    )

    _install_services(
        monkeypatch,
        initial,
    )

    removed = client.request(
        "DELETE",
        base_url,
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert removed.status_code == 200
    assert removed.json()["membership"]["status"] == (
        "removed"
    )

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    reactivate = client.post(
        f"{base_url}/reactivate",
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert reactivate.status_code == 409
    assert reactivate.json()["detail"] == (
        "membership_removed"
    )

    role_change = client.patch(
        f"{base_url}/role",
        json={
            "actor_user_id": owner.user_id,
            "role": "editor",
        },
    )

    assert role_change.status_code == 409
    assert role_change.json()["detail"] == (
        "membership_removed"
    )

    repeat_remove = client.request(
        "DELETE",
        base_url,
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert repeat_remove.status_code == 409
    assert repeat_remove.json()["detail"] == (
        "membership_removed"
    )

    restarted_again = _services(database_path)

    _install_services(
        monkeypatch,
        restarted_again,
    )

    persisted = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert persisted.status_code == 200
    assert persisted.json()["membership"]["status"] == (
        "removed"
    )
    assert persisted.json()["membership"]["role"] == (
        "viewer"
    )


def test_owner_lifecycle_operations_remain_protected_after_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "owner-lifecycle-protection.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    _install_services(
        monkeypatch,
        initial,
    )

    base_url = (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        f"/members/{owner.user_id}"
    )

    suspend = client.post(
        f"{base_url}/suspend",
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert suspend.status_code == 409
    assert suspend.json()["detail"] == (
        "owner_lifecycle_protected"
    )

    remove = client.request(
        "DELETE",
        base_url,
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert remove.status_code == 409
    assert remove.json()["detail"] == (
        "owner_lifecycle_protected"
    )

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    persisted = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert persisted.status_code == 200
    assert persisted.json()["membership"]["role"] == (
        "owner"
    )
    assert persisted.json()["membership"]["status"] == (
        "active"
    )
