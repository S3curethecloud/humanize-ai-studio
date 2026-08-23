from __future__ import annotations

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
    EnterpriseMembershipStatus,
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)


@pytest.fixture
def services(
    monkeypatch: pytest.MonkeyPatch,
) -> V2Services:
    test_services = V2Services(
        persistence_settings=V2PersistenceSettings(
            backend=PersistenceBackend.MEMORY,
            sqlite_path=None,
            database_url=None,
        ),
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        test_services,
    )

    return test_services


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _seed_workspace(
    services: V2Services,
    *,
    workspace_id: str = "workspace_members",
    organization_id: str = "org_members",
    owner_user_id: str = "user_owner",
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
]:
    runtime = services.enterprise_authorization

    organization = EnterpriseOrganization(
        organization_id=organization_id,
        name="Membership Organization",
        created_by_user_id=owner_user_id,
    )

    workspace = EnterpriseWorkspace(
        workspace_id=workspace_id,
        organization_id=organization.organization_id,
        name="Membership Workspace",
        created_by_user_id=owner_user_id,
    )

    owner = EnterpriseWorkspaceMembership(
        membership_id=f"membership_{workspace_id}_owner",
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
    status: EnterpriseMembershipStatus = (
        EnterpriseMembershipStatus.ACTIVE
    ),
) -> EnterpriseWorkspaceMembership:
    membership = EnterpriseWorkspaceMembership(
        membership_id=membership_id,
        organization_id=workspace.organization_id,
        workspace_id=workspace.workspace_id,
        user_id=user_id,
        role=role,
        status=status,
    )

    services.enterprise_authorization.memberships.create(
        membership
    )

    return membership


def test_owner_can_list_members_with_effective_permissions(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_viewer",
        user_id="user_viewer",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    response = client.get(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["workspace_id"] == workspace.workspace_id
    assert len(payload["members"]) == 2

    members_by_user = {
        item["membership"]["user_id"]: item
        for item in payload["members"]
    }

    owner_payload = members_by_user[owner.user_id]
    viewer_payload = members_by_user["user_viewer"]

    assert owner_payload["membership"]["role"] == "owner"
    assert (
        "workspace.transfer_ownership"
        in owner_payload["effective_permissions"]
    )

    assert viewer_payload["membership"]["role"] == "viewer"
    assert (
        "members.read"
        in viewer_payload["effective_permissions"]
    )
    assert (
        "members.invite"
        not in viewer_payload["effective_permissions"]
    )


def test_owner_can_get_member(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    member = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_editor",
        user_id="user_editor",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    response = client.get(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            f"/members/{member.user_id}"
        ),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["membership"]["membership_id"] == (
        member.membership_id
    )
    assert payload["membership"]["role"] == "editor"
    assert (
        "rewrite.execute"
        in payload["effective_permissions"]
    )


def test_admin_can_add_non_owner_member(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, _ = _seed_workspace(services)

    admin = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_admin",
        user_id="user_admin",
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        json={
            "actor_user_id": admin.user_id,
            "membership_id": "membership_new_editor",
            "user_id": "user_new_editor",
            "role": "editor",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["membership"]["user_id"] == "user_new_editor"
    assert payload["membership"]["role"] == "editor"
    assert payload["membership"]["status"] == "active"
    assert (
        "rewrite.execute"
        in payload["effective_permissions"]
    )


def test_editor_cannot_add_member(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, _ = _seed_workspace(services)

    editor = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_editor_actor",
        user_id="user_editor_actor",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        json={
            "actor_user_id": editor.user_id,
            "membership_id": "membership_denied",
            "user_id": "user_denied",
            "role": "viewer",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_denied"
    )


def test_add_member_rejects_owner_role(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    response = client.post(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        json={
            "actor_user_id": owner.user_id,
            "membership_id": "membership_second_owner",
            "user_id": "user_second_owner",
            "role": "owner",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "owner_role_requires_transfer"
    )


def test_duplicate_current_membership_returns_conflict(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_existing",
        user_id="user_existing",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        json={
            "actor_user_id": owner.user_id,
            "membership_id": "membership_duplicate",
            "user_id": "user_existing",
            "role": "editor",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "duplicate_current_membership"
    )


def test_get_missing_member_returns_not_found(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    response = client.get(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            "/members/user_missing"
        ),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "target_not_found"


def test_admin_can_change_non_owner_role(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, _ = _seed_workspace(services)

    admin = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_admin",
        user_id="user_admin",
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    target = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_role_target",
        user_id="user_role_target",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    response = client.patch(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            f"/members/{target.user_id}/role"
        ),
        json={
            "actor_user_id": admin.user_id,
            "role": "reviewer",
        },
    )

    assert response.status_code == 200
    assert response.json()["membership"]["role"] == (
        "reviewer"
    )


def test_change_role_cannot_promote_to_owner(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    target = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_promotion_target",
        user_id="user_promotion_target",
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    response = client.patch(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            f"/members/{target.user_id}/role"
        ),
        json={
            "actor_user_id": owner.user_id,
            "role": "owner",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "owner_role_requires_transfer"
    )


def test_admin_can_suspend_reactivate_and_remove_member(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, _ = _seed_workspace(services)

    admin = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_admin",
        user_id="user_admin",
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    target = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_lifecycle_target",
        user_id="user_lifecycle_target",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    base_url = (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        f"/members/{target.user_id}"
    )

    suspended = client.post(
        f"{base_url}/suspend",
        json={
            "actor_user_id": admin.user_id,
        },
    )

    assert suspended.status_code == 200
    assert suspended.json()["membership"]["status"] == (
        "suspended"
    )

    reactivated = client.post(
        f"{base_url}/reactivate",
        json={
            "actor_user_id": admin.user_id,
        },
    )

    assert reactivated.status_code == 200
    assert reactivated.json()["membership"]["status"] == (
        "active"
    )

    removed = client.request(
        "DELETE",
        base_url,
        json={
            "actor_user_id": admin.user_id,
        },
    )

    assert removed.status_code == 200
    assert removed.json()["membership"]["status"] == (
        "removed"
    )


def test_owner_lifecycle_is_protected(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    response = client.post(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            f"/members/{owner.user_id}/suspend"
        ),
        json={
            "actor_user_id": owner.user_id,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "owner_lifecycle_protected"
    )


def test_owner_can_transfer_ownership(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    target = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_new_owner",
        user_id="user_new_owner",
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    response = client.post(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            "/ownership-transfer"
        ),
        json={
            "actor_user_id": owner.user_id,
            "target_user_id": target.user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["previous_owner"]["user_id"] == (
        owner.user_id
    )
    assert payload["previous_owner"]["role"] == "admin"

    assert payload["new_owner"]["user_id"] == (
        target.user_id
    )
    assert payload["new_owner"]["role"] == "owner"


def test_non_owner_cannot_transfer_ownership(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, _ = _seed_workspace(services)

    admin = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_admin",
        user_id="user_admin",
        role=EnterpriseWorkspaceRole.ADMIN,
    )

    target = _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_target",
        user_id="user_target",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    response = client.post(
        (
            f"/api/v2/workspaces/{workspace.workspace_id}"
            "/ownership-transfer"
        ),
        json={
            "actor_user_id": admin.user_id,
            "target_user_id": target.user_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_denied"
    )


def test_member_list_status_filter_is_enforced(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, owner = _seed_workspace(services)

    _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_active",
        user_id="user_active",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    _seed_member(
        services,
        workspace=workspace,
        membership_id="membership_suspended",
        user_id="user_suspended",
        role=EnterpriseWorkspaceRole.VIEWER,
        status=EnterpriseMembershipStatus.SUSPENDED,
    )

    response = client.get(
        f"/api/v2/workspaces/{workspace.workspace_id}/members",
        params={
            "actor_user_id": owner.user_id,
            "status": "suspended",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload["members"]) == 1
    assert payload["members"][0]["membership"]["user_id"] == (
        "user_suspended"
    )
    assert payload["members"][0]["membership"]["status"] == (
        "suspended"
    )
