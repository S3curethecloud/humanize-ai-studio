from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)

import pytest
from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.core.settings import (
    ProviderName,
    Settings,
)
from app.domain.models import (
    DocumentType,
    RewriteIntensity,
    RewriteRequest,
)
from app.main import app
from app.v2.api.dependencies import (
    V2Services,
)
from app.v2.api.evidence_access import (
    EVIDENCE_BEARER_TOKEN_ENV,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
    ProviderTargetDeclarationSettings,
)
from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingOperationKind,
)
from app.v2.domain.enterprise_provider_routing_policy import (
    EnterpriseProviderRoutingPolicyStatus,
    EnterpriseWorkspaceProviderRoutingPolicy,
)
from app.v2.domain.provider_routing import (
    FallbackPolicy,
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


TARGET_ID = "deterministic-primary"

PROVIDER_REQUIRED_TEXT = (
    "The policy engine evaluates every proposed "
    "tool call before execution."
)


def _provider_settings(
) -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/test/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )


def _persistence_settings(
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _target_settings(
) -> ProviderTargetDeclarationSettings:
    return ProviderTargetDeclarationSettings(
        targets=(
            ProviderModelTarget(
                target_id=TARGET_ID,
                provider=ProviderIdentity(
                    provider_id=(
                        DETERMINISTIC_PROVIDER_ID
                    ),
                    display_name="Deterministic",
                ),
                model=ModelIdentity(
                    provider_id=(
                        DETERMINISTIC_PROVIDER_ID
                    ),
                    model_id=(
                        DETERMINISTIC_MODEL_ID
                    ),
                ),
                capabilities=(
                    ProviderModelCapabilities(
                        capabilities=frozenset(
                            {
                                ProviderCapability.REWRITE,
                                ProviderCapability.CLAIM_LOCK,
                            }
                        ),
                    )
                ),
                enabled=True,
            ),
        ),
    )


@pytest.fixture
def services(
    monkeypatch: pytest.MonkeyPatch,
) -> V2Services:
    monkeypatch.delenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        raising=False,
    )

    monkeypatch.delenv(
        EVIDENCE_BEARER_TOKEN_ENV,
        raising=False,
    )

    test_services = V2Services(
        persistence_settings=(
            _persistence_settings()
        ),
        provider_settings=(
            _provider_settings()
        ),
        provider_target_settings=(
            _target_settings()
        ),
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        test_services,
    )

    return test_services


@pytest.fixture
def client(
) -> TestClient:
    return TestClient(
        app
    )


def _provision_workspace(
    services: V2Services,
    *,
    label: str,
) -> tuple[
    str,
    str,
]:
    user = services.workspace.create_user(
        email=(
            f"routing-r6c2-{label}@example.com"
        ),
        display_name=(
            f"Routing R6C2 {label}"
        ),
    )

    workspace = (
        services.workspace_provisioning
        .create_workspace(
            user_id=user.user_id,
            name=(
                f"Routing R6C2 {label}"
            ),
        )
    )

    return (
        user.user_id,
        workspace.workspace_id,
    )


def _create_active_policy(
    services: V2Services,
    *,
    workspace_id: str,
    user_id: str,
) -> EnterpriseWorkspaceProviderRoutingPolicy:
    repository = (
        services.enterprise_provider_routing_policies
    )

    assert repository is not None

    now = datetime.now(
        UTC
    )

    policy = (
        EnterpriseWorkspaceProviderRoutingPolicy(
            policy_id=(
                f"routing-policy-{workspace_id}"
            ),
            workspace_id=workspace_id,
            status=(
                EnterpriseProviderRoutingPolicyStatus.ACTIVE
            ),
            ordered_target_ids=(
                TARGET_ID,
            ),
            fallback_policy=FallbackPolicy(),
            created_by_user_id=user_id,
            created_at=now,
            updated_by_user_id=user_id,
            updated_at=now,
            revision=1,
        )
    )

    return repository.create(
        policy
    )


def _provider_required_request(
) -> RewriteRequest:
    return RewriteRequest(
        text=PROVIDER_REQUIRED_TEXT,
        document_type=DocumentType.GENERAL,
        audience="engineering leadership",
        tone="natural and clear",
        intensity=(
            RewriteIntensity.NATURAL_REWRITE
        ),
        preserve_numbers=True,
        preserve_dates=True,
    )


def _start_operation(
    services: V2Services,
    *,
    workspace_id: str,
    user_id: str,
):
    operation_service = (
        services
        .enterprise_provider_routing_operation_service
    )

    assert operation_service is not None

    return operation_service.start(
        workspace_id=workspace_id,
        user_id=user_id,
        operation_kind=(
            EnterpriseProviderRoutingOperationKind
            .SINGLE_REWRITE
        ),
        policy_id=(
            f"routing-policy-{workspace_id}"
        ),
        policy_revision=1,
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
            }
        ),
    )


def test_list_and_get_expose_authoritative_recorded_routing_execution_without_platform_bearer(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="recorded",
        )
    )

    policy = _create_active_policy(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    rewrite_result = (
        services.rewrite.execute(
            workspace_id=workspace_id,
            user_id=user_id,
            request=(
                _provider_required_request()
            ),
        )
    )

    assert (
        rewrite_result.response
        .rewrite_necessity
        .provider_required
        is True
    )

    list_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/routing-executions"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert list_response.status_code == 200

    body = list_response.json()

    assert body["workspace_id"] == workspace_id
    assert len(body["records"]) == 1

    record = body["records"][0]
    operation = record["operation"]

    assert (
        operation["workspace_id"]
        == workspace_id
    )

    assert (
        operation["policy_id"]
        == policy.policy_id
    )

    assert (
        operation["status"]
        == "succeeded"
    )

    assert (
        operation["rewrite_history_id"]
        == rewrite_result.history.rewrite_id
    )

    assert len(record["bindings"]) == 1

    binding_view = record["bindings"][0]

    assert (
        binding_view["binding"]["status"]
        == "recorded"
    )

    assert (
        binding_view["routing_evidence"]
        is not None
    )

    assert (
        binding_view[
            "routing_evidence"
        ]["evidence_id"]
        == binding_view[
            "binding"
        ]["evidence_id"]
    )

    assert (
        binding_view[
            "routing_evidence"
        ]["execution_outcome"]
        == "succeeded"
    )

    operation_id = (
        operation["operation_id"]
    )

    get_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/routing-executions/"
            f"{operation_id}"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert get_response.status_code == 200
    assert (
        get_response.json()
        == record
    )


def test_reserved_binding_is_exposed_with_explicit_null_without_fabricating_platform_evidence(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="reserved",
        )
    )

    operation = _start_operation(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    operation_service = (
        services
        .enterprise_provider_routing_operation_service
    )

    assert operation_service is not None

    evidence_id = (
        "routing-evidence-reserved-r6c2"
    )

    operation_service.reserve_routing_evidence(
        operation_id=operation.operation_id,
        evidence_id=evidence_id,
    )

    operation_service.complete_failure(
        operation_id=operation.operation_id,
        failure_code=(
            "simulated_pre_evidence_failure"
        ),
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/routing-executions/"
            f"{operation.operation_id}"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["operation"]["status"]
        == "failed"
    )

    assert len(body["bindings"]) == 1

    binding_view = body["bindings"][0]

    assert (
        binding_view["binding"]["evidence_id"]
        == evidence_id
    )

    assert (
        binding_view["binding"]["status"]
        == "reserved"
    )

    assert "routing_evidence" in binding_view

    assert (
        binding_view["routing_evidence"]
        is None
    )


def test_cross_tenant_workspace_read_is_denied_before_evidence_disclosure(
    services: V2Services,
    client: TestClient,
) -> None:
    user_a_id, _workspace_a_id = (
        _provision_workspace(
            services,
            label="tenant-a",
        )
    )

    _user_b_id, workspace_b_id = (
        _provision_workspace(
            services,
            label="tenant-b",
        )
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_b_id}/routing-executions"
        ),
        params={
            "user_id": user_a_id,
        },
    )

    assert response.status_code == 403

    assert (
        response.json()["detail"]
        == "membership_not_found"
    )

    assert "records" not in response.json()


def test_missing_and_foreign_operation_use_identical_not_found_semantics(
    services: V2Services,
    client: TestClient,
) -> None:
    user_a_id, workspace_a_id = (
        _provision_workspace(
            services,
            label="not-found-a",
        )
    )

    user_b_id, workspace_b_id = (
        _provision_workspace(
            services,
            label="not-found-b",
        )
    )

    foreign_operation = (
        _start_operation(
            services,
            workspace_id=workspace_b_id,
            user_id=user_b_id,
        )
    )

    missing_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_a_id}/routing-executions/"
            f"missing-operation"
        ),
        params={
            "user_id": user_a_id,
        },
    )

    foreign_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_a_id}/routing-executions/"
            f"{foreign_operation.operation_id}"
        ),
        params={
            "user_id": user_a_id,
        },
    )

    assert (
        missing_response.status_code
        == 404
    )

    assert (
        foreign_response.status_code
        == 404
    )

    assert (
        missing_response.json()
        == foreign_response.json()
        == {
            "detail": (
                "routing_execution_not_found"
            )
        }
    )


def test_recorded_binding_without_platform_evidence_fails_closed_at_http_boundary(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="integrity",
        )
    )

    operation = _start_operation(
        services,
        workspace_id=workspace_id,
        user_id=user_id,
    )

    operation_service = (
        services
        .enterprise_provider_routing_operation_service
    )

    assert operation_service is not None

    evidence_id = (
        "routing-evidence-missing-r6c2"
    )

    operation_service.reserve_routing_evidence(
        operation_id=operation.operation_id,
        evidence_id=evidence_id,
    )

    operation_service.confirm_routing_evidence(
        operation_id=operation.operation_id,
        evidence_id=evidence_id,
    )

    operation_service.complete_failure(
        operation_id=operation.operation_id,
        failure_code=(
            "simulated_corrupt_evidence_link"
        ),
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/routing-executions/"
            f"{operation.operation_id}"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": (
            "workspace_routing_execution_"
            "evidence_integrity_error"
        )
    }


@pytest.mark.parametrize(
    "limit",
    (
        0,
        101,
    ),
)
def test_workspace_routing_execution_list_rejects_out_of_contract_limits(
    services: V2Services,
    client: TestClient,
    limit: int,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label=f"limit-{limit}",
        )
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/routing-executions"
        ),
        params={
            "user_id": user_id,
            "limit": limit,
        },
    )

    assert response.status_code == 422


def test_workspace_routing_execution_routes_require_user_identity(
    services: V2Services,
    client: TestClient,
) -> None:
    _user_id, workspace_id = (
        _provision_workspace(
            services,
            label="identity",
        )
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/routing-executions"
        )
    )

    assert response.status_code == 422


def test_workspace_routing_execution_surface_is_get_only(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="get-only",
        )
    )

    response = client.post(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/routing-executions"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 405
