from datetime import (
    UTC,
    datetime,
    timedelta,
)
from itertools import count
import sqlite3
from unittest.mock import MagicMock

import pytest

from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseEvaluationEvidenceBindingStatus,
    EnterpriseEvaluationOperationStatus,
    EnterpriseWorkspaceEvaluationOperation,
)
from app.v2.domain.eval_ops import (
    EvaluationComparator,
    EvaluationDatasetIdentity,
    EvaluationGateDecision,
    EvaluationGateResult,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationQualityGate,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
    EvaluationThreshold,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
)
from app.v2.repositories.enterprise_evaluation_operations import (
    EnterpriseEvaluationOperationAlreadyExistsError,
    EnterpriseEvaluationOperationIntegrityError,
    EnterpriseEvaluationOperationRevisionConflictError,
    EnterpriseEvaluationOperationTerminalError,
)
from app.v2.repositories.enterprise_evaluation_operations_sqlite import (
    SQLiteEnterpriseWorkspaceEvaluationOperationRepository,
)
from app.v2.services.enterprise_evaluation_operation_service import (
    EnterpriseEvaluationOperationService,
)
from app.v2.services.routing_eval_evidence_query_service import (
    EvaluationEvidenceQueryService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


NOW = datetime(
    2026,
    9,
    3,
    17,
    0,
    tzinfo=UTC,
)


def _run_record(
    *,
    run_id: str = "run-1",
) -> EvaluationRunRecord:
    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id=run_id,
            dataset=EvaluationDatasetIdentity(
                dataset_id="dataset-1",
                dataset_version="v1",
            ),
            target_id="target-1",
        ),
        outcome=EvaluationRunOutcome.SUCCEEDED,
        evaluated_case_count=1,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=(
                    EvaluationMetric.CLAIM_PRESERVATION
                ),
                value=0.95,
            ),
        ),
    )


def _run_evidence(
    *,
    evidence_id: str,
) -> EvaluationEvidenceRecord:
    return EvaluationEvidenceRecord(
        evidence_id=evidence_id,
        run=_run_record(),
        observed_at=(
            NOW + timedelta(minutes=1)
        ),
    )


def _gate_evidence(
    *,
    evidence_id: str,
    gate_id: str = "gate-1",
) -> EvaluationEvidenceRecord:
    run = _run_record()

    gate = EvaluationQualityGate(
        gate_id=gate_id,
        thresholds=(
            EvaluationThreshold(
                metric=(
                    EvaluationMetric.CLAIM_PRESERVATION
                ),
                comparator=(
                    EvaluationComparator.AT_LEAST
                ),
                threshold=0.90,
            ),
        ),
    )

    result = EvaluationGateResult(
        gate=gate,
        run_id="run-1",
        decision=EvaluationGateDecision.PASSED,
        metric_results=(
            run.metric_results[0],
        ),
    )

    return EvaluationEvidenceRecord(
        evidence_id=evidence_id,
        run=run,
        gate_result=result,
        observed_at=(
            NOW + timedelta(minutes=1)
        ),
    )


def _service(
    *,
    database_path,
    operation_id: str = "operation-1",
):
    repository = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    authorization = MagicMock(
        spec=WorkspaceAuthorizationGate,
    )

    evidence = MagicMock(
        spec=EvaluationEvidenceQueryService,
    )

    binding_ids = iter(
        (
            "binding-run",
            "binding-gate",
        )
    )

    evidence_ids = iter(
        (
            "evidence-run",
            "evidence-gate",
        )
    )

    ticks = count()

    service = EnterpriseEvaluationOperationService(
        repository=repository,
        authorization_gate=authorization,
        evaluation_evidence=evidence,
        operation_id_factory=(
            lambda: operation_id
        ),
        binding_id_factory=(
            lambda: next(binding_ids)
        ),
        evidence_id_factory=(
            lambda: next(evidence_ids)
        ),
        clock=(
            lambda: (
                NOW
                + timedelta(
                    seconds=next(ticks)
                )
            )
        ),
    )

    return (
        service,
        repository,
        evidence,
    )


def _start(
    service: EnterpriseEvaluationOperationService,
):
    return service.start(
        workspace_id="workspace-1",
        actor_user_id="editor-1",
        run_id="run-1",
        dataset_id="dataset-1",
        dataset_version="v1",
        target_id="target-1",
        requested_metrics=(
            EvaluationMetric.CLAIM_PRESERVATION,
        ),
    )


def _new_operation(
    *,
    operation_id: str,
    workspace_id: str,
    created_at: datetime,
) -> EnterpriseWorkspaceEvaluationOperation:
    return EnterpriseWorkspaceEvaluationOperation(
        operation_id=operation_id,
        workspace_id=workspace_id,
        actor_user_id="editor-1",
        run_id=f"run-{operation_id}",
        dataset_id="dataset-1",
        dataset_version="v1",
        target_id="target-1",
        requested_metrics=(
            EvaluationMetric.CLAIM_PRESERVATION,
        ),
        status=EnterpriseEvaluationOperationStatus.OPEN,
        created_at=created_at,
        updated_at=created_at,
        revision=1,
    )


def test_sqlite_operation_persists_across_restart(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, _, _ = _service(
        database_path=database_path,
    )

    created = _start(
        service
    )

    reopened = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    assert (
        reopened.get(
            "operation-1"
        )
        == created
    )


def test_sqlite_reserved_run_binding_persists_across_restart(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, _, _ = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    reserved = service.reserve_run_evidence(
        operation_id="operation-1",
    )

    reopened = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    persisted = reopened.get(
        "operation-1"
    )

    assert persisted == reserved
    assert persisted is not None
    assert (
        persisted.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_sqlite_recorded_run_and_success_persist_across_restart(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, _, evidence = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    reserved = service.reserve_run_evidence(
        operation_id="operation-1",
    )

    binding = reserved.evidence_bindings[0]

    evidence.get.return_value = (
        _run_evidence(
            evidence_id=binding.evidence_id,
        )
    )

    confirmed = service.confirm_evidence(
        operation_id="operation-1",
        binding_id=binding.binding_id,
    )

    assert (
        confirmed.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
    )

    completed = service.complete_success(
        operation_id="operation-1",
    )

    reopened = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    persisted = reopened.get(
        "operation-1"
    )

    assert persisted == completed
    assert persisted is not None
    assert (
        persisted.status
        is EnterpriseEvaluationOperationStatus.SUCCEEDED
    )
    assert (
        persisted.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
    )


def test_sqlite_run_and_gate_bindings_persist_across_restart(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, _, evidence = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    run_reserved = service.reserve_run_evidence(
        operation_id="operation-1",
    )

    run_binding = (
        run_reserved.evidence_bindings[0]
    )

    run_record = _run_evidence(
        evidence_id=run_binding.evidence_id,
    )

    evidence.get.return_value = run_record

    service.confirm_evidence(
        operation_id="operation-1",
        binding_id=run_binding.binding_id,
    )

    gate_reserved = service.reserve_gate_evidence(
        operation_id="operation-1",
        gate_id="gate-1",
    )

    gate_binding = (
        gate_reserved.evidence_bindings[-1]
    )

    gate_record = _gate_evidence(
        evidence_id=gate_binding.evidence_id,
        gate_id="gate-1",
    )

    evidence.get.return_value = gate_record

    service.confirm_evidence(
        operation_id="operation-1",
        binding_id=gate_binding.binding_id,
    )

    completed = service.complete_success(
        operation_id="operation-1",
    )

    reopened = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    persisted = reopened.get(
        "operation-1"
    )

    assert persisted == completed
    assert persisted is not None
    assert len(
        persisted.evidence_bindings
    ) == 2

    assert all(
        binding.status
        is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
        for binding in persisted.evidence_bindings
    )

    assert (
        persisted.evidence_bindings[1].gate_id
        == "gate-1"
    )


def test_sqlite_failure_preserves_reserved_binding(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, _, _ = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    failed = service.complete_failure(
        operation_id="operation-1",
    )

    reopened = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    persisted = reopened.get(
        "operation-1"
    )

    assert persisted == failed
    assert persisted is not None

    assert (
        persisted.status
        is EnterpriseEvaluationOperationStatus.FAILED
    )

    assert (
        persisted.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_sqlite_repository_requires_expected_revision(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, repository, _ = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    payload = operation.model_dump(
        mode="python"
    )

    payload.update(
        {
            "updated_at": (
                NOW + timedelta(seconds=10)
            ),
            "revision": 2,
        }
    )

    candidate = (
        EnterpriseWorkspaceEvaluationOperation
        .model_validate(
            payload
        )
    )

    with pytest.raises(
        EnterpriseEvaluationOperationRevisionConflictError,
        match="revision conflict",
    ):
        repository.update(
            candidate,
            expected_revision=99,
        )


def test_sqlite_duplicate_create_fails_closed(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, repository, _ = _service(
        database_path=database_path,
    )

    created = _start(
        service
    )

    with pytest.raises(
        EnterpriseEvaluationOperationAlreadyExistsError,
        match="already exists",
    ):
        repository.create(
            created
        )


def test_sqlite_workspace_listing_is_isolated_and_ordered(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    repository = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    first = _new_operation(
        operation_id="operation-a",
        workspace_id="workspace-1",
        created_at=NOW,
    )

    second = _new_operation(
        operation_id="operation-b",
        workspace_id="workspace-1",
        created_at=(
            NOW + timedelta(seconds=1)
        ),
    )

    foreign = _new_operation(
        operation_id="operation-c",
        workspace_id="workspace-2",
        created_at=(
            NOW + timedelta(seconds=2)
        ),
    )

    repository.create(
        first
    )
    repository.create(
        second
    )
    repository.create(
        foreign
    )

    listed = repository.list_for_workspace(
        workspace_id="workspace-1",
    )

    assert tuple(
        operation.operation_id
        for operation in listed
    ) == (
        "operation-b",
        "operation-a",
    )

    assert all(
        operation.workspace_id
        == "workspace-1"
        for operation in listed
    )


def test_sqlite_terminal_operation_rejects_update_after_restart(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, _, _ = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    failed = service.complete_failure(
        operation_id="operation-1",
    )

    reopened = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    payload = failed.model_dump(
        mode="python"
    )

    payload.update(
        {
            "updated_at": (
                failed.updated_at
                + timedelta(seconds=1)
            ),
            "revision": (
                failed.revision + 1
            ),
        }
    )

    candidate = (
        EnterpriseWorkspaceEvaluationOperation
        .model_validate(
            payload
        )
    )

    with pytest.raises(
        EnterpriseEvaluationOperationTerminalError,
        match="terminal",
    ):
        reopened.update(
            candidate,
            expected_revision=failed.revision,
        )


def test_sqlite_reuses_canonical_immutable_provenance_validation(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    service, _, _ = _service(
        database_path=database_path,
    )

    created = _start(
        service
    )

    reopened = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    payload = created.model_dump(
        mode="python"
    )

    payload.update(
        {
            "workspace_id": "workspace-foreign",
            "updated_at": (
                created.updated_at
                + timedelta(seconds=1)
            ),
            "revision": 2,
        }
    )

    candidate = (
        EnterpriseWorkspaceEvaluationOperation
        .model_validate(
            payload
        )
    )

    with pytest.raises(
        EnterpriseEvaluationOperationIntegrityError,
        match="workspace_id is immutable",
    ):
        reopened.update(
            candidate,
            expected_revision=1,
        )


def test_sqlite_workspace_row_payload_mismatch_fails_closed(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    repository = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    operation = _new_operation(
        operation_id="operation-a",
        workspace_id="workspace-1",
        created_at=NOW,
    )

    repository.create(
        operation
    )

    with sqlite3.connect(
        database_path
    ) as connection:
        connection.execute(
            """
            UPDATE enterprise_workspace_evaluation_operations
            SET workspace_id = ?
            WHERE operation_id = ?
            """,
            (
                "workspace-2",
                "operation-a",
            ),
        )

    with pytest.raises(
        EnterpriseEvaluationOperationIntegrityError,
        match="workspace_id",
    ):
        repository.list_for_workspace(
            workspace_id="workspace-2",
        )


def test_sqlite_operation_id_row_payload_mismatch_fails_closed(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    repository = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    operation = _new_operation(
        operation_id="operation-a",
        workspace_id="workspace-1",
        created_at=NOW,
    )

    repository.create(
        operation
    )

    with sqlite3.connect(
        database_path
    ) as connection:
        connection.execute(
            """
            UPDATE enterprise_workspace_evaluation_operations
            SET operation_id = ?
            WHERE operation_id = ?
            """,
            (
                "operation-tampered",
                "operation-a",
            ),
        )

    with pytest.raises(
        EnterpriseEvaluationOperationIntegrityError,
        match="operation_id",
    ):
        repository.get(
            "operation-tampered"
        )


def test_sqlite_update_pre_read_row_payload_mismatch_fails_closed(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "evaluation-operation.sqlite3"
    )

    repository = (
        SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
            database_path=database_path,
        )
    )

    created = _new_operation(
        operation_id="operation-a",
        workspace_id="workspace-1",
        created_at=NOW,
    )

    repository.create(
        created
    )

    payload = created.model_dump(
        mode="python"
    )

    payload.update(
        {
            "updated_at": (
                created.updated_at
                + timedelta(seconds=1)
            ),
            "revision": 2,
        }
    )

    candidate = (
        EnterpriseWorkspaceEvaluationOperation
        .model_validate(
            payload
        )
    )

    with sqlite3.connect(
        database_path
    ) as connection:
        connection.execute(
            """
            UPDATE enterprise_workspace_evaluation_operations
            SET actor_user_id = ?
            WHERE operation_id = ?
            """,
            (
                "tampered-actor",
                "operation-a",
            ),
        )

    with pytest.raises(
        EnterpriseEvaluationOperationIntegrityError,
        match="actor_user_id",
    ):
        repository.update(
            candidate,
            expected_revision=1,
        )
