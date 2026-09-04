from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseEvaluationEvidenceBindingStatus,
    EnterpriseEvaluationEvidenceKind,
    EnterpriseEvaluationOperationStatus,
    EnterpriseWorkspaceEvaluationEvidenceBinding,
    EnterpriseWorkspaceEvaluationOperation,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseOrganization,
    EnterpriseWorkspace,
    EnterpriseWorkspaceMembership,
    EnterpriseWorkspaceRole,
)
from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
)
from app.v2.repositories.enterprise_evaluation_operations import (
    InMemoryEnterpriseWorkspaceEvaluationOperationRepository,
)
from app.v2.repositories.enterprise_evaluation_operations_sqlite import (
    SQLiteEnterpriseWorkspaceEvaluationOperationRepository,
)
from app.v2.services.enterprise_authorization_runtime_factory import (
    build_enterprise_authorization_runtime,
)
from app.v2.services.routing_eval_evidence_factory import (
    build_routing_eval_evidence_repositories,
)
from app.v2.services.routing_eval_evidence_query_service import (
    EvaluationEvidenceQueryService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)
from app.v2.services.workspace_evaluation_evidence_query_service import (
    WorkspaceEvaluationEvidenceQueryService,
)


NOW = datetime(
    2026,
    9,
    4,
    1,
    0,
    tzinfo=UTC,
)

_BACKENDS = (
    PersistenceBackend.MEMORY,
    PersistenceBackend.SQLITE,
)


class _OperationReadProbe:
    def __init__(
        self,
        repository: object,
    ) -> None:
        self._repository = repository
        self.find_calls = 0
        self.list_calls = 0

    def find_by_binding_for_workspace(
        self,
        *,
        workspace_id: str,
        binding_id: str,
    ):
        self.find_calls += 1

        return (
            self._repository
            .find_by_binding_for_workspace(
                workspace_id=workspace_id,
                binding_id=binding_id,
            )
        )

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 1000,
    ):
        self.list_calls += 1

        return self._repository.list_for_workspace(
            workspace_id=workspace_id,
            limit=limit,
        )


class _EvaluationEvidenceReadProbe:
    def __init__(
        self,
        query: EvaluationEvidenceQueryService,
    ) -> None:
        self._query = query
        self.get_calls = 0

    def get(
        self,
        *,
        evidence_id: str,
    ):
        self.get_calls += 1

        return self._query.get(
            evidence_id=evidence_id,
        )


@dataclass(
    frozen=True,
    slots=True,
)
class _Harness:
    operations: object
    evidence_repository: object
    operation_reads: _OperationReadProbe
    evidence_reads: _EvaluationEvidenceReadProbe
    service: WorkspaceEvaluationEvidenceQueryService
    workspace_a_id: str
    workspace_b_id: str
    user_a_id: str
    user_b_id: str


def _settings(
    *,
    backend: PersistenceBackend,
    tmp_path: Path,
) -> V2PersistenceSettings:
    sqlite_path = None

    if backend is PersistenceBackend.SQLITE:
        sqlite_path = (
            tmp_path
            / "i4-cross-tenant.sqlite3"
        )

    return V2PersistenceSettings(
        backend=backend,
        sqlite_path=sqlite_path,
        database_url=None,
    )


def _operation_repository(
    *,
    settings: V2PersistenceSettings,
):
    if (
        settings.backend
        is PersistenceBackend.MEMORY
    ):
        return (
            InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
        )

    if (
        settings.backend
        is PersistenceBackend.SQLITE
    ):
        if settings.sqlite_path is None:
            raise AssertionError(
                "sqlite path required"
            )

        return (
            SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
                database_path=settings.sqlite_path,
            )
        )

    raise AssertionError(
        "unsupported I4 backend"
    )


def _provision_workspace(
    *,
    authorization_runtime: object,
    label: str,
) -> tuple[str, str]:
    organization_id = f"organization-{label}"
    workspace_id = f"workspace-{label}"
    user_id = f"viewer-{label}"

    authorization_runtime.organizations.create(
        EnterpriseOrganization(
            organization_id=organization_id,
            name=f"Organization {label}",
            created_by_user_id=user_id,
            created_at=NOW,
        )
    )

    authorization_runtime.workspaces.create(
        EnterpriseWorkspace(
            workspace_id=workspace_id,
            organization_id=organization_id,
            name=f"Workspace {label}",
            created_by_user_id=user_id,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    authorization_runtime.memberships.create(
        EnterpriseWorkspaceMembership(
            membership_id=f"membership-{label}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            role=EnterpriseWorkspaceRole.VIEWER,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    return (
        user_id,
        workspace_id,
    )


def _harness(
    *,
    backend: PersistenceBackend,
    tmp_path: Path,
) -> _Harness:
    settings = _settings(
        backend=backend,
        tmp_path=tmp_path,
    )

    authorization_runtime = (
        build_enterprise_authorization_runtime(
            settings
        )
    )

    user_a_id, workspace_a_id = (
        _provision_workspace(
            authorization_runtime=(
                authorization_runtime
            ),
            label="a",
        )
    )

    user_b_id, workspace_b_id = (
        _provision_workspace(
            authorization_runtime=(
                authorization_runtime
            ),
            label="b",
        )
    )

    operations = _operation_repository(
        settings=settings,
    )

    evidence_repositories = (
        build_routing_eval_evidence_repositories(
            settings
        )
    )

    evidence_repository = (
        evidence_repositories.evaluation
    )

    operation_reads = _OperationReadProbe(
        operations
    )

    evidence_reads = (
        _EvaluationEvidenceReadProbe(
            EvaluationEvidenceQueryService(
                repository=evidence_repository,
            )
        )
    )

    authorization_gate = (
        WorkspaceAuthorizationGate(
            resolver=(
                authorization_runtime
                .authorization_resolver
            )
        )
    )

    service = (
        WorkspaceEvaluationEvidenceQueryService(
            operations=operation_reads,
            evaluation_evidence=evidence_reads,
            authorization_gate=authorization_gate,
        )
    )

    return _Harness(
        operations=operations,
        evidence_repository=evidence_repository,
        operation_reads=operation_reads,
        evidence_reads=evidence_reads,
        service=service,
        workspace_a_id=workspace_a_id,
        workspace_b_id=workspace_b_id,
        user_a_id=user_a_id,
        user_b_id=user_b_id,
    )


def _run_record(
    *,
    label: str,
) -> EvaluationRunRecord:
    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id=f"run-{label}",
            dataset=EvaluationDatasetIdentity(
                dataset_id=f"dataset-{label}",
                dataset_version="v1",
            ),
            target_id=f"target-{label}",
        ),
        outcome=EvaluationRunOutcome.SUCCEEDED,
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


def _seed_run_binding(
    harness: _Harness,
    *,
    workspace_id: str,
    actor_user_id: str,
    label: str,
    recorded: bool,
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

    harness.operations.create(
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

    harness.operations.update(
        reserved_operation,
        expected_revision=1,
    )

    if not recorded:
        return binding

    harness.evidence_repository.create(
        EvaluationEvidenceRecord(
            evidence_id=binding.evidence_id,
            run=_run_record(
                label=label,
            ),
            observed_at=(
                NOW + timedelta(seconds=2)
            ),
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
        updated_at=(
            NOW + timedelta(seconds=3)
        ),
        revision=3,
    )

    harness.operations.update(
        recorded_operation,
        expected_revision=2,
    )

    return recorded_binding


@pytest.mark.parametrize(
    "backend",
    _BACKENDS,
    ids=("memory", "sqlite"),
)
def test_authorized_same_workspace_recorded_binding_control(
    backend: PersistenceBackend,
    tmp_path: Path,
) -> None:
    harness = _harness(
        backend=backend,
        tmp_path=tmp_path,
    )

    binding = _seed_run_binding(
        harness,
        workspace_id=harness.workspace_a_id,
        actor_user_id=harness.user_a_id,
        label="a-recorded",
        recorded=True,
    )

    detail = harness.service.get(
        workspace_id=harness.workspace_a_id,
        user_id=harness.user_a_id,
        binding_id=binding.binding_id,
    )

    assert detail is not None
    assert detail.binding_id == binding.binding_id
    assert detail.workspace_id == harness.workspace_a_id

    assert not hasattr(
        detail,
        "evidence_id",
    )

    listed = harness.service.list_workspace(
        workspace_id=harness.workspace_a_id,
        user_id=harness.user_a_id,
    )

    assert tuple(
        item.binding_id
        for item in listed
    ) == (
        binding.binding_id,
    )

    assert all(
        not hasattr(
            item,
            "evidence_id",
        )
        for item in listed
    )

    assert harness.operation_reads.find_calls == 2
    assert harness.operation_reads.list_calls == 1
    assert harness.evidence_reads.get_calls == 2


@pytest.mark.parametrize(
    "backend",
    _BACKENDS,
    ids=("memory", "sqlite"),
)
def test_foreign_user_detail_denied_before_operation_or_platform_lookup(
    backend: PersistenceBackend,
    tmp_path: Path,
) -> None:
    harness = _harness(
        backend=backend,
        tmp_path=tmp_path,
    )

    binding = _seed_run_binding(
        harness,
        workspace_id=harness.workspace_b_id,
        actor_user_id=harness.user_b_id,
        label="b-detail",
        recorded=True,
    )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        harness.service.get(
            workspace_id=harness.workspace_b_id,
            user_id=harness.user_a_id,
            binding_id=binding.binding_id,
        )

    assert harness.operation_reads.find_calls == 0
    assert harness.operation_reads.list_calls == 0
    assert harness.evidence_reads.get_calls == 0


@pytest.mark.parametrize(
    "backend",
    _BACKENDS,
    ids=("memory", "sqlite"),
)
def test_foreign_user_list_denied_before_operation_or_platform_lookup(
    backend: PersistenceBackend,
    tmp_path: Path,
) -> None:
    harness = _harness(
        backend=backend,
        tmp_path=tmp_path,
    )

    _seed_run_binding(
        harness,
        workspace_id=harness.workspace_b_id,
        actor_user_id=harness.user_b_id,
        label="b-list",
        recorded=True,
    )

    with pytest.raises(
        PermissionError,
        match="membership_not_found",
    ):
        harness.service.list_workspace(
            workspace_id=harness.workspace_b_id,
            user_id=harness.user_a_id,
        )

    assert harness.operation_reads.find_calls == 0
    assert harness.operation_reads.list_calls == 0
    assert harness.evidence_reads.get_calls == 0


@pytest.mark.parametrize(
    "backend",
    _BACKENDS,
    ids=("memory", "sqlite"),
)
def test_foreign_binding_and_raw_evidence_identifier_do_not_confer_authority(
    backend: PersistenceBackend,
    tmp_path: Path,
) -> None:
    harness = _harness(
        backend=backend,
        tmp_path=tmp_path,
    )

    binding = _seed_run_binding(
        harness,
        workspace_id=harness.workspace_b_id,
        actor_user_id=harness.user_b_id,
        label="b-foreign",
        recorded=True,
    )

    assert (
        harness.service.get(
            workspace_id=harness.workspace_a_id,
            user_id=harness.user_a_id,
            binding_id=binding.binding_id,
        )
        is None
    )

    assert (
        harness.service.get(
            workspace_id=harness.workspace_a_id,
            user_id=harness.user_a_id,
            binding_id=binding.evidence_id,
        )
        is None
    )

    assert harness.operation_reads.find_calls == 2
    assert harness.operation_reads.list_calls == 0
    assert harness.evidence_reads.get_calls == 0


@pytest.mark.parametrize(
    "backend",
    _BACKENDS,
    ids=("memory", "sqlite"),
)
def test_reserved_binding_is_invisible_to_authorized_workspace_user(
    backend: PersistenceBackend,
    tmp_path: Path,
) -> None:
    harness = _harness(
        backend=backend,
        tmp_path=tmp_path,
    )

    binding = _seed_run_binding(
        harness,
        workspace_id=harness.workspace_a_id,
        actor_user_id=harness.user_a_id,
        label="a-reserved",
        recorded=False,
    )

    assert (
        harness.service.get(
            workspace_id=harness.workspace_a_id,
            user_id=harness.user_a_id,
            binding_id=binding.binding_id,
        )
        is None
    )

    assert harness.service.list_workspace(
        workspace_id=harness.workspace_a_id,
        user_id=harness.user_a_id,
    ) == ()

    assert harness.operation_reads.find_calls == 2
    assert harness.operation_reads.list_calls == 1
    assert harness.evidence_reads.get_calls == 0
