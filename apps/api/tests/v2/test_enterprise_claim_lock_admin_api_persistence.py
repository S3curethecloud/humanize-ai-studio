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
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
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
    workspace_id: str = "workspace_claim_lock_persist",
    organization_id: str = "org_claim_lock_persist",
    owner_user_id: str = "user_owner_persist",
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
]:
    runtime = services.enterprise_authorization

    organization = EnterpriseOrganization(
        organization_id=organization_id,
        name="Persistent Claim Lock Organization",
        created_by_user_id=owner_user_id,
    )

    workspace = EnterpriseWorkspace(
        workspace_id=workspace_id,
        organization_id=organization.organization_id,
        name="Persistent Claim Lock Workspace",
        created_by_user_id=owner_user_id,
    )

    owner = EnterpriseWorkspaceMembership(
        membership_id="membership_claim_lock_owner_persist",
        organization_id=organization.organization_id,
        workspace_id=workspace.workspace_id,
        user_id=owner_user_id,
        role=EnterpriseWorkspaceRole.OWNER,
    )

    runtime.organizations.create(organization)
    runtime.workspaces.create(workspace)
    runtime.memberships.create(owner)

    return workspace, owner


def _base_url(
    workspace: EnterpriseWorkspace,
) -> str:
    return (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        "/claim-lock-policy"
    )


def _create_policy(
    *,
    client: TestClient,
    workspace: EnterpriseWorkspace,
    owner: EnterpriseWorkspaceMembership,
    policy_id: str = "policy_persist",
) -> dict[str, object]:
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


def test_created_policy_survives_sqlite_runtime_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "claim-lock-create.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    _install_services(
        monkeypatch,
        initial,
    )

    created = _create_policy(
        client=client,
        workspace=workspace,
        owner=owner,
    )

    assert created["policy_id"] == "policy_persist"
    assert created["status"] == "active"
    assert created["enforcement_mode"] == "strict"
    assert created["revision"] == 1

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    response = client.get(
        _base_url(workspace),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert response.status_code == 200

    persisted = response.json()["policy"]

    assert persisted == created
    assert persisted["workspace_id"] == workspace.workspace_id
    assert persisted["revision"] == 1

    term = persisted["protected_terms"][0]

    assert term["provenance"]["origin"] == "workspace"
    assert (
        term["provenance"]["source_reference"]
        == (
            "workspace-claim-lock-policy:"
            "policy_persist:revision:1"
        )
    )


def test_update_disable_enable_survive_successive_sqlite_restarts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "claim-lock-lifecycle.db"

    current = _services(database_path)
    workspace, owner = _seed_workspace(current)

    _install_services(
        monkeypatch,
        current,
    )

    _create_policy(
        client=client,
        workspace=workspace,
        owner=owner,
    )

    current = _services(database_path)

    _install_services(
        monkeypatch,
        current,
    )

    updated = client.patch(
        _base_url(workspace),
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_persist",
            "expected_revision": 1,
            "enforcement_mode": "audit_only",
            "protected_terms": [
                {
                    "term_id": "term_account",
                    "text": "Account 8842",
                    "case_sensitive": False,
                },
            ],
        },
    )

    assert updated.status_code == 200

    updated_policy = updated.json()["policy"]

    assert updated_policy["revision"] == 2
    assert updated_policy["status"] == "active"
    assert updated_policy["enforcement_mode"] == "audit_only"
    assert len(updated_policy["protected_terms"]) == 1
    assert (
        updated_policy["protected_terms"][0]["term_id"]
        == "term_account"
    )
    assert (
        updated_policy["protected_terms"][0]
        ["provenance"]["source_reference"]
        == (
            "workspace-claim-lock-policy:"
            "policy_persist:revision:2"
        )
    )

    current = _services(database_path)

    _install_services(
        monkeypatch,
        current,
    )

    after_update = client.get(
        _base_url(workspace),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert after_update.status_code == 200
    assert after_update.json()["policy"] == updated_policy

    disabled = client.post(
        f"{_base_url(workspace)}/disable",
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_persist",
            "expected_revision": 2,
        },
    )

    assert disabled.status_code == 200
    assert disabled.json()["policy"]["status"] == "disabled"
    assert disabled.json()["policy"]["revision"] == 3

    current = _services(database_path)

    _install_services(
        monkeypatch,
        current,
    )

    after_disable = client.get(
        _base_url(workspace),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert after_disable.status_code == 200
    assert after_disable.json()["policy"]["status"] == "disabled"
    assert after_disable.json()["policy"]["revision"] == 3

    enabled = client.post(
        f"{_base_url(workspace)}/enable",
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_persist",
            "expected_revision": 3,
        },
    )

    assert enabled.status_code == 200
    assert enabled.json()["policy"]["status"] == "active"
    assert enabled.json()["policy"]["revision"] == 4

    current = _services(database_path)

    _install_services(
        monkeypatch,
        current,
    )

    after_enable = client.get(
        _base_url(workspace),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert after_enable.status_code == 200
    assert after_enable.json()["policy"]["status"] == "active"
    assert after_enable.json()["policy"]["revision"] == 4


def test_stale_revision_after_restart_conflicts_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "claim-lock-revision.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    _install_services(
        monkeypatch,
        initial,
    )

    _create_policy(
        client=client,
        workspace=workspace,
        owner=owner,
    )

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    updated = client.patch(
        _base_url(workspace),
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_persist",
            "expected_revision": 1,
            "enforcement_mode": "audit_only",
            "protected_terms": [],
        },
    )

    assert updated.status_code == 200
    assert updated.json()["policy"]["revision"] == 2
    assert updated.json()["policy"]["status"] == "active"

    restarted_again = _services(database_path)

    _install_services(
        monkeypatch,
        restarted_again,
    )

    stale = client.post(
        f"{_base_url(workspace)}/disable",
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_persist",
            "expected_revision": 1,
        },
    )

    assert stale.status_code == 409
    assert stale.json()["detail"] == "revision_conflict"

    persisted = client.get(
        _base_url(workspace),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert persisted.status_code == 200
    assert persisted.json()["policy"]["revision"] == 2
    assert persisted.json()["policy"]["status"] == "active"
    assert (
        persisted.json()["policy"]["enforcement_mode"]
        == "audit_only"
    )


def test_archive_survives_restart_and_allows_new_revision_one_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    database_path = tmp_path / "claim-lock-archive.db"

    initial = _services(database_path)
    workspace, owner = _seed_workspace(initial)

    _install_services(
        monkeypatch,
        initial,
    )

    _create_policy(
        client=client,
        workspace=workspace,
        owner=owner,
        policy_id="policy_archived",
    )

    archived = client.post(
        f"{_base_url(workspace)}/archive",
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_archived",
            "expected_revision": 1,
        },
    )

    assert archived.status_code == 200

    archived_payload = archived.json()["policy"]

    assert archived_payload["status"] == "archived"
    assert archived_payload["revision"] == 2

    restarted = _services(database_path)

    _install_services(
        monkeypatch,
        restarted,
    )

    current = client.get(
        _base_url(workspace),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert current.status_code == 404
    assert current.json()["detail"] == "policy_not_found"

    historical = (
        restarted.enterprise_claim_lock_policies.get_by_id(
            "policy_archived"
        )
    )

    assert historical is not None
    assert (
        historical.status
        is EnterpriseClaimLockPolicyStatus.ARCHIVED
    )
    assert historical.revision == 2
    assert historical.workspace_id == workspace.workspace_id

    replacement = client.post(
        _base_url(workspace),
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_replacement",
            "enforcement_mode": "audit_only",
            "protected_terms": [
                {
                    "term_id": "term_replacement",
                    "text": "Replacement Value",
                },
            ],
        },
    )

    assert replacement.status_code == 201

    replacement_payload = replacement.json()["policy"]

    assert replacement_payload["policy_id"] == (
        "policy_replacement"
    )
    assert replacement_payload["status"] == "active"
    assert replacement_payload["revision"] == 1

    restarted_again = _services(database_path)

    _install_services(
        monkeypatch,
        restarted_again,
    )

    persisted_replacement = client.get(
        _base_url(workspace),
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert persisted_replacement.status_code == 200
    assert (
        persisted_replacement.json()["policy"]
        == replacement_payload
    )

    persisted_historical = (
        restarted_again.enterprise_claim_lock_policies.get_by_id(
            "policy_archived"
        )
    )

    assert persisted_historical is not None
    assert (
        persisted_historical.status
        is EnterpriseClaimLockPolicyStatus.ARCHIVED
    )
    assert persisted_historical.revision == 2
