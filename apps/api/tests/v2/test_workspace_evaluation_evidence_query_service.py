from datetime import (
    UTC,
    datetime,
    timedelta,
)
from unittest.mock import MagicMock

import pytest

from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseEvaluationEvidenceBindingStatus,
    EnterpriseEvaluationEvidenceKind,
    EnterpriseEvaluationOperationStatus,
    EnterpriseWorkspaceEvaluationEvidenceBinding,
    EnterpriseWorkspaceEvaluationOperation,
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
    EnterpriseWorkspaceEvaluationOperationRepository,
)
from app.v2.services.routing_eval_evidence_query_service import (
    EvaluationEvidenceNotFoundError,
    EvaluationEvidenceQueryService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)
from app.v2.services.workspace_evaluation_evidence_query_service import (
    WorkspaceEvaluationEvidenceIntegrityError,
    WorkspaceEvaluationEvidenceQueryService,
)


NOW = datetime(
    2026,
    9,
    3,
    20,
    0,
    tzinfo=UTC,
)


def _run_record(
    *,
    run_id: str = "run-1",
    outcome: EvaluationRunOutcome = EvaluationRunOutcome.SUCCEEDED,
) -> EvaluationRunRecord:
    if outcome is EvaluationRunOutcome.SUCCEEDED:
        metric_results = (
            EvaluationMetricResult(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                value=0.95,
            ),
        )
        failure_reason = None
    else:
        metric_results = ()
        failure_reason = "evaluation execution failed"

    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id=run_id,
            dataset=EvaluationDatasetIdentity(
                dataset_id="dataset-1",
                dataset_version="v1",
            ),
            target_id="target-1",
        ),
        outcome=outcome,
        evaluated_case_count=1,
        failed_case_count=(
            0
            if outcome is EvaluationRunOutcome.SUCCEEDED
            else 1
        ),
        metric_results=metric_results,
        failure_reason=failure_reason,
    )


def _run_evidence(
    *,
    evidence_id: str,
    run_id: str = "run-1",
    outcome: EvaluationRunOutcome = EvaluationRunOutcome.SUCCEEDED,
) -> EvaluationEvidenceRecord:
    return EvaluationEvidenceRecord(
        evidence_id=evidence_id,
        run=_run_record(
            run_id=run_id,
            outcome=outcome,
        ),
        observed_at=(
            NOW + timedelta(seconds=2)
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
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                comparator=EvaluationComparator.AT_LEAST,
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
            NOW + timedelta(seconds=2)
        ),
    )


def _binding(
    *,
    binding_id: str = "binding-run",
    evidence_id: str = "evidence-run",
    evidence_kind: EnterpriseEvaluationEvidenceKind = (
        EnterpriseEvaluationEvidenceKind.RUN
    ),
    status: EnterpriseEvaluationEvidenceBindingStatus = (
        EnterpriseEvaluationEvidenceBindingStatus.RECORDED
    ),
    operation_id: str = "operation-1",
    workspace_id: str = "workspace-1",
    run_id: str = "run-1",
    gate_id: str | None = None,
) -> EnterpriseWorkspaceEvaluationEvidenceBinding:
    return EnterpriseWorkspaceEvaluationEvidenceBinding(
        binding_id=binding_id,
        operation_id=operation_id,
        workspace_id=workspace_id,
        evidence_id=evidence_id,
        evidence_kind=evidence_kind,
        run_id=run_id,
        gate_id=gate_id,
        status=status,
        created_at=NOW,
        recorded_at=(
            NOW + timedelta(seconds=1)
            if status
            is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
            else None
        ),
    )


def _operation(
    *,
    bindings: tuple[
        EnterpriseWorkspaceEvaluationEvidenceBinding,
        ...,
    ],
    operation_id: str = "operation-1",
    workspace_id: str = "workspace-1",
    run_id: str = "run-1",
    status: EnterpriseEvaluationOperationStatus = (
        EnterpriseEvaluationOperationStatus.SUCCEEDED
    ),
) -> EnterpriseWorkspaceEvaluationOperation:
    return EnterpriseWorkspaceEvaluationOperation(
        operation_id=operation_id,
        workspace_id=workspace_id,
        actor_user_id="editor-1",
        run_id=run_id,
        dataset_id="dataset-1",
        dataset_version="v1",
        target_id="target-1",
        requested_metrics=(
            EvaluationMetric.CLAIM_PRESERVATION,
        ),
        evidence_bindings=bindings,
        status=status,
        created_at=(
            NOW - timedelta(seconds=1)
        ),
        updated_at=(
            NOW + timedelta(seconds=1)
        ),
        revision=3,
    )


def _service():
    operations = MagicMock(
        spec=EnterpriseWorkspaceEvaluationOperationRepository,
    )
    evidence = MagicMock(
        spec=EvaluationEvidenceQueryService,
    )
    authorization = MagicMock(
        spec=WorkspaceAuthorizationGate,
    )

    service = WorkspaceEvaluationEvidenceQueryService(
        operations=operations,
        evaluation_evidence=evidence,
        authorization_gate=authorization,
    )

    return (
        service,
        operations,
        evidence,
        authorization,
    )


def test_get_returns_recorded_workspace_projection_without_evidence_id() -> None:
    service, operations, evidence, authorization = _service()

    binding = _binding()

    operation = _operation(
        bindings=(binding,),
    )

    operations.find_by_binding_for_workspace.return_value = operation

    evidence.get.return_value = _run_evidence(
        evidence_id=binding.evidence_id,
    )

    result = service.get(
        workspace_id="workspace-1",
        user_id="viewer-1",
        binding_id="binding-run",
    )

    assert result is not None
    assert result.binding_id == "binding-run"
    assert result.operation_id == "operation-1"
    assert result.workspace_id == "workspace-1"

    assert (
        result.operation_status
        is EnterpriseEvaluationOperationStatus.SUCCEEDED
    )

    assert (
        result.run.outcome
        is EvaluationRunOutcome.SUCCEEDED
    )

    assert result.gate_result is None

    assert not hasattr(
        result,
        "evidence_id",
    )

    authorization.require.assert_called_once_with(
        workspace_id="workspace-1",
        user_id="viewer-1",
        permission=EnterprisePermission.EVALUATION_READ,
    )

    evidence.get.assert_called_once_with(
        evidence_id="evidence-run",
    )


def test_get_foreign_workspace_binding_is_confidentiality_equivalent_not_found() -> None:
    service, operations, evidence, _ = _service()

    operations.find_by_binding_for_workspace.return_value = None

    result = service.get(
        workspace_id="workspace-1",
        user_id="viewer-1",
        binding_id="binding-foreign",
    )

    assert result is None

    evidence.get.assert_not_called()


def test_get_reserved_binding_is_not_workspace_visible() -> None:
    service, operations, evidence, _ = _service()

    binding = _binding(
        status=(
            EnterpriseEvaluationEvidenceBindingStatus.RESERVED
        ),
    )

    operation = _operation(
        bindings=(binding,),
        status=EnterpriseEvaluationOperationStatus.OPEN,
    )

    operations.find_by_binding_for_workspace.return_value = operation

    assert (
        service.get(
            workspace_id="workspace-1",
            user_id="viewer-1",
            binding_id="binding-run",
        )
        is None
    )

    evidence.get.assert_not_called()


def test_get_recorded_binding_missing_platform_evidence_fails_closed() -> None:
    service, operations, evidence, _ = _service()

    binding = _binding()

    operation = _operation(
        bindings=(binding,),
    )

    operations.find_by_binding_for_workspace.return_value = operation

    evidence.get.side_effect = EvaluationEvidenceNotFoundError(
        "missing"
    )

    with pytest.raises(
        WorkspaceEvaluationEvidenceIntegrityError,
        match="missing platform evidence",
    ):
        service.get(
            workspace_id="workspace-1",
            user_id="viewer-1",
            binding_id="binding-run",
        )


def test_get_platform_provenance_mismatch_fails_closed() -> None:
    service, operations, evidence, _ = _service()

    binding = _binding()

    operation = _operation(
        bindings=(binding,),
    )

    operations.find_by_binding_for_workspace.return_value = operation

    evidence.get.return_value = _run_evidence(
        evidence_id=binding.evidence_id,
        run_id="run-other",
    )

    with pytest.raises(
        WorkspaceEvaluationEvidenceIntegrityError,
        match="provenance integrity",
    ):
        service.get(
            workspace_id="workspace-1",
            user_id="viewer-1",
            binding_id="binding-run",
        )


def test_list_workspace_returns_only_recorded_bindings() -> None:
    service, operations, evidence, _ = _service()

    recorded = _binding()

    reserved_gate = _binding(
        binding_id="binding-gate",
        evidence_id="evidence-gate",
        evidence_kind=EnterpriseEvaluationEvidenceKind.GATE,
        status=EnterpriseEvaluationEvidenceBindingStatus.RESERVED,
        gate_id="gate-1",
    )

    operation = _operation(
        bindings=(
            recorded,
            reserved_gate,
        ),
        status=EnterpriseEvaluationOperationStatus.OPEN,
    )

    operations.list_for_workspace.return_value = (
        operation,
    )

    evidence.get.return_value = _run_evidence(
        evidence_id=recorded.evidence_id,
    )

    result = service.list_workspace(
        workspace_id="workspace-1",
        user_id="viewer-1",
    )

    assert len(result) == 1
    assert result[0].binding_id == "binding-run"

    evidence.get.assert_called_once_with(
        evidence_id="evidence-run",
    )


def test_list_workspace_foreign_repository_result_fails_closed() -> None:
    service, operations, evidence, _ = _service()

    binding = _binding(
        operation_id="operation-foreign",
        workspace_id="workspace-2",
    )

    foreign = _operation(
        bindings=(binding,),
        operation_id="operation-foreign",
        workspace_id="workspace-2",
    )

    operations.list_for_workspace.return_value = (
        foreign,
    )

    with pytest.raises(
        WorkspaceEvaluationEvidenceIntegrityError,
        match="foreign workspace",
    ):
        service.list_workspace(
            workspace_id="workspace-1",
            user_id="viewer-1",
        )

    evidence.get.assert_not_called()


def test_get_gate_binding_preserves_gate_result_without_evidence_id() -> None:
    service, operations, evidence, _ = _service()

    run_binding = _binding()

    gate_binding = _binding(
        binding_id="binding-gate",
        evidence_id="evidence-gate",
        evidence_kind=EnterpriseEvaluationEvidenceKind.GATE,
        gate_id="gate-1",
    )

    operation = _operation(
        bindings=(
            run_binding,
            gate_binding,
        ),
    )

    operations.find_by_binding_for_workspace.return_value = operation

    evidence.get.return_value = _gate_evidence(
        evidence_id=gate_binding.evidence_id,
    )

    result = service.get(
        workspace_id="workspace-1",
        user_id="viewer-1",
        binding_id="binding-gate",
    )

    assert result is not None
    assert result.gate_result is not None

    assert (
        result.gate_result.decision
        is EvaluationGateDecision.PASSED
    )

    assert not hasattr(
        result,
        "evidence_id",
    )


def test_projection_preserves_operation_success_with_failed_evaluation_outcome() -> None:
    service, operations, evidence, _ = _service()

    binding = _binding()

    operation = _operation(
        bindings=(binding,),
        status=EnterpriseEvaluationOperationStatus.SUCCEEDED,
    )

    operations.find_by_binding_for_workspace.return_value = operation

    evidence.get.return_value = _run_evidence(
        evidence_id=binding.evidence_id,
        outcome=EvaluationRunOutcome.FAILED,
    )

    result = service.get(
        workspace_id="workspace-1",
        user_id="viewer-1",
        binding_id="binding-run",
    )

    assert result is not None

    assert (
        result.operation_status
        is EnterpriseEvaluationOperationStatus.SUCCEEDED
    )

    assert (
        result.run.outcome
        is EvaluationRunOutcome.FAILED
    )


def test_authorization_denial_prevents_binding_lookup() -> None:
    service, operations, evidence, authorization = _service()

    authorization.require.side_effect = PermissionError(
        "authorization_denied"
    )

    with pytest.raises(
        PermissionError,
        match="authorization_denied",
    ):
        service.get(
            workspace_id="workspace-1",
            user_id="viewer-1",
            binding_id="binding-run",
        )

    operations.find_by_binding_for_workspace.assert_not_called()
    evidence.get.assert_not_called()

def test_list_workspace_duplicate_binding_id_fails_closed_before_evidence_resolution() -> None:
    service, operations, evidence, _ = _service()

    first_binding = _binding(
        binding_id="binding-shared",
        evidence_id="evidence-1",
        operation_id="operation-1",
        run_id="run-1",
    )

    second_binding = _binding(
        binding_id="binding-shared",
        evidence_id="evidence-2",
        operation_id="operation-2",
        run_id="run-2",
    )

    first = _operation(
        bindings=(
            first_binding,
        ),
        operation_id="operation-1",
        run_id="run-1",
    )

    second = _operation(
        bindings=(
            second_binding,
        ),
        operation_id="operation-2",
        run_id="run-2",
    )

    operations.list_for_workspace.return_value = (
        first,
        second,
    )

    with pytest.raises(
        WorkspaceEvaluationEvidenceIntegrityError,
        match="not unique within workspace",
    ):
        service.list_workspace(
            workspace_id="workspace-1",
            user_id="viewer-1",
        )

    evidence.get.assert_not_called()

def test_list_workspace_checks_global_binding_uniqueness_beyond_operation_window() -> None:
    service, operations, evidence, _ = _service()

    binding = _binding(
        binding_id="binding-shared",
    )

    visible = _operation(
        bindings=(
            binding,
        ),
    )

    operations.list_for_workspace.return_value = (
        visible,
    )

    from app.v2.repositories.enterprise_evaluation_operations import (
        EnterpriseEvaluationOperationIntegrityError,
    )

    operations.find_by_binding_for_workspace.side_effect = (
        EnterpriseEvaluationOperationIntegrityError(
            "enterprise evaluation evidence binding identity "
            "is not unique within workspace: "
            "workspace-1/binding-shared"
        )
    )

    with pytest.raises(
        EnterpriseEvaluationOperationIntegrityError,
        match="not unique within workspace",
    ):
        service.list_workspace(
            workspace_id="workspace-1",
            user_id="viewer-1",
            operation_limit=1,
        )

    evidence.get.assert_not_called()
