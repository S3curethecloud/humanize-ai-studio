from __future__ import annotations

from typing import Any

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


def _seed_two_tenants(
    services: V2Services,
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
]:
    workspace_a, owner_a = _seed_workspace(
        services,
        organization_id="org_claim_lock_a",
        workspace_id="workspace_claim_lock_a",
        owner_user_id="user_claim_lock_owner_a",
        owner_membership_id="membership_claim_lock_owner_a",
    )

    workspace_b, owner_b = _seed_workspace(
        services,
        organization_id="org_claim_lock_b",
        workspace_id="workspace_claim_lock_b",
        owner_user_id="user_claim_lock_owner_b",
        owner_membership_id="membership_claim_lock_owner_b",
    )

    return (
        workspace_a,
        owner_a,
        workspace_b,
        owner_b,
    )


def _base_url(
    workspace: EnterpriseWorkspace,
) -> str:
    return (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        "/claim-lock-policy"
    )


def _create_policy_for_workspace(
    *,
    client: TestClient,
    workspace: EnterpriseWorkspace,
    owner: EnterpriseWorkspaceMembership,
    policy_id: str = "policy_claim_lock_b",
) -> dict[str, Any]:
    response = client.post(
        _base_url(workspace),
        json={
            "actor_user_id": owner.user_id,
            "policy_id": policy_id,
            "enforcement_mode": "strict",
            "protected_terms": [
                {
                    "term_id": "term_customer",
                    "text": "Customer Alpha",
                },
            ],
        },
    )

    assert response.status_code == 201

    return response.json()["policy"]


def _update_payload(
    *,
    actor_user_id: str,
    policy_id: str,
) -> dict[str, object]:
    return {
        "actor_user_id": actor_user_id,
        "policy_id": policy_id,
        "expected_revision": 1,
        "enforcement_mode": "audit_only",
        "protected_terms": [
            {
                "term_id": "term_attempted",
                "text": "Attempted Mutation",
            },
        ],
    }


def _lifecycle_payload(
    *,
    actor_user_id: str,
    policy_id: str,
) -> dict[str, object]:
    return {
        "actor_user_id": actor_user_id,
        "policy_id": policy_id,
        "expected_revision": 1,
    }


def _mutation_request(
    *,
    client: TestClient,
    method: str,
    base_url: str,
    suffix: str,
    actor_user_id: str,
    policy_id: str,
) -> Any:
    if method == "PATCH":
        payload = _update_payload(
            actor_user_id=actor_user_id,
            policy_id=policy_id,
        )
    else:
        payload = _lifecycle_payload(
            actor_user_id=actor_user_id,
            policy_id=policy_id,
        )

    return client.request(
        method,
        f"{base_url}{suffix}",
        json=payload,
    )


def test_cross_tenant_get_does_not_reveal_target_existence(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        owner_b,
    ) = _seed_two_tenants(services)

    _create_policy_for_workspace(
        client=client,
        workspace=workspace_b,
        owner=owner_b,
    )

    existing = client.get(
        _base_url(workspace_b),
        params={
            "actor_user_id": owner_a.user_id,
        },
    )

    missing_target = client.get(
        (
            "/api/v2/workspaces/"
            "workspace_claim_lock_does_not_exist/"
            "claim-lock-policy"
        ),
        params={
            "actor_user_id": owner_a.user_id,
        },
    )

    assert existing.status_code == 403
    assert missing_target.status_code == 403

    assert existing.json()["detail"] == (
        "authorization_resolution_failed"
    )
    assert missing_target.json()["detail"] == (
        "authorization_resolution_failed"
    )

    assert existing.json() == missing_target.json()


def test_cross_tenant_create_is_denied_without_policy_mutation(
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        owner_b,
    ) = _seed_two_tenants(services)

    created = _create_policy_for_workspace(
        client=client,
        workspace=workspace_b,
        owner=owner_b,
    )

    repository = services.enterprise_claim_lock_policies

    before = repository.get_by_id(
        "policy_claim_lock_b"
    )

    assert before is not None
    assert before.model_dump(mode="json") == created

    attempted_policy_id = "policy_cross_tenant_attempt"

    response = client.post(
        _base_url(workspace_b),
        json={
            "actor_user_id": owner_a.user_id,
            "policy_id": attempted_policy_id,
            "enforcement_mode": "audit_only",
            "protected_terms": [],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_resolution_failed"
    )

    after = repository.get_by_id(
        "policy_claim_lock_b"
    )

    assert after == before
    assert repository.get_by_id(attempted_policy_id) is None
    assert (
        repository.get_for_workspace(
            workspace_b.workspace_id
        )
        == before
    )


@pytest.mark.parametrize(
    ("method", "suffix"),
    (
        ("PATCH", ""),
        ("POST", "/enable"),
        ("POST", "/disable"),
        ("POST", "/archive"),
    ),
)
def test_cross_tenant_mutation_is_denied_without_policy_state_change(
    method: str,
    suffix: str,
    services: V2Services,
    client: TestClient,
) -> None:
    (
        _,
        owner_a,
        workspace_b,
        owner_b,
    ) = _seed_two_tenants(services)

    _create_policy_for_workspace(
        client=client,
        workspace=workspace_b,
        owner=owner_b,
    )

    repository = services.enterprise_claim_lock_policies

    before = repository.get_by_id(
        "policy_claim_lock_b"
    )

    assert before is not None
    assert before.revision == 1
    assert before.status.value == "active"

    response = _mutation_request(
        client=client,
        method=method,
        base_url=_base_url(workspace_b),
        suffix=suffix,
        actor_user_id=owner_a.user_id,
        policy_id="policy_claim_lock_b",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "authorization_resolution_failed"
    )

    after = repository.get_by_id(
        "policy_claim_lock_b"
    )

    assert after == before
    assert after is not None
    assert after.revision == 1
    assert after.status.value == "active"

    assert (
        repository.get_for_workspace(
            workspace_b.workspace_id
        )
        == before
    )


@pytest.mark.parametrize(
    ("method", "suffix"),
    (
        ("PATCH", ""),
        ("POST", "/enable"),
        ("POST", "/disable"),
        ("POST", "/archive"),
    ),
)
def test_cross_workspace_policy_id_is_indistinguishable_from_missing(
    method: str,
    suffix: str,
    services: V2Services,
    client: TestClient,
) -> None:
    (
        workspace_a,
        owner_a,
        workspace_b,
        owner_b,
    ) = _seed_two_tenants(services)

    _create_policy_for_workspace(
        client=client,
        workspace=workspace_b,
        owner=owner_b,
    )

    repository = services.enterprise_claim_lock_policies

    before_b = repository.get_by_id(
        "policy_claim_lock_b"
    )

    assert before_b is not None

    cross_workspace = _mutation_request(
        client=client,
        method=method,
        base_url=_base_url(workspace_a),
        suffix=suffix,
        actor_user_id=owner_a.user_id,
        policy_id="policy_claim_lock_b",
    )

    missing = _mutation_request(
        client=client,
        method=method,
        base_url=_base_url(workspace_a),
        suffix=suffix,
        actor_user_id=owner_a.user_id,
        policy_id="policy_does_not_exist",
    )

    assert cross_workspace.status_code == 404
    assert missing.status_code == 404

    assert cross_workspace.json() == {
        "detail": "policy_not_found",
    }
    assert missing.json() == {
        "detail": "policy_not_found",
    }
    assert cross_workspace.json() == missing.json()

    after_b = repository.get_by_id(
        "policy_claim_lock_b"
    )

    assert after_b == before_b
    assert (
        repository.get_for_workspace(
            workspace_b.workspace_id
        )
        == before_b
    )

    assert (
        repository.get_for_workspace(
            workspace_a.workspace_id
        )
        is None
    )
