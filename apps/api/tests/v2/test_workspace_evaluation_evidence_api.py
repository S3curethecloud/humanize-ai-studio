from __future__ import annotations

import json
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.core.settings import (
    ProviderName,
    Settings,
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
from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseEvaluationEvidenceBindingStatus,
    EnterpriseEvaluationEvidenceKind,
    EnterpriseEvaluationOperationStatus,
    EnterpriseWorkspaceEvaluationEvidenceBinding,
    EnterpriseWorkspaceEvaluationOperation,
)
from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
)
from app.v2.services.enterprise_evaluation_operation_repository_factory import (
    ExternalEnterpriseEvaluationOperationPersistenceUnavailableError,
    build_enterprise_evaluation_operation_repository,
)
from app.v2.services.provider_execution_factory import (
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
)


NOW = datetime(
    2026,
    9,
    4,
    2,
    0,
    tzinfo=UTC,
)

TARGET_ID = "deterministic-primary"

_BACKENDS = (
    PersistenceBackend.MEMORY,
    PersistenceBackend.SQLITE,
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


def _persistence_settings(
    *,
    backend: PersistenceBackend,
    tmp_path: Path,
) -> V2PersistenceSettings:
    sqlite_path = None

    if backend is PersistenceBackend.SQLITE:
        sqlite_path = (
            tmp_path
            / "i5-workspace-evaluation.sqlite3"
        )

    return V2PersistenceSettings(
        backend=backend,
        sqlite_path=sqlite_path,
        database_url=None,
    )


@pytest.fixture(
    params=_BACKENDS,
    ids=("memory", "sqlite"),
)
def services(
    request: pytest.FixtureRequest,
    tmp_path: Path,
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
            _persistence_settings(
                backend=request.param,
                tmp_path=tmp_path,
            )
        ),
        provider_settings=_provider_settings(),
        provider_target_settings=_target_settings(),
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
) -> tuple[str, str]:
    user = services.workspace.create_user(
        email=f"i5-{label}@example.com",
        display_name=f"I5 {label}",
    )

    workspace = (
        services.workspace_provisioning
        .create_workspace(
            user_id=user.user_id,
            name=f"I5 {label}",
        )
    )

    return (
        user.user_id,
        workspace.workspace_id,
    )


def _replace_operation(
    operation: EnterpriseWorkspaceEvaluationOperation,
    **updates: object,
) -> EnterpriseWorkspaceEvaluationOperation:
    payload = operation.model_dump(
        mode="python"
    )
    payload.update(
        updates
    )

    return (
        EnterpriseWorkspaceEvaluationOperation
        .model_validate(
            payload
        )
    )


def _run_record(
    *,
    label: str,
    outcome: EvaluationRunOutcome,
) -> EvaluationRunRecord:
    if outcome is EvaluationRunOutcome.FAILED:
        return EvaluationRunRecord(
            identity=EvaluationRunIdentity(
                run_id=f"run-{label}",
                dataset=EvaluationDatasetIdentity(
                    dataset_id=f"dataset-{label}",
                    dataset_version="v1",
                ),
                target_id=f"target-{label}",
            ),
            outcome=outcome,
            evaluated_case_count=1,
            failed_case_count=1,
            metric_results=(),
            failure_reason=(
                "simulated evaluation failure"
            ),
        )

    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id=f"run-{label}",
            dataset=EvaluationDatasetIdentity(
                dataset_id=f"dataset-{label}",
                dataset_version="v1",
            ),
            target_id=f"target-{label}",
        ),
        outcome=outcome,
        evaluated_case_count=1,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=(
                    EvaluationMetric
                    .CLAIM_PRESERVATION
                ),
                value=0.95,
            ),
        ),
        failure_reason=None,
    )


def _seed_binding(
    services: V2Services,
    *,
    workspace_id: str,
    actor_user_id: str,
    label: str,
    recorded: bool,
    persist_platform_evidence: bool = True,
    operation_status: (
        EnterpriseEvaluationOperationStatus
    ) = EnterpriseEvaluationOperationStatus.OPEN,
    run_outcome: (
        EvaluationRunOutcome
    ) = EvaluationRunOutcome.SUCCEEDED,
) -> EnterpriseWorkspaceEvaluationEvidenceBinding:
    operation = (
        EnterpriseWorkspaceEvaluationOperation(
            operation_id=f"operation-{label}",
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            run_id=f"run-{label}",
            dataset_id=f"dataset-{label}",
            dataset_version="v1",
            target_id=f"target-{label}",
            requested_metrics=(
                EvaluationMetric.CLAIM_PRESERVATION,
            ),
            status=(
                EnterpriseEvaluationOperationStatus
                .OPEN
            ),
            created_at=NOW,
            updated_at=NOW,
            revision=1,
        )
    )

    services.enterprise_evaluation_operations.create(
        operation
    )

    binding_created_at = (
        NOW + timedelta(seconds=1)
    )

    binding = (
        EnterpriseWorkspaceEvaluationEvidenceBinding(
            binding_id=f"binding-{label}",
            operation_id=operation.operation_id,
            workspace_id=workspace_id,
            evidence_id=f"evidence-{label}",
            evidence_kind=(
                EnterpriseEvaluationEvidenceKind.RUN
            ),
            run_id=operation.run_id,
            status=(
                EnterpriseEvaluationEvidenceBindingStatus
                .RESERVED
            ),
            created_at=binding_created_at,
        )
    )

    reserved_operation = _replace_operation(
        operation,
        evidence_bindings=(binding,),
        updated_at=binding_created_at,
        revision=2,
    )

    services.enterprise_evaluation_operations.update(
        reserved_operation,
        expected_revision=1,
    )

    if not recorded:
        return binding

    if persist_platform_evidence:
        (
            services
            .routing_eval_evidence_repositories
            .evaluation
            .create(
                EvaluationEvidenceRecord(
                    evidence_id=binding.evidence_id,
                    run=_run_record(
                        label=label,
                        outcome=run_outcome,
                    ),
                    observed_at=(
                        NOW + timedelta(seconds=2)
                    ),
                )
            )
        )

    binding_payload = binding.model_dump(
        mode="python"
    )
    binding_payload.update(
        {
            "status": (
                EnterpriseEvaluationEvidenceBindingStatus
                .RECORDED
            ),
            "recorded_at": (
                NOW + timedelta(seconds=3)
            ),
        }
    )

    recorded_binding = (
        EnterpriseWorkspaceEvaluationEvidenceBinding
        .model_validate(
            binding_payload
        )
    )

    recorded_operation = _replace_operation(
        reserved_operation,
        evidence_bindings=(
            recorded_binding,
        ),
        status=operation_status,
        updated_at=(
            NOW + timedelta(seconds=3)
        ),
        revision=3,
    )

    services.enterprise_evaluation_operations.update(
        recorded_operation,
        expected_revision=2,
    )

    return recorded_binding


def test_authorized_list_and_detail_expose_workspace_projection_without_platform_bearer(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="authorized",
        )
    )

    binding = _seed_binding(
        services,
        workspace_id=workspace_id,
        actor_user_id=user_id,
        label="authorized",
        recorded=True,
        operation_status=(
            EnterpriseEvaluationOperationStatus
            .SUCCEEDED
        ),
    )

    list_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert list_response.status_code == 200

    list_body = list_response.json()

    assert list_body["workspace_id"] == workspace_id
    assert len(list_body["records"]) == 1

    record = list_body["records"][0]

    assert record["binding_id"] == binding.binding_id
    assert record["workspace_id"] == workspace_id
    assert record["operation_status"] == "succeeded"
    assert record["evidence_kind"] == "run"

    assert (
        "evidence_id"
        not in json.dumps(
            list_body,
            sort_keys=True,
        )
    )

    detail_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence/"
            f"{binding.binding_id}"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert detail_response.status_code == 200
    assert detail_response.json() == record

    assert (
        "evidence_id"
        not in json.dumps(
            detail_response.json(),
            sort_keys=True,
        )
    )

    platform_response = client.get(
        (
            "/api/v2/evidence/evaluation/"
            f"{binding.evidence_id}"
        )
    )

    assert platform_response.status_code == 404


def test_foreign_principal_list_and_detail_are_403(
    services: V2Services,
    client: TestClient,
) -> None:
    user_a_id, _workspace_a_id = (
        _provision_workspace(
            services,
            label="foreign-principal-a",
        )
    )

    user_b_id, workspace_b_id = (
        _provision_workspace(
            services,
            label="foreign-principal-b",
        )
    )

    binding = _seed_binding(
        services,
        workspace_id=workspace_b_id,
        actor_user_id=user_b_id,
        label="foreign-principal",
        recorded=True,
    )

    list_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_b_id}/evaluation-evidence"
        ),
        params={
            "user_id": user_a_id,
        },
    )

    detail_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_b_id}/evaluation-evidence/"
            f"{binding.binding_id}"
        ),
        params={
            "user_id": user_a_id,
        },
    )

    assert list_response.status_code == 403
    assert detail_response.status_code == 403

    assert list_response.json() == {
        "detail": "membership_not_found"
    }
    assert detail_response.json() == {
        "detail": "membership_not_found"
    }


def test_missing_and_foreign_binding_are_confidentiality_equivalent_404(
    services: V2Services,
    client: TestClient,
) -> None:
    user_a_id, workspace_a_id = (
        _provision_workspace(
            services,
            label="binding-a",
        )
    )

    user_b_id, workspace_b_id = (
        _provision_workspace(
            services,
            label="binding-b",
        )
    )

    foreign_binding = _seed_binding(
        services,
        workspace_id=workspace_b_id,
        actor_user_id=user_b_id,
        label="foreign-binding",
        recorded=True,
    )

    missing_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_a_id}/evaluation-evidence/"
            "missing-binding"
        ),
        params={
            "user_id": user_a_id,
        },
    )

    foreign_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_a_id}/evaluation-evidence/"
            f"{foreign_binding.binding_id}"
        ),
        params={
            "user_id": user_a_id,
        },
    )

    expected = {
        "detail": (
            "workspace_evaluation_evidence_not_found"
        )
    }

    assert missing_response.status_code == 404
    assert foreign_response.status_code == 404

    assert missing_response.json() == expected
    assert foreign_response.json() == expected


def test_reserved_binding_is_404_and_absent_from_list(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="reserved",
        )
    )

    binding = _seed_binding(
        services,
        workspace_id=workspace_id,
        actor_user_id=user_id,
        label="reserved",
        recorded=False,
    )

    detail_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence/"
            f"{binding.binding_id}"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert detail_response.status_code == 404

    assert detail_response.json() == {
        "detail": (
            "workspace_evaluation_evidence_not_found"
        )
    }

    list_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert list_response.status_code == 200
    assert list_response.json() == {
        "workspace_id": workspace_id,
        "records": [],
    }


def test_recorded_binding_missing_platform_evidence_fails_closed_500(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="integrity",
        )
    )

    binding = _seed_binding(
        services,
        workspace_id=workspace_id,
        actor_user_id=user_id,
        label="integrity",
        recorded=True,
        persist_platform_evidence=False,
    )

    detail_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence/"
            f"{binding.binding_id}"
        ),
        params={
            "user_id": user_id,
        },
    )

    list_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence"
        ),
        params={
            "user_id": user_id,
        },
    )

    expected = {
        "detail": (
            "workspace_evaluation_evidence_"
            "integrity_error"
        )
    }

    assert detail_response.status_code == 500
    assert list_response.status_code == 500

    assert detail_response.json() == expected
    assert list_response.json() == expected


def test_workspace_routes_require_user_id(
    services: V2Services,
    client: TestClient,
) -> None:
    _user_id, workspace_id = (
        _provision_workspace(
            services,
            label="identity",
        )
    )

    list_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence"
        )
    )

    detail_response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence/"
            "binding-any"
        )
    )

    assert list_response.status_code == 422
    assert detail_response.status_code == 422


@pytest.mark.parametrize(
    "limit",
    (
        0,
        101,
    ),
)
def test_list_rejects_out_of_contract_limits(
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
            f"{workspace_id}/evaluation-evidence"
        ),
        params={
            "user_id": user_id,
            "limit": limit,
        },
    )

    assert response.status_code == 422


def test_workspace_evaluation_surface_is_get_only(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="get-only",
        )
    )

    list_response = client.post(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence"
        ),
        params={
            "user_id": user_id,
        },
    )

    detail_response = client.post(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence/"
            "binding-any"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert list_response.status_code == 405
    assert detail_response.status_code == 405


def test_operation_success_does_not_conflate_failed_evaluation_outcome(
    services: V2Services,
    client: TestClient,
) -> None:
    user_id, workspace_id = (
        _provision_workspace(
            services,
            label="status-separation",
        )
    )

    binding = _seed_binding(
        services,
        workspace_id=workspace_id,
        actor_user_id=user_id,
        label="status-separation",
        recorded=True,
        operation_status=(
            EnterpriseEvaluationOperationStatus
            .SUCCEEDED
        ),
        run_outcome=(
            EvaluationRunOutcome.FAILED
        ),
    )

    response = client.get(
        (
            f"/api/v2/workspaces/"
            f"{workspace_id}/evaluation-evidence/"
            f"{binding.binding_id}"
        ),
        params={
            "user_id": user_id,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["operation_status"] == "succeeded"
    assert body["run"]["outcome"] == "failed"
    assert (
        body["run"]["failure_reason"]
        == "simulated evaluation failure"
    )


def test_external_operation_repository_factory_fails_closed(
) -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url=(
            "postgresql://example.invalid/humanize"
        ),
    )

    with pytest.raises(
        ExternalEnterpriseEvaluationOperationPersistenceUnavailableError,
    ):
        build_enterprise_evaluation_operation_repository(
            settings
        )
