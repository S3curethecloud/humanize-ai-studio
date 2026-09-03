from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseEvaluationEvidenceBindingStatus,
    EnterpriseEvaluationEvidenceKind,
    EnterpriseEvaluationOperationStatus,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
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
    EnterpriseEvaluationOperationTerminalError,
    InMemoryEnterpriseWorkspaceEvaluationOperationRepository,
)
from app.v2.services.enterprise_evaluation_operation_service import (
    EnterpriseEvaluationEvidenceBindingStateError,
    EnterpriseEvaluationEvidenceIntegrityError,
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
    14,
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
    evidence_id: str = "evidence-run",
    run_id: str = "run-1",
) -> EvaluationEvidenceRecord:
    return EvaluationEvidenceRecord(
        evidence_id=evidence_id,
        run=_run_record(
            run_id=run_id,
        ),
        observed_at=NOW,
    )


def _gate_evidence(
    *,
    evidence_id: str = "evidence-gate",
    gate_id: str = "gate-1",
) -> EvaluationEvidenceRecord:
    run = _run_record()

    metric_result = (
        run.metric_results[0]
    )

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

    gate_result = EvaluationGateResult(
        gate=gate,
        run_id="run-1",
        decision=EvaluationGateDecision.PASSED,
        metric_results=(
            metric_result,
        ),
    )

    return EvaluationEvidenceRecord(
        evidence_id=evidence_id,
        run=run,
        gate_result=gate_result,
        observed_at=NOW,
    )


def _service():
    repository = (
        InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
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

    service = EnterpriseEvaluationOperationService(
        repository=repository,
        authorization_gate=authorization,
        evaluation_evidence=evidence,
        operation_id_factory=(
            lambda: "operation-1"
        ),
        binding_id_factory=(
            lambda: next(binding_ids)
        ),
        evidence_id_factory=(
            lambda: next(evidence_ids)
        ),
        clock=(
            lambda: NOW
        ),
    )

    return (
        service,
        repository,
        authorization,
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


def test_start_requires_evaluation_run_permission() -> None:
    (
        service,
        repository,
        authorization,
        _,
    ) = _service()

    operation = _start(
        service
    )

    authorization.require.assert_called_once_with(
        workspace_id="workspace-1",
        user_id="editor-1",
        permission=EnterprisePermission.EVALUATION_RUN,
    )

    assert (
        operation.operation_id
        == "operation-1"
    )

    assert (
        repository.get(
            "operation-1"
        )
        == operation
    )


def test_denied_start_creates_no_operation() -> None:
    (
        service,
        repository,
        authorization,
        _,
    ) = _service()

    authorization.require.side_effect = PermissionError(
        "authorization_denied"
    )

    with pytest.raises(
        PermissionError,
        match="authorization_denied",
    ):
        _start(
            service
        )

    assert (
        repository.get(
            "operation-1"
        )
        is None
    )


def test_service_reserves_server_generated_run_binding() -> None:
    (
        service,
        _,
        _,
        _,
    ) = _service()

    _start(
        service
    )

    operation = service.reserve_run_evidence(
        operation_id="operation-1",
    )

    binding = operation.evidence_bindings[0]

    assert binding.binding_id == "binding-run"
    assert binding.evidence_id == "evidence-run"
    assert (
        binding.evidence_kind
        is EnterpriseEvaluationEvidenceKind.RUN
    )
    assert (
        binding.status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_confirms_exact_run_evidence() -> None:
    (
        service,
        _,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    reserved = service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence()
    )

    confirmed = service.confirm_evidence(
        operation_id="operation-1",
        binding_id=(
            reserved.evidence_bindings[0]
            .binding_id
        ),
    )

    evidence.get.assert_called_once_with(
        evidence_id="evidence-run",
    )

    assert (
        confirmed.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
    )


def test_service_rejects_foreign_run_evidence() -> None:
    (
        service,
        _,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence(
            run_id="foreign-run",
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="run identity",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )


def test_gate_reservation_requires_recorded_run() -> None:
    (
        service,
        _,
        _,
        _,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceBindingStateError,
        match="recorded run evidence binding",
    ):
        service.reserve_gate_evidence(
            operation_id="operation-1",
            gate_id="gate-1",
        )


def test_service_reserves_and_confirms_gate_evidence() -> None:
    (
        service,
        _,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence()
    )

    service.confirm_evidence(
        operation_id="operation-1",
        binding_id="binding-run",
    )

    reserved_gate = service.reserve_gate_evidence(
        operation_id="operation-1",
        gate_id="gate-1",
    )

    gate_binding = (
        reserved_gate.evidence_bindings[1]
    )

    assert (
        gate_binding.evidence_kind
        is EnterpriseEvaluationEvidenceKind.GATE
    )
    assert gate_binding.gate_id == "gate-1"
    assert gate_binding.evidence_id == "evidence-gate"

    evidence.get.return_value = (
        _gate_evidence()
    )

    confirmed = service.confirm_evidence(
        operation_id="operation-1",
        binding_id="binding-gate",
    )

    assert (
        confirmed.evidence_bindings[1].status
        is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
    )


def test_service_completes_only_after_recorded_run() -> None:
    (
        service,
        _,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceBindingStateError,
        match="recorded run evidence binding",
    ):
        service.complete_success(
            operation_id="operation-1",
        )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence()
    )

    service.confirm_evidence(
        operation_id="operation-1",
        binding_id="binding-run",
    )

    completed = service.complete_success(
        operation_id="operation-1",
    )

    assert (
        completed.status
        is EnterpriseEvaluationOperationStatus.SUCCEEDED
    )

    with pytest.raises(
        EnterpriseEvaluationOperationTerminalError,
        match="terminal",
    ):
        service.reserve_gate_evidence(
            operation_id="operation-1",
            gate_id="gate-1",
        )


def test_failure_can_preserve_reserved_binding() -> None:
    (
        service,
        _,
        _,
        _,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    failed = service.complete_failure(
        operation_id="operation-1",
    )

    assert (
        failed.status
        is EnterpriseEvaluationOperationStatus.FAILED
    )

    assert (
        failed.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_missing_platform_evidence() -> None:
    from app.v2.services.routing_eval_evidence_query_service import (
        EvaluationEvidenceNotFoundError,
    )

    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.side_effect = (
        EvaluationEvidenceNotFoundError(
            "evaluation evidence does not exist"
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="does not exist in platform evidence",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_platform_evidence_id_substitution() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence(
            evidence_id="foreign-evidence",
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="identity does not match reserved evidence",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_run_binding_resolving_gate_evidence() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _gate_evidence(
            evidence_id="evidence-run",
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="run evidence binding resolved to gate evidence",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_gate_evidence_run_mismatch() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence()
    )

    service.confirm_evidence(
        operation_id="operation-1",
        binding_id="binding-run",
    )

    service.reserve_gate_evidence(
        operation_id="operation-1",
        gate_id="gate-1",
    )

    foreign_gate_evidence = (
        _gate_evidence()
        .model_copy(
            update={
                "run": _run_record(
                    run_id="foreign-run",
                ),
            }
        )
    )

    evidence.get.return_value = (
        foreign_gate_evidence
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="run identity",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-gate",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    assert (
        operation.evidence_bindings[1].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_gate_evidence_gate_id_mismatch() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence()
    )

    service.confirm_evidence(
        operation_id="operation-1",
        binding_id="binding-run",
    )

    service.reserve_gate_evidence(
        operation_id="operation-1",
        gate_id="gate-1",
    )

    evidence.get.return_value = (
        _gate_evidence(
            gate_id="foreign-gate",
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="gate evidence identity",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-gate",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    assert (
        operation.evidence_bindings[1].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_gate_binding_resolving_run_only_evidence() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence()
    )

    service.confirm_evidence(
        operation_id="operation-1",
        binding_id="binding-run",
    )

    service.reserve_gate_evidence(
        operation_id="operation-1",
        gate_id="gate-1",
    )

    evidence.get.return_value = (
        _run_evidence(
            evidence_id="evidence-gate",
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="gate evidence binding resolved to run-only evidence",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-gate",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    assert (
        operation.evidence_bindings[1].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_dataset_id_mismatch() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    run = _run_record()

    foreign_identity = (
        run.identity.model_copy(
            update={
                "dataset": EvaluationDatasetIdentity(
                    dataset_id="foreign-dataset",
                    dataset_version="v1",
                ),
            }
        )
    )

    foreign_run = run.model_copy(
        update={
            "identity": foreign_identity,
        }
    )

    evidence.get.return_value = (
        _run_evidence().model_copy(
            update={
                "run": foreign_run,
            }
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="dataset identity",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None
    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_dataset_version_mismatch() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    run = _run_record()

    foreign_identity = (
        run.identity.model_copy(
            update={
                "dataset": EvaluationDatasetIdentity(
                    dataset_id="dataset-1",
                    dataset_version="foreign-version",
                ),
            }
        )
    )

    foreign_run = run.model_copy(
        update={
            "identity": foreign_identity,
        }
    )

    evidence.get.return_value = (
        _run_evidence().model_copy(
            update={
                "run": foreign_run,
            }
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="dataset identity",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None
    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_target_id_mismatch() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    run = _run_record()

    foreign_identity = (
        run.identity.model_copy(
            update={
                "target_id": "foreign-target",
            }
        )
    )

    foreign_run = run.model_copy(
        update={
            "identity": foreign_identity,
        }
    )

    evidence.get.return_value = (
        _run_evidence().model_copy(
            update={
                "run": foreign_run,
            }
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="target identity",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None
    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_unrequested_metric() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    run = _run_record()

    unexpected_metric = EvaluationMetricResult(
        metric=EvaluationMetric.NATURALNESS,
        value=0.80,
    )

    foreign_run = run.model_copy(
        update={
            "metric_results": (
                *run.metric_results,
                unexpected_metric,
            ),
        }
    )

    evidence.get.return_value = (
        _run_evidence().model_copy(
            update={
                "run": foreign_run,
            }
        )
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="metrics not requested",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None
    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_success_missing_requested_metric() -> None:
    (
        service,
        repository,
        authorization,
        evidence,
    ) = _service()

    service.start(
        workspace_id="workspace-1",
        actor_user_id="editor-1",
        run_id="run-1",
        dataset_id="dataset-1",
        dataset_version="v1",
        target_id="target-1",
        requested_metrics=(
            EvaluationMetric.CLAIM_PRESERVATION,
            EvaluationMetric.NATURALNESS,
        ),
    )

    authorization.require.assert_called_once_with(
        workspace_id="workspace-1",
        user_id="editor-1",
        permission=EnterprisePermission.EVALUATION_RUN,
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence()
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="metrics do not match enterprise operation request",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None
    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_run_evidence_predating_reservation() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    stale_evidence = (
        _run_evidence()
        .model_copy(
            update={
                "observed_at": datetime(
                    2026,
                    9,
                    3,
                    13,
                    59,
                    tzinfo=UTC,
                ),
            }
        )
    )

    evidence.get.return_value = stale_evidence

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="predates reserved binding",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-run",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    assert (
        operation.evidence_bindings[0].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )


def test_service_rejects_gate_evidence_predating_reservation() -> None:
    (
        service,
        repository,
        _,
        evidence,
    ) = _service()

    _start(
        service
    )

    service.reserve_run_evidence(
        operation_id="operation-1",
    )

    evidence.get.return_value = (
        _run_evidence()
    )

    service.confirm_evidence(
        operation_id="operation-1",
        binding_id="binding-run",
    )

    service.reserve_gate_evidence(
        operation_id="operation-1",
        gate_id="gate-1",
    )

    stale_gate_evidence = (
        _gate_evidence()
        .model_copy(
            update={
                "observed_at": datetime(
                    2026,
                    9,
                    3,
                    13,
                    59,
                    tzinfo=UTC,
                ),
            }
        )
    )

    evidence.get.return_value = (
        stale_gate_evidence
    )

    with pytest.raises(
        EnterpriseEvaluationEvidenceIntegrityError,
        match="predates reserved binding",
    ):
        service.confirm_evidence(
            operation_id="operation-1",
            binding_id="binding-gate",
        )

    operation = repository.get(
        "operation-1"
    )

    assert operation is not None

    assert (
        operation.evidence_bindings[1].status
        is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    )
