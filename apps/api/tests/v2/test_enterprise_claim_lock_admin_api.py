from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)
from app.v2.services.enterprise_claim_lock_admin_service import (
    ClaimLockAdministrationFailureReason,
    EnterpriseClaimLockAdministrationError,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _memory_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _policy(
    *,
    policy_id: str = "policy_test",
    workspace_id: str = "workspace_test",
    status: EnterpriseClaimLockPolicyStatus = (
        EnterpriseClaimLockPolicyStatus.ACTIVE
    ),
    enforcement_mode: ClaimLockEnforcementMode = (
        ClaimLockEnforcementMode.STRICT
    ),
    revision: int = 1,
    term_id: str = "term_customer",
    term_text: str = "Customer Alpha",
    case_sensitive: bool = True,
) -> EnterpriseWorkspaceClaimLockPolicy:
    timestamp = datetime(
        2026,
        8,
        24,
        12,
        0,
        tzinfo=UTC,
    )

    source_reference = (
        "workspace-claim-lock-policy:"
        f"{policy_id}:revision:{revision}"
    )

    return EnterpriseWorkspaceClaimLockPolicy(
        policy_id=policy_id,
        workspace_id=workspace_id,
        status=status,
        enforcement_mode=enforcement_mode,
        protected_terms=(
            ProtectedTerm(
                term_id=term_id,
                text=term_text,
                case_sensitive=case_sensitive,
                provenance=ClaimLockProvenance(
                    origin=ClaimLockOrigin.WORKSPACE,
                    source_reference=source_reference,
                ),
            ),
        ),
        created_by_user_id="user_admin",
        created_at=timestamp,
        updated_by_user_id="user_admin",
        updated_at=timestamp,
        revision=revision,
    )


def _create_payload(
    *,
    policy_id: str = "policy_test",
) -> dict[str, object]:
    return {
        "actor_user_id": "user_admin",
        "policy_id": policy_id,
        "enforcement_mode": "strict",
        "protected_terms": [
            {
                "term_id": "term_customer",
                "text": "Customer Alpha",
            },
        ],
    }


def _update_payload() -> dict[str, object]:
    return {
        "actor_user_id": "user_admin",
        "policy_id": "policy_test",
        "expected_revision": 1,
        "enforcement_mode": "audit_only",
        "protected_terms": [
            {
                "term_id": "term_account",
                "text": "Account 8842",
                "case_sensitive": False,
            },
        ],
    }


def _lifecycle_payload() -> dict[str, object]:
    return {
        "actor_user_id": "user_admin",
        "policy_id": "policy_test",
        "expected_revision": 1,
    }


def _mock_claim_lock_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> MagicMock:
    container = MagicMock()
    admin = MagicMock()
    container.claim_lock_admin = admin

    monkeypatch.setattr(
        v2_routes,
        "services",
        container,
    )

    return admin


def _seed_workspace_owner(
    services: V2Services,
) -> tuple[
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
]:
    runtime = services.enterprise_authorization

    organization = EnterpriseOrganization(
        organization_id="org_claim_lock_http",
        name="Claim Lock HTTP Organization",
        created_by_user_id="user_owner",
    )

    workspace = EnterpriseWorkspace(
        workspace_id="workspace_claim_lock_http",
        organization_id=organization.organization_id,
        name="Claim Lock HTTP Workspace",
        created_by_user_id="user_owner",
    )

    owner = EnterpriseWorkspaceMembership(
        membership_id="membership_claim_lock_owner",
        organization_id=organization.organization_id,
        workspace_id=workspace.workspace_id,
        user_id="user_owner",
        role=EnterpriseWorkspaceRole.OWNER,
    )

    runtime.organizations.create(organization)
    runtime.workspaces.create(workspace)
    runtime.memberships.create(owner)

    return workspace, owner


def test_full_claim_lock_administration_lifecycle_over_http(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    services = V2Services(
        persistence_settings=_memory_settings(),
    )

    workspace, owner = _seed_workspace_owner(services)

    monkeypatch.setattr(
        v2_routes,
        "services",
        services,
    )

    base_url = (
        f"/api/v2/workspaces/{workspace.workspace_id}"
        "/claim-lock-policy"
    )

    created = client.post(
        base_url,
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_primary",
            "enforcement_mode": "strict",
            "protected_terms": [
                {
                    "term_id": "term_primary",
                    "text": "Customer Alpha",
                },
            ],
        },
    )

    assert created.status_code == 201

    created_policy = created.json()["policy"]

    assert created_policy["policy_id"] == "policy_primary"
    assert created_policy["workspace_id"] == workspace.workspace_id
    assert created_policy["status"] == "active"
    assert created_policy["enforcement_mode"] == "strict"
    assert created_policy["revision"] == 1

    created_term = created_policy["protected_terms"][0]

    assert created_term["term_id"] == "term_primary"
    assert created_term["case_sensitive"] is True
    assert created_term["provenance"]["origin"] == "workspace"
    assert (
        created_term["provenance"]["source_reference"]
        == (
            "workspace-claim-lock-policy:"
            "policy_primary:revision:1"
        )
    )

    fetched = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert fetched.status_code == 200
    assert fetched.json()["policy"] == created_policy

    updated = client.patch(
        base_url,
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_primary",
            "expected_revision": 1,
            "enforcement_mode": "audit_only",
            "protected_terms": [
                {
                    "term_id": "term_replacement",
                    "text": "Account 8842",
                    "case_sensitive": False,
                },
            ],
        },
    )

    assert updated.status_code == 200

    updated_policy = updated.json()["policy"]

    assert updated_policy["policy_id"] == "policy_primary"
    assert updated_policy["status"] == "active"
    assert updated_policy["enforcement_mode"] == "audit_only"
    assert updated_policy["revision"] == 2
    assert len(updated_policy["protected_terms"]) == 1

    updated_term = updated_policy["protected_terms"][0]

    assert updated_term["term_id"] == "term_replacement"
    assert updated_term["text"] == "Account 8842"
    assert updated_term["case_sensitive"] is False
    assert (
        updated_term["provenance"]["source_reference"]
        == (
            "workspace-claim-lock-policy:"
            "policy_primary:revision:2"
        )
    )

    disabled = client.post(
        f"{base_url}/disable",
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_primary",
            "expected_revision": 2,
        },
    )

    assert disabled.status_code == 200
    assert disabled.json()["policy"]["status"] == "disabled"
    assert disabled.json()["policy"]["revision"] == 3

    enabled = client.post(
        f"{base_url}/enable",
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_primary",
            "expected_revision": 3,
        },
    )

    assert enabled.status_code == 200
    assert enabled.json()["policy"]["status"] == "active"
    assert enabled.json()["policy"]["revision"] == 4

    archived = client.post(
        f"{base_url}/archive",
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_primary",
            "expected_revision": 4,
        },
    )

    assert archived.status_code == 200
    assert archived.json()["policy"]["status"] == "archived"
    assert archived.json()["policy"]["revision"] == 5

    after_archive = client.get(
        base_url,
        params={
            "actor_user_id": owner.user_id,
        },
    )

    assert after_archive.status_code == 404
    assert after_archive.json()["detail"] == "policy_not_found"

    replacement = client.post(
        base_url,
        json={
            "actor_user_id": owner.user_id,
            "policy_id": "policy_replacement",
            "enforcement_mode": "strict",
            "protected_terms": [],
        },
    )

    assert replacement.status_code == 201

    replacement_policy = replacement.json()["policy"]

    assert replacement_policy["policy_id"] == "policy_replacement"
    assert replacement_policy["status"] == "active"
    assert replacement_policy["revision"] == 1


def test_get_claim_lock_policy_requires_actor_identity(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    response = client.get(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
    )

    assert response.status_code == 422
    admin.get_policy.assert_not_called()


def test_get_claim_lock_policy_delegates_to_admin_service(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    admin.get_policy.return_value = _policy()

    response = client.get(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        params={
            "actor_user_id": "user_viewer",
        },
    )

    assert response.status_code == 200
    assert response.json()["policy"]["policy_id"] == "policy_test"

    admin.get_policy.assert_called_once_with(
        actor_user_id="user_viewer",
        workspace_id="workspace_test",
    )


def test_create_claim_lock_policy_binds_workspace_path_and_terms(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    admin.create_policy.return_value = _policy()

    response = client.post(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        json=_create_payload(),
    )

    assert response.status_code == 201
    assert response.json()["policy"]["workspace_id"] == (
        "workspace_test"
    )

    admin.create_policy.assert_called_once()

    call = admin.create_policy.call_args

    assert call.kwargs["actor_user_id"] == "user_admin"
    assert call.kwargs["workspace_id"] == "workspace_test"
    assert call.kwargs["policy_id"] == "policy_test"
    assert (
        call.kwargs["enforcement_mode"]
        is ClaimLockEnforcementMode.STRICT
    )
    assert (
        call.kwargs["status"]
        is EnterpriseClaimLockPolicyStatus.ACTIVE
    )
    assert call.kwargs["protected_terms"] == (
        {
            "term_id": "term_customer",
            "text": "Customer Alpha",
            "case_sensitive": True,
        },
    )


def test_create_claim_lock_policy_rejects_body_workspace_id(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    payload = _create_payload()
    payload["workspace_id"] = "workspace_other"

    response = client.post(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        json=payload,
    )

    assert response.status_code == 422
    admin.create_policy.assert_not_called()


def test_create_claim_lock_policy_rejects_client_provenance(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    payload = _create_payload()

    protected_terms = payload["protected_terms"]

    assert isinstance(protected_terms, list)
    assert isinstance(protected_terms[0], dict)

    protected_terms[0]["provenance"] = {
        "origin": "workspace",
        "source_reference": "forged",
    }

    response = client.post(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        json=payload,
    )

    assert response.status_code == 422
    admin.create_policy.assert_not_called()


@pytest.mark.parametrize(
    "missing_field",
    (
        "enforcement_mode",
        "protected_terms",
    ),
)
def test_update_claim_lock_policy_requires_complete_replacement_fields(
    missing_field: str,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    payload = _update_payload()
    del payload[missing_field]

    response = client.patch(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        json=payload,
    )

    assert response.status_code == 422
    admin.update_policy.assert_not_called()


def test_update_claim_lock_policy_delegates_complete_replacement(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    admin.update_policy.return_value = _policy(
        revision=2,
        enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
        term_id="term_account",
        term_text="Account 8842",
        case_sensitive=False,
    )

    response = client.patch(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        json=_update_payload(),
    )

    assert response.status_code == 200

    admin.update_policy.assert_called_once_with(
        actor_user_id="user_admin",
        workspace_id="workspace_test",
        policy_id="policy_test",
        expected_revision=1,
        enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
        protected_terms=(
            {
                "term_id": "term_account",
                "text": "Account 8842",
                "case_sensitive": False,
            },
        ),
    )


@pytest.mark.parametrize(
    ("suffix", "method_name", "returned_status"),
    (
        (
            "enable",
            "enable_policy",
            EnterpriseClaimLockPolicyStatus.ACTIVE,
        ),
        (
            "disable",
            "disable_policy",
            EnterpriseClaimLockPolicyStatus.DISABLED,
        ),
        (
            "archive",
            "archive_policy",
            EnterpriseClaimLockPolicyStatus.ARCHIVED,
        ),
    ),
)
def test_claim_lock_lifecycle_routes_delegate_exactly(
    suffix: str,
    method_name: str,
    returned_status: EnterpriseClaimLockPolicyStatus,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)
    method = getattr(admin, method_name)

    method.return_value = _policy(
        status=returned_status,
        revision=2,
    )

    response = client.post(
        (
            "/api/v2/workspaces/workspace_test/"
            f"claim-lock-policy/{suffix}"
        ),
        json=_lifecycle_payload(),
    )

    assert response.status_code == 200
    assert response.json()["policy"]["status"] == (
        returned_status.value
    )

    method.assert_called_once_with(
        actor_user_id="user_admin",
        workspace_id="workspace_test",
        policy_id="policy_test",
        expected_revision=1,
    )


@pytest.mark.parametrize(
    "missing_field",
    (
        "policy_id",
        "expected_revision",
    ),
)
def test_claim_lock_lifecycle_requires_target_and_revision(
    missing_field: str,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    payload = _lifecycle_payload()
    del payload[missing_field]

    response = client.post(
        (
            "/api/v2/workspaces/workspace_test/"
            "claim-lock-policy/disable"
        ),
        json=payload,
    )

    assert response.status_code == 422
    admin.disable_policy.assert_not_called()


@pytest.mark.parametrize(
    ("reason", "expected_status", "expected_detail"),
    (
        (
            ClaimLockAdministrationFailureReason
            .AUTHORIZATION_RESOLUTION_FAILED,
            403,
            "authorization_resolution_failed",
        ),
        (
            ClaimLockAdministrationFailureReason
            .AUTHORIZATION_DENIED,
            403,
            "authorization_denied",
        ),
        (
            ClaimLockAdministrationFailureReason.POLICY_NOT_FOUND,
            404,
            "policy_not_found",
        ),
        (
            ClaimLockAdministrationFailureReason
            .POLICY_SCOPE_MISMATCH,
            404,
            "policy_not_found",
        ),
        (
            ClaimLockAdministrationFailureReason
            .POLICY_ALREADY_EXISTS,
            409,
            "policy_already_exists",
        ),
        (
            ClaimLockAdministrationFailureReason.POLICY_ARCHIVED,
            409,
            "policy_archived",
        ),
        (
            ClaimLockAdministrationFailureReason.POLICY_NOT_ACTIVE,
            409,
            "policy_not_active",
        ),
        (
            ClaimLockAdministrationFailureReason
            .POLICY_ALREADY_ACTIVE,
            409,
            "policy_already_active",
        ),
        (
            ClaimLockAdministrationFailureReason
            .POLICY_ALREADY_DISABLED,
            409,
            "policy_already_disabled",
        ),
        (
            ClaimLockAdministrationFailureReason.REVISION_CONFLICT,
            409,
            "revision_conflict",
        ),
        (
            ClaimLockAdministrationFailureReason
            .INVALID_WORKSPACE_TERM,
            422,
            "invalid_workspace_term",
        ),
        (
            ClaimLockAdministrationFailureReason
            .PERSISTENCE_REJECTED,
            500,
            "persistence_rejected",
        ),
        (
            ClaimLockAdministrationFailureReason
            .TRANSACTION_REQUIRED,
            500,
            "transaction_required",
        ),
    ),
)
def test_claim_lock_http_failure_matrix(
    reason: ClaimLockAdministrationFailureReason,
    expected_status: int,
    expected_detail: str,
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    admin.get_policy.side_effect = (
        EnterpriseClaimLockAdministrationError(reason)
    )

    response = client.get(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        params={
            "actor_user_id": "user_actor",
        },
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_scope_mismatch_is_publicly_identical_to_not_found(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    admin = _mock_claim_lock_admin(monkeypatch)

    admin.get_policy.side_effect = (
        EnterpriseClaimLockAdministrationError(
            ClaimLockAdministrationFailureReason
            .POLICY_SCOPE_MISMATCH
        )
    )

    scope_mismatch = client.get(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        params={
            "actor_user_id": "user_actor",
        },
    )

    admin.get_policy.side_effect = (
        EnterpriseClaimLockAdministrationError(
            ClaimLockAdministrationFailureReason
            .POLICY_NOT_FOUND
        )
    )

    not_found = client.get(
        "/api/v2/workspaces/workspace_test/claim-lock-policy",
        params={
            "actor_user_id": "user_actor",
        },
    )

    assert scope_mismatch.status_code == 404
    assert not_found.status_code == 404
    assert scope_mismatch.json() == not_found.json()
    assert scope_mismatch.json() == {
        "detail": "policy_not_found",
    }
