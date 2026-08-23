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


def _seed_enterprise_context(
    services: V2Services,
    *,
    role: EnterpriseWorkspaceRole,
    user_id: str = "user_context",
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
]:
    runtime = services.enterprise_authorization

    organization = EnterpriseOrganization(
        organization_id="org_context",
        name="Context Organization",
        created_by_user_id="user_owner",
    )

    workspace = EnterpriseWorkspace(
        workspace_id="workspace_context",
        organization_id=organization.organization_id,
        name="Enterprise Content Workspace",
        created_by_user_id="user_owner",
    )

    membership = EnterpriseWorkspaceMembership(
        membership_id=f"membership_{role.value}",
        organization_id=organization.organization_id,
        workspace_id=workspace.workspace_id,
        user_id=user_id,
        role=role,
    )

    runtime.organizations.create(
        organization
    )
    runtime.workspaces.create(
        workspace
    )
    runtime.memberships.create(
        membership
    )

    return workspace, membership


def test_access_context_returns_canonical_owner_context(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, membership = _seed_enterprise_context(
        services,
        role=EnterpriseWorkspaceRole.OWNER,
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace.workspace_id}/access-context"
        ),
        params={
            "user_id": membership.user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["workspace"]["workspace_id"] == (
        workspace.workspace_id
    )
    assert payload["workspace"]["name"] == (
        "Enterprise Content Workspace"
    )
    assert payload["membership"]["membership_id"] == (
        membership.membership_id
    )
    assert payload["membership"]["role"] == "owner"

    permissions = set(
        payload["permissions"]
    )

    assert "workspace.read" in permissions
    assert "rewrite.execute" in permissions
    assert "quota.manage" in permissions
    assert "provider_policy.manage" in permissions
    assert "evaluation.manage" in permissions


def test_access_context_returns_viewer_permission_projection(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, membership = _seed_enterprise_context(
        services,
        role=EnterpriseWorkspaceRole.VIEWER,
        user_id="user_viewer",
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace.workspace_id}/access-context"
        ),
        params={
            "user_id": membership.user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["membership"]["role"] == "viewer"

    permissions = set(
        payload["permissions"]
    )

    assert "workspace.read" in permissions
    assert "members.read" in permissions
    assert "quota.read" in permissions
    assert "provider_policy.read" in permissions
    assert "evaluation.read" in permissions

    assert "rewrite.execute" not in permissions
    assert "quota.manage" not in permissions
    assert "provider_policy.manage" not in permissions
    assert "evaluation.manage" not in permissions


def test_access_context_rejects_missing_membership(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, _ = _seed_enterprise_context(
        services,
        role=EnterpriseWorkspaceRole.OWNER,
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace.workspace_id}/access-context"
        ),
        params={
            "user_id": "user_outsider",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "membership_not_found"
    )


def test_access_context_returns_not_found_for_unknown_workspace(
    services: V2Services,
    client: TestClient,
) -> None:
    response = client.get(
        (
            "/api/v2/workspaces/"
            "workspace_missing/access-context"
        ),
        params={
            "user_id": "user_context",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "workspace_not_found"
    )


def test_access_context_rejects_inactive_membership(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, membership = _seed_enterprise_context(
        services,
        role=EnterpriseWorkspaceRole.EDITOR,
        user_id="user_suspended",
    )

    suspended = membership.model_copy(
        update={
            "status": EnterpriseMembershipStatus.SUSPENDED,
        },
    )

    services.enterprise_authorization.memberships.update(
        suspended
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace.workspace_id}/access-context"
        ),
        params={
            "user_id": suspended.user_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "membership_not_active"
    )
