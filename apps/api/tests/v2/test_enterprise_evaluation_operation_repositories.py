from datetime import (
    UTC,
    datetime,
    timedelta,
)

import pytest

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
from app.v2.repositories.enterprise_evaluation_operations import (
    EnterpriseEvaluationOperationIntegrityError,
    EnterpriseEvaluationOperationRevisionConflictError,
    EnterpriseEvaluationOperationTerminalError,
    InMemoryEnterpriseWorkspaceEvaluationOperationRepository,
)


NOW = datetime(
    2026,
    9,
    3,
    14,
    0,
    tzinfo=UTC,
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


def _replace(
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


def _reserved_binding(
) -> EnterpriseWorkspaceEvaluationEvidenceBinding:
    return EnterpriseWorkspaceEvaluationEvidenceBinding(
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
        created_at=(
            NOW
            + timedelta(seconds=1)
        ),
    )


def test_repository_creates_reads_and_lists_workspace() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
    )

    operation = repository.create(
        _operation()
    )

    assert (
        repository.get(
            operation.operation_id
        )
        == operation
    )

    assert (
        repository.list_for_workspace(
            workspace_id="workspace-1",
        )
        == (
            operation,
        )
    )

    assert (
        repository.list_for_workspace(
            workspace_id="workspace-2",
        )
        == ()
    )


def test_repository_accepts_single_reserved_binding_append() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    candidate = _replace(
        original,
        evidence_bindings=(
            _reserved_binding(),
        ),
        updated_at=(
            NOW
            + timedelta(seconds=1)
        ),
        revision=2,
    )

    assert (
        repository.update(
            candidate,
            expected_revision=1,
        )
        == candidate
    )


def test_repository_rejects_revision_conflict() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    candidate = _replace(
        original,
        updated_at=(
            NOW
            + timedelta(seconds=1)
        ),
        revision=2,
    )

    with pytest.raises(
        EnterpriseEvaluationOperationRevisionConflictError,
        match="revision conflict",
    ):
        repository.update(
            candidate,
            expected_revision=99,
        )


def test_repository_rejects_workspace_mutation() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    candidate = _replace(
        original,
        workspace_id="workspace-2",
        updated_at=(
            NOW
            + timedelta(seconds=1)
        ),
        revision=2,
    )

    with pytest.raises(
        EnterpriseEvaluationOperationIntegrityError,
        match="workspace_id is immutable",
    ):
        repository.update(
            candidate,
            expected_revision=1,
        )


def test_repository_rejects_binding_removal() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    with_binding = _replace(
        original,
        evidence_bindings=(
            _reserved_binding(),
        ),
        updated_at=(
            NOW
            + timedelta(seconds=1)
        ),
        revision=2,
    )

    repository.update(
        with_binding,
        expected_revision=1,
    )

    removed = _replace(
        with_binding,
        evidence_bindings=(),
        updated_at=(
            NOW
            + timedelta(seconds=2)
        ),
        revision=3,
    )

    with pytest.raises(
        EnterpriseEvaluationOperationIntegrityError,
        match="cannot be removed",
    ):
        repository.update(
            removed,
            expected_revision=2,
        )


def test_repository_rejects_recorded_binding_change() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    reserved = _replace(
        original,
        evidence_bindings=(
            _reserved_binding(),
        ),
        updated_at=(
            NOW
            + timedelta(seconds=1)
        ),
        revision=2,
    )

    repository.update(
        reserved,
        expected_revision=1,
    )

    recorded = (
        reserved.evidence_bindings[0]
        .model_copy(
            update={
                "status": (
                    EnterpriseEvaluationEvidenceBindingStatus
                    .RECORDED
                ),
                "recorded_at": (
                    NOW
                    + timedelta(seconds=2)
                ),
            }
        )
    )

    confirmed = _replace(
        reserved,
        evidence_bindings=(
            recorded,
        ),
        updated_at=(
            NOW
            + timedelta(seconds=2)
        ),
        revision=3,
    )

    repository.update(
        confirmed,
        expected_revision=2,
    )

    changed = (
        recorded.model_copy(
            update={
                "recorded_at": (
                    NOW
                    + timedelta(seconds=3)
                ),
            }
        )
    )

    candidate = _replace(
        confirmed,
        evidence_bindings=(
            changed,
        ),
        updated_at=(
            NOW
            + timedelta(seconds=3)
        ),
        revision=4,
    )

    with pytest.raises(
        EnterpriseEvaluationOperationIntegrityError,
        match="cannot be changed",
    ):
        repository.update(
            candidate,
            expected_revision=3,
        )


def test_repository_rejects_terminal_operation_update() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    failed = _replace(
        original,
        status=(
            EnterpriseEvaluationOperationStatus.FAILED
        ),
        updated_at=(
            NOW
            + timedelta(seconds=1)
        ),
        revision=2,
    )

    repository.update(
        failed,
        expected_revision=1,
    )

    candidate = _replace(
        failed,
        updated_at=(
            NOW
            + timedelta(seconds=2)
        ),
        revision=3,
    )

    with pytest.raises(
        EnterpriseEvaluationOperationTerminalError,
        match="terminal",
    ):
        repository.update(
            candidate,
            expected_revision=2,
        )
