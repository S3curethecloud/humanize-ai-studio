from datetime import (
    UTC,
    datetime,
    timedelta,
)

import pytest

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingEvidenceBindingStatus,
    EnterpriseProviderRoutingOperationKind,
    EnterpriseProviderRoutingOperationStatus,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    EnterpriseProviderRoutingOperationRevisionConflictError,
)
from app.v2.repositories.enterprise_provider_routing_operations_sqlite import (
    SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.services.enterprise_provider_routing_operation_service import (
    EnterpriseProviderRoutingOperationService,
)


NOW = datetime(
    2026,
    9,
    2,
    19,
    0,
    tzinfo=UTC,
)


def _service(
    *,
    database_path,
) -> tuple[
    EnterpriseProviderRoutingOperationService,
    SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository,
]:
    repository = (
        SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository(
            database_path=database_path,
        )
    )

    ticks = iter(
        (
            NOW,
            NOW + timedelta(seconds=1),
            NOW + timedelta(seconds=2),
            NOW + timedelta(seconds=3),
            NOW + timedelta(seconds=4),
            NOW + timedelta(seconds=5),
        )
    )

    service = (
        EnterpriseProviderRoutingOperationService(
            repository=repository,
            operation_id_factory=(
                lambda: "routing-operation-1"
            ),
            clock=(
                lambda: next(ticks)
            ),
        )
    )

    return (
        service,
        repository,
    )


def _start(
    service: EnterpriseProviderRoutingOperationService,
) -> None:
    service.start(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind
            .SINGLE_REWRITE
        ),
        policy_id="routing-policy-1",
        policy_revision=8,
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
            }
        ),
    )


def test_sqlite_operation_persists_across_restart(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "routing-operation.sqlite3"
    )

    service, _ = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    reserved = service.reserve_routing_evidence(
        operation_id="routing-operation-1",
        evidence_id="routing-evidence-1",
    )

    assert (
        reserved.routing_evidence_bindings[0].status
        is EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
    )

    reopened = (
        SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository(
            database_path=database_path,
        )
    )

    assert (
        reopened.get(
            "routing-operation-1"
        )
        == reserved
    )


def test_sqlite_operation_records_evidence_and_success(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "routing-operation.sqlite3"
    )

    service, _ = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    service.reserve_routing_evidence(
        operation_id="routing-operation-1",
        evidence_id="routing-evidence-1",
    )

    confirmed = service.confirm_routing_evidence(
        operation_id="routing-operation-1",
        evidence_id="routing-evidence-1",
    )

    assert (
        confirmed.routing_evidence_bindings[0].status
        is EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
    )

    completed = service.complete_success(
        operation_id="routing-operation-1",
        provider_execution_required=True,
        rewrite_history_id="history-1",
    )

    reopened = (
        SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository(
            database_path=database_path,
        )
    )

    persisted = reopened.get(
        "routing-operation-1"
    )

    assert persisted == completed
    assert persisted is not None
    assert (
        persisted.status
        is EnterpriseProviderRoutingOperationStatus.SUCCEEDED
    )
    assert (
        persisted.rewrite_history_id
        == "history-1"
    )


def test_sqlite_failure_preserves_reserved_binding(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "routing-operation.sqlite3"
    )

    service, _ = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    service.reserve_routing_evidence(
        operation_id="routing-operation-1",
        evidence_id="routing-evidence-1",
    )

    failed = service.complete_failure(
        operation_id="routing-operation-1",
        failure_code="routing_provider_failure",
    )

    reopened = (
        SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository(
            database_path=database_path,
        )
    )

    persisted = reopened.get(
        "routing-operation-1"
    )

    assert persisted == failed
    assert persisted is not None
    assert (
        persisted.status
        is EnterpriseProviderRoutingOperationStatus.FAILED
    )
    assert (
        persisted.routing_evidence_bindings[0].status
        is EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
    )


def test_sqlite_repository_requires_expected_revision(
    tmp_path,
) -> None:
    database_path = (
        tmp_path
        / "routing-operation.sqlite3"
    )

    service, repository = _service(
        database_path=database_path,
    )

    _start(
        service
    )

    operation = repository.get(
        "routing-operation-1"
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

    candidate = type(
        operation
    ).model_validate(
        payload
    )

    with pytest.raises(
        EnterpriseProviderRoutingOperationRevisionConflictError,
        match="revision conflict",
    ):
        repository.update(
            candidate,
            expected_revision=99,
        )
