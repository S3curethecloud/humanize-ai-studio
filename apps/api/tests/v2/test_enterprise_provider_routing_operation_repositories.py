from datetime import (
    UTC,
    datetime,
    timedelta,
)

import pytest

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingEvidenceBinding,
    EnterpriseProviderRoutingEvidenceBindingStatus,
    EnterpriseProviderRoutingOperationKind,
    EnterpriseProviderRoutingOperationStatus,
    EnterpriseWorkspaceProviderRoutingOperation,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    EnterpriseProviderRoutingOperationIntegrityError,
    EnterpriseProviderRoutingOperationRevisionConflictError,
    EnterpriseProviderRoutingOperationTerminalError,
    InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository,
)


NOW = datetime(
    2026,
    9,
    2,
    18,
    0,
    tzinfo=UTC,
)


def _operation(
    **updates: object,
) -> EnterpriseWorkspaceProviderRoutingOperation:
    payload: dict[
        str,
        object,
    ] = {
        "operation_id": "routing-operation-1",
        "workspace_id": "workspace-1",
        "user_id": "editor-1",
        "operation_kind": (
            EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
        ),
        "policy_id": "routing-policy-1",
        "policy_revision": 3,
        "required_capabilities": frozenset(
            {
                ProviderCapability.REWRITE,
            }
        ),
        "status": (
            EnterpriseProviderRoutingOperationStatus.OPEN
        ),
        "created_at": NOW,
        "updated_at": NOW,
        "revision": 1,
    }
    payload.update(
        updates
    )

    return (
        EnterpriseWorkspaceProviderRoutingOperation(
            **payload
        )
    )


def _replace(
    operation: EnterpriseWorkspaceProviderRoutingOperation,
    **updates: object,
) -> EnterpriseWorkspaceProviderRoutingOperation:
    payload = operation.model_dump(
        mode="python"
    )
    payload.update(
        updates
    )

    return (
        EnterpriseWorkspaceProviderRoutingOperation
        .model_validate(
            payload
        )
    )


def _reserved(
) -> EnterpriseProviderRoutingEvidenceBinding:
    return (
        EnterpriseProviderRoutingEvidenceBinding(
            ordinal=1,
            evidence_id="routing-evidence-1",
            status=(
                EnterpriseProviderRoutingEvidenceBindingStatus
                .RESERVED
            ),
        )
    )


def test_repository_creates_and_reads_operation() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
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


def test_repository_accepts_single_reserved_binding_append() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    candidate = _replace(
        original,
        routing_evidence_bindings=(
            _reserved(),
        ),
        updated_at=(
            NOW
            + timedelta(
                seconds=1
            )
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
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    candidate = _replace(
        original,
        updated_at=(
            NOW
            + timedelta(
                seconds=1
            )
        ),
        revision=2,
    )

    with pytest.raises(
        EnterpriseProviderRoutingOperationRevisionConflictError,
        match="revision conflict",
    ):
        repository.update(
            candidate,
            expected_revision=99,
        )


def test_repository_rejects_binding_removal() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    with_binding = _replace(
        original,
        routing_evidence_bindings=(
            _reserved(),
        ),
        updated_at=(
            NOW
            + timedelta(
                seconds=1
            )
        ),
        revision=2,
    )

    repository.update(
        with_binding,
        expected_revision=1,
    )

    removed = _replace(
        with_binding,
        routing_evidence_bindings=(),
        updated_at=(
            NOW
            + timedelta(
                seconds=2
            )
        ),
        revision=3,
    )

    with pytest.raises(
        EnterpriseProviderRoutingOperationIntegrityError,
        match="cannot be removed",
    ):
        repository.update(
            removed,
            expected_revision=2,
        )


def test_repository_rejects_recorded_binding_downgrade() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
    )

    recorded_binding = (
        EnterpriseProviderRoutingEvidenceBinding(
            ordinal=1,
            evidence_id="routing-evidence-1",
            status=(
                EnterpriseProviderRoutingEvidenceBindingStatus
                .RECORDED
            ),
        )
    )

    original = repository.create(
        _operation()
    )

    reserved = _replace(
        original,
        routing_evidence_bindings=(
            _reserved(),
        ),
        updated_at=(
            NOW
            + timedelta(
                seconds=1
            )
        ),
        revision=2,
    )

    repository.update(
        reserved,
        expected_revision=1,
    )

    confirmed = _replace(
        reserved,
        routing_evidence_bindings=(
            recorded_binding,
        ),
        updated_at=(
            NOW
            + timedelta(
                seconds=2
            )
        ),
        revision=3,
    )

    repository.update(
        confirmed,
        expected_revision=2,
    )

    downgraded = _replace(
        confirmed,
        routing_evidence_bindings=(
            _reserved(),
        ),
        updated_at=(
            NOW
            + timedelta(
                seconds=3
            )
        ),
        revision=4,
    )

    with pytest.raises(
        EnterpriseProviderRoutingOperationIntegrityError,
        match="cannot be downgraded",
    ):
        repository.update(
            downgraded,
            expected_revision=3,
        )


def test_repository_rejects_terminal_operation_update() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
    )

    original = repository.create(
        _operation()
    )

    completed = _replace(
        original,
        status=(
            EnterpriseProviderRoutingOperationStatus
            .NO_PROVIDER_EXECUTION
        ),
        rewrite_history_id="history-1",
        updated_at=(
            NOW
            + timedelta(
                seconds=1
            )
        ),
        revision=2,
    )

    repository.update(
        completed,
        expected_revision=1,
    )

    next_candidate = _replace(
        completed,
        updated_at=(
            NOW
            + timedelta(
                seconds=2
            )
        ),
        revision=3,
    )

    with pytest.raises(
        EnterpriseProviderRoutingOperationTerminalError,
        match="terminal",
    ):
        repository.update(
            next_candidate,
            expected_revision=2,
        )
