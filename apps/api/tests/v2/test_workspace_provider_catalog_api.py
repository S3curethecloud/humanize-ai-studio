from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.core.settings import (
    ProviderName,
    Settings,
)
from app.main import app
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    ProviderTargetDeclarationSettings,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.services.provider_execution_factory import (
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
)


def _target(
    *,
    target_id: str,
    provider_id: str,
    provider_display_name: str,
    model_id: str,
    enabled: bool = True,
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=provider_id,
            display_name=provider_display_name,
        ),
        model=ModelIdentity(
            provider_id=provider_id,
            model_id=model_id,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        ),
        enabled=enabled,
    )


def _provider_settings() -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/test/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
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
        provider_settings=_provider_settings(),
        provider_target_settings=(
            ProviderTargetDeclarationSettings(
                targets=(
                    _target(
                        target_id=(
                            "deterministic-primary"
                        ),
                        provider_id=(
                            DETERMINISTIC_PROVIDER_ID
                        ),
                        provider_display_name=(
                            "Deterministic"
                        ),
                        model_id=(
                            DETERMINISTIC_MODEL_ID
                        ),
                    ),
                ),
            )
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
    workspace_id: str,
    user_id: str,
    role: EnterpriseWorkspaceRole,
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
]:
    runtime = services.enterprise_authorization

    organization = EnterpriseOrganization(
        organization_id=f"org-{workspace_id}",
        name=f"Organization {workspace_id}",
        created_by_user_id=user_id,
    )

    workspace = EnterpriseWorkspace(
        workspace_id=workspace_id,
        organization_id=organization.organization_id,
        name=f"Workspace {workspace_id}",
        created_by_user_id=user_id,
    )

    membership = EnterpriseWorkspaceMembership(
        membership_id=(
            f"membership-{workspace_id}-{user_id}"
        ),
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


def test_viewer_can_read_platform_provider_catalog(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, membership = _seed_workspace(
        services,
        workspace_id="workspace-provider-viewer",
        user_id="user-provider-viewer",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace.workspace_id}/providers"
        ),
        params={
            "user_id": membership.user_id,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["workspace_id"] == (
        workspace.workspace_id
    )
    assert payload["catalog_scope"] == "platform"

    assert payload["targets"] == [
        {
            "target_id": "deterministic-primary",
            "provider_id": "deterministic",
            "provider_display_name": "Deterministic",
            "model_id": "rules-v1",
            "capabilities": [
                "rewrite",
            ],
            "enabled": True,
        }
    ]

    assert set(
        payload["targets"][0]
    ) == {
        "target_id",
        "provider_id",
        "provider_display_name",
        "model_id",
        "capabilities",
        "enabled",
    }


def test_enabled_only_filter_excludes_disabled_target(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, membership = _seed_workspace(
        services,
        workspace_id="workspace-provider-filter",
        user_id="user-provider-filter",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    services.provider_catalog.create(
        _target(
            target_id="disabled-target",
            provider_id="visibility-test-provider",
            provider_display_name=(
                "Visibility Test Provider"
            ),
            model_id="visibility-model",
            enabled=False,
        )
    )

    all_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace.workspace_id}/providers"
        ),
        params={
            "user_id": membership.user_id,
        },
    )

    assert all_response.status_code == 200

    assert {
        target["target_id"]
        for target in all_response.json()["targets"]
    } == {
        "deterministic-primary",
        "disabled-target",
    }

    enabled_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace.workspace_id}/providers"
        ),
        params={
            "user_id": membership.user_id,
            "enabled_only": True,
        },
    )

    assert enabled_response.status_code == 200

    assert [
        target["target_id"]
        for target in enabled_response.json()["targets"]
    ] == [
        "deterministic-primary"
    ]


def test_cross_tenant_user_cannot_read_provider_catalog(
    services: V2Services,
    client: TestClient,
) -> None:
    _, source_membership = _seed_workspace(
        services,
        workspace_id="workspace-provider-source",
        user_id="user-provider-source",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    target_workspace, _ = _seed_workspace(
        services,
        workspace_id="workspace-provider-target",
        user_id="user-provider-target",
        role=EnterpriseWorkspaceRole.OWNER,
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{target_workspace.workspace_id}/providers"
        ),
        params={
            "user_id": source_membership.user_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "membership_not_found"
    )
    assert "targets" not in response.json()


def test_suspended_member_cannot_read_provider_catalog(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, membership = _seed_workspace(
        services,
        workspace_id="workspace-provider-suspended",
        user_id="user-provider-suspended",
        role=EnterpriseWorkspaceRole.VIEWER,
    )

    suspended = membership.model_copy(
        update={
            "status": (
                EnterpriseMembershipStatus.SUSPENDED
            ),
        }
    )

    services.enterprise_authorization.memberships.update(
        suspended
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace.workspace_id}/providers"
        ),
        params={
            "user_id": suspended.user_id,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "membership_not_active"
    )


def test_provider_catalog_visibility_route_is_read_only(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace, membership = _seed_workspace(
        services,
        workspace_id="workspace-provider-read-only",
        user_id="user-provider-read-only",
        role=EnterpriseWorkspaceRole.OWNER,
    )

    url = (
        f"/api/v2/workspaces/"
        f"{workspace.workspace_id}/providers"
    )

    for method in (
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    ):
        response = client.request(
            method,
            url,
            params={
                "user_id": membership.user_id,
            },
        )

        assert response.status_code == 405
