from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseEvaluationEvidenceBindingStatus,
    EnterpriseEvaluationEvidenceKind,
    EnterpriseEvaluationOperationStatus,
    EnterpriseWorkspaceEvaluationEvidenceBinding,
    EnterpriseWorkspaceEvaluationOperation,
)
from app.v2.domain.eval_ops import (
    EvaluationMetric,
)


NOW = datetime(
    2026,
    9,
    3,
    14,
    0,
    tzinfo=UTC,
)


def _binding(
    *,
    binding_id: str = "binding-1",
    evidence_id: str = "evidence-1",
    evidence_kind: EnterpriseEvaluationEvidenceKind = (
        EnterpriseEvaluationEvidenceKind.RUN
    ),
    gate_id: str | None = None,
    status: EnterpriseEvaluationEvidenceBindingStatus = (
        EnterpriseEvaluationEvidenceBindingStatus.RESERVED
    ),
) -> EnterpriseWorkspaceEvaluationEvidenceBinding:
    return EnterpriseWorkspaceEvaluationEvidenceBinding(
        binding_id=binding_id,
        operation_id="operation-1",
        workspace_id="workspace-1",
        evidence_id=evidence_id,
        evidence_kind=evidence_kind,
        run_id="run-1",
        gate_id=gate_id,
        status=status,
        created_at=NOW,
        recorded_at=(
            NOW
            if (
                status
                is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
            )
            else None
        ),
    )


def _operation(
    **updates: object,
) -> EnterpriseWorkspaceEvaluationOperation:
    payload: dict[str, object] = {
        "operation_id": "operation-1",
        "workspace_id": "workspace-1",
        "actor_user_id": "editor-1",
        "run_id": "run-1",
        "dataset_id": "dataset-1",
        "dataset_version": "v1",
        "target_id": "target-1",
        "requested_metrics": (
            EvaluationMetric.CLAIM_PRESERVATION,
        ),
        "status": (
            EnterpriseEvaluationOperationStatus.OPEN
        ),
        "created_at": NOW,
        "updated_at": NOW,
        "revision": 1,
    }

    payload.update(
        updates
    )

    return EnterpriseWorkspaceEvaluationOperation(
        **payload
    )


def test_run_binding_rejects_gate_id() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain gate_id",
    ):
        _binding(
            gate_id="gate-1",
        )


def test_gate_binding_requires_gate_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires gate_id",
    ):
        _binding(
            evidence_kind=(
                EnterpriseEvaluationEvidenceKind.GATE
            ),
        )


def test_reserved_binding_rejects_recorded_at() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain recorded_at",
    ):
        EnterpriseWorkspaceEvaluationEvidenceBinding(
            binding_id="binding-1",
            operation_id="operation-1",
            workspace_id="workspace-1",
            evidence_id="evidence-1",
            evidence_kind=(
                EnterpriseEvaluationEvidenceKind.RUN
            ),
            run_id="run-1",
            status=(
                EnterpriseEvaluationEvidenceBindingStatus.RESERVED
            ),
            created_at=NOW,
            recorded_at=NOW,
        )


def test_operation_rejects_foreign_workspace_binding() -> None:
    binding = _binding().model_copy(
        update={
            "workspace_id": "workspace-2",
        }
    )

    with pytest.raises(
        ValidationError,
        match="workspace identity must match",
    ):
        _operation(
            evidence_bindings=(
                binding,
            ),
        )


def test_operation_allows_only_one_run_binding() -> None:
    with pytest.raises(
        ValidationError,
        match="at most one run evidence binding",
    ):
        _operation(
            evidence_bindings=(
                _binding(),
                _binding(
                    binding_id="binding-2",
                    evidence_id="evidence-2",
                ),
            ),
        )


def test_gate_bindings_require_distinct_gate_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="distinct gate IDs",
    ):
        _operation(
            evidence_bindings=(
                _binding(
                    binding_id="binding-gate-1",
                    evidence_id="evidence-gate-1",
                    evidence_kind=(
                        EnterpriseEvaluationEvidenceKind.GATE
                    ),
                    gate_id="gate-1",
                ),
                _binding(
                    binding_id="binding-gate-2",
                    evidence_id="evidence-gate-2",
                    evidence_kind=(
                        EnterpriseEvaluationEvidenceKind.GATE
                    ),
                    gate_id="gate-1",
                ),
            ),
        )


def test_success_requires_recorded_run_binding() -> None:
    with pytest.raises(
        ValidationError,
        match="one recorded run evidence binding",
    ):
        _operation(
            status=(
                EnterpriseEvaluationOperationStatus.SUCCEEDED
            ),
        )


def test_success_accepts_recorded_run_and_gate_bindings() -> None:
    operation = _operation(
        evidence_bindings=(
            _binding(
                status=(
                    EnterpriseEvaluationEvidenceBindingStatus
                    .RECORDED
                ),
            ),
            _binding(
                binding_id="binding-gate",
                evidence_id="evidence-gate",
                evidence_kind=(
                    EnterpriseEvaluationEvidenceKind.GATE
                ),
                gate_id="gate-1",
                status=(
                    EnterpriseEvaluationEvidenceBindingStatus
                    .RECORDED
                ),
            ),
        ),
        status=(
            EnterpriseEvaluationOperationStatus.SUCCEEDED
        ),
    )

    assert (
        operation.status
        is EnterpriseEvaluationOperationStatus.SUCCEEDED
    )
