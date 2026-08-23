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
    organization_id: str,
    workspace_id: str,
    owner_user_id: str,
    owner_membership_id: str,
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
]:
    runtime = services.enterprise_authorization

    organization = EnterpriseOrganization(
        organization_id=organization_id,
        name=f"Organization {organization_id}",
        created_by_user_id=owner_user_id,
    )

    workspace = EnterpriseWorkspace(
        workspace_id=workspace_id,
        organization_id=organization.organization_id,
        name=f"Workspace {workspace_id}",
        created_by_user_id=owner_user_id,
    )

    owner = EnterpriseWorkspaceMembership(
        membership_id=owner_membership_id,
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


def _seed_two_tenants(
    services: V2Services,
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceMembership,
]:
    workspace_a, owner_a = _seed_workspace(
        services,
        organization_id="org_a",
        workspace_id="workspace_a",
        owner_user_id="user_owner_a",
        owner_membership_id="membership_owner_a",
    )

    workspace_b, owner_b = _seed_workspace(
        services,
        organization_id="org_b",
        workspace_id="workspace_b",
        owner_user_id="user_owner_b",
        owner_membership_id="membership_owner_b",
    )

    member_b = _seed_member(
        services,
        workspace=workspace_b,
        membership_id="membership_target_b",
        user_id="user_target_b",
        role=EnterpriseWorkspaceRole.EDITOR,
    )

    return (
        workspace_a,
        owner_a,
        workspace_b,
        owner_b,
        member_b,
    )


def test_workspace_a_actor_cannot_list_workspace_b_members(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        _,
        _,
    ) = _seed_two_tenants(services)

    response = client.get(
        f"/api/v2/workspaces/{workspace_b.workspace_id}/members",
        params={
            "actor_user_id": owner_a.user_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_resolution_failed"
    )


def test_cross_tenant_get_does_not_reveal_target_existence(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        _,
        member_b,
    ) = _seed_two_tenants(services)

    existing = client.get(
        (
            f"/api/v2/workspaces/{workspace_b.workspace_id}"
            f"/members/{member_b.user_id}"
        ),
        params={
            "actor_user_id": owner_a.user_id,
        },
    )

    missing = client.get(
        (
            f"/api/v2/workspaces/{workspace_b.workspace_id}"
            "/members/user_does_not_exist"
        ),
        params={
            "actor_user_id": owner_a.user_id,
        },
    )

    assert existing.status_code == 403
    assert missing.status_code == 403

    assert existing.json()["detail"] == (
        "authorization_resolution_failed"
    )
    assert missing.json()["detail"] == (
        "authorization_resolution_failed"
    )

    assert existing.json() == missing.json()


def test_cross_workspace_target_is_not_discoverable_from_actor_workspace(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        workspace_a,
        owner_a,
        _,
        _,
        member_b,
    ) = _seed_two_tenants(services)

    cross_workspace_target = client.get(
        (
            f"/api/v2/workspaces/{workspace_a.workspace_id}"
            f"/members/{member_b.user_id}"
        ),
        params={
            "actor_user_id": owner_a.user_id,
        },
    )

    nonexistent_target = client.get(
        (
            f"/api/v2/workspaces/{workspace_a.workspace_id}"
            "/members/user_does_not_exist"
        ),
        params={
            "actor_user_id": owner_a.user_id,
        },
    )

    assert cross_workspace_target.status_code == 404
    assert nonexistent_target.status_code == 404

    assert cross_workspace_target.json()["detail"] == (
        "target_not_found"
    )
    assert nonexistent_target.json()["detail"] == (
        "target_not_found"
    )

    assert cross_workspace_target.json() == (
        nonexistent_target.json()
    )


def test_cross_tenant_add_is_denied_without_creating_membership(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        _,
        _,
    ) = _seed_two_tenants(services)

    runtime = services.enterprise_authorization

    before = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id="user_attempted_cross_tenant_add",
    )

    assert before is None

    response = client.post(
        f"/api/v2/workspaces/{workspace_b.workspace_id}/members",
        json={
            "actor_user_id": owner_a.user_id,
            "membership_id": "membership_cross_tenant_add",
            "user_id": "user_attempted_cross_tenant_add",
            "role": "viewer",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_resolution_failed"
    )

    after = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id="user_attempted_cross_tenant_add",
    )

    assert after is None


def test_cross_tenant_role_change_is_denied_without_mutation(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        _,
        member_b,
    ) = _seed_two_tenants(services)

    runtime = services.enterprise_authorization

    before = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert before is not None
    assert before.role is EnterpriseWorkspaceRole.EDITOR

    response = client.patch(
        (
            f"/api/v2/workspaces/{workspace_b.workspace_id}"
            f"/members/{member_b.user_id}/role"
        ),
        json={
            "actor_user_id": owner_a.user_id,
            "role": "admin",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_resolution_failed"
    )

    after = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert after is not None
    assert after.membership_id == before.membership_id
    assert after.role is EnterpriseWorkspaceRole.EDITOR
    assert after.status == before.status
    assert after.updated_at == before.updated_at


def test_cross_tenant_suspend_is_denied_without_mutation(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        _,
        member_b,
    ) = _seed_two_tenants(services)

    runtime = services.enterprise_authorization

    before = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert before is not None

    response = client.post(
        (
            f"/api/v2/workspaces/{workspace_b.workspace_id}"
            f"/members/{member_b.user_id}/suspend"
        ),
        json={
            "actor_user_id": owner_a.user_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_resolution_failed"
    )

    after = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert after is not None
    assert after.membership_id == before.membership_id
    assert after.role == before.role
    assert after.status == before.status
    assert after.updated_at == before.updated_at


def test_cross_tenant_remove_is_denied_without_mutation(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        _,
        member_b,
    ) = _seed_two_tenants(services)

    runtime = services.enterprise_authorization

    before = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert before is not None

    response = client.request(
        "DELETE",
        (
            f"/api/v2/workspaces/{workspace_b.workspace_id}"
            f"/members/{member_b.user_id}"
        ),
        json={
            "actor_user_id": owner_a.user_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_resolution_failed"
    )

    after = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert after is not None
    assert after.membership_id == before.membership_id
    assert after.role == before.role
    assert after.status == before.status
    assert after.updated_at == before.updated_at


def test_cross_tenant_ownership_transfer_is_denied_without_mutation(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        owner_b,
        member_b,
    ) = _seed_two_tenants(services)

    runtime = services.enterprise_authorization

    before_owner = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=owner_b.user_id,
    )

    before_target = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert before_owner is not None
    assert before_target is not None
    assert before_owner.role is EnterpriseWorkspaceRole.OWNER
    assert before_target.role is EnterpriseWorkspaceRole.EDITOR

    response = client.post(
        (
            f"/api/v2/workspaces/{workspace_b.workspace_id}"
            "/ownership-transfer"
        ),
        json={
            "actor_user_id": owner_a.user_id,
            "target_user_id": member_b.user_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_resolution_failed"
    )

    after_owner = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=owner_b.user_id,
    )

    after_target = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert after_owner is not None
    assert after_target is not None

    assert after_owner.membership_id == (
        before_owner.membership_id
    )
    assert after_owner.role is EnterpriseWorkspaceRole.OWNER
    assert after_owner.status == before_owner.status
    assert after_owner.updated_at == before_owner.updated_at

    assert after_target.membership_id == (
        before_target.membership_id
    )
    assert after_target.role is EnterpriseWorkspaceRole.EDITOR
    assert after_target.status == before_target.status
    assert after_target.updated_at == before_target.updated_at


def test_workspace_a_owner_cannot_transfer_to_workspace_b_member(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        workspace_a,
        owner_a,
        workspace_b,
        _,
        member_b,
    ) = _seed_two_tenants(services)

    runtime = services.enterprise_authorization

    before_a = runtime.memberships.get_current(
        workspace_id=workspace_a.workspace_id,
        user_id=owner_a.user_id,
    )

    before_b = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert before_a is not None
    assert before_b is not None

    response = client.post(
        (
            f"/api/v2/workspaces/{workspace_a.workspace_id}"
            "/ownership-transfer"
        ),
        json={
            "actor_user_id": owner_a.user_id,
            "target_user_id": member_b.user_id,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "target_not_found"
    )

    after_a = runtime.memberships.get_current(
        workspace_id=workspace_a.workspace_id,
        user_id=owner_a.user_id,
    )

    after_b = runtime.memberships.get_current(
        workspace_id=workspace_b.workspace_id,
        user_id=member_b.user_id,
    )

    assert after_a is not None
    assert after_b is not None

    assert after_a.role is EnterpriseWorkspaceRole.OWNER
    assert after_a.status == before_a.status
    assert after_a.updated_at == before_a.updated_at

    assert after_b.role is EnterpriseWorkspaceRole.EDITOR
    assert after_b.status == before_b.status
    assert after_b.updated_at == before_b.updated_at
