from datetime import UTC, datetime

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingEvidenceBindingStatus,
    EnterpriseProviderRoutingOperationKind,
    EnterpriseProviderRoutingOperationStatus,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.services.enterprise_provider_routing_operation_service import (
    EnterpriseProviderRoutingOperationService,
)


NOW = datetime(
    2026,
    9,
    2,
    18,
    0,
    tzinfo=UTC,
)


def _service(
) -> tuple[
    EnterpriseProviderRoutingOperationService,
    InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository,
]:
    repository = (
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
    )

    service = (
        EnterpriseProviderRoutingOperationService(
            repository=repository,
            operation_id_factory=(
                lambda: "routing-operation-1"
            ),
            clock=(
                lambda: NOW
            ),
        )
    )

    return (
        service,
        repository,
    )


def test_service_starts_server_generated_operation() -> None:
    service, repository = _service()

    operation = service.start(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind
            .SINGLE_REWRITE
        ),
        policy_id="routing-policy-1",
        policy_revision=7,
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
            }
        ),
    )

    assert (
        operation.operation_id
        == "routing-operation-1"
    )
    assert (
        operation.status
        is EnterpriseProviderRoutingOperationStatus.OPEN
    )
    assert (
        repository.get(
            "routing-operation-1"
        )
        == operation
    )


def test_service_reserves_confirms_and_completes_success() -> None:
    service, _ = _service()

    service.start(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind
            .SINGLE_REWRITE
        ),
        policy_id="routing-policy-1",
        policy_revision=7,
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
            }
        ),
    )

    reserved = service.reserve_routing_evidence(
        operation_id="routing-operation-1",
        evidence_id="routing-evidence-1",
    )

    assert (
        reserved.routing_evidence_bindings[0].status
        is EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
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

    assert (
        completed.status
        is EnterpriseProviderRoutingOperationStatus.SUCCEEDED
    )
    assert (
        completed.rewrite_history_id
        == "history-1"
    )


def test_service_completes_no_provider_execution() -> None:
    service, _ = _service()

    service.start(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind
            .SINGLE_REWRITE
        ),
        policy_id="routing-policy-1",
        policy_revision=7,
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
            }
        ),
    )

    completed = service.complete_success(
        operation_id="routing-operation-1",
        provider_execution_required=False,
        rewrite_history_id="history-1",
    )

    assert (
        completed.status
        is EnterpriseProviderRoutingOperationStatus
        .NO_PROVIDER_EXECUTION
    )
    assert (
        completed.routing_evidence_bindings
        == ()
    )


def test_service_failure_preserves_reserved_evidence_identity() -> None:
    service, _ = _service()

    service.start(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind
            .SINGLE_REWRITE
        ),
        policy_id="routing-policy-1",
        policy_revision=7,
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
            }
        ),
    )

    service.reserve_routing_evidence(
        operation_id="routing-operation-1",
        evidence_id="routing-evidence-1",
    )

    failed = service.complete_failure(
        operation_id="routing-operation-1",
        failure_code="routing_provider_failure",
    )

    assert (
        failed.status
        is EnterpriseProviderRoutingOperationStatus.FAILED
    )
    assert (
        failed.failure_code
        == "routing_provider_failure"
    )
    assert (
        failed.routing_evidence_bindings[0].status
        is EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
    )


def test_service_long_document_success_links_audit() -> None:
    service, _ = _service()

    service.start(
        workspace_id="workspace-1",
        user_id="editor-1",
        operation_kind=(
            EnterpriseProviderRoutingOperationKind
            .LONG_DOCUMENT_REWRITE
        ),
        policy_id="routing-policy-1",
        policy_revision=7,
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.LONG_DOCUMENT,
            }
        ),
    )

    service.reserve_routing_evidence(
        operation_id="routing-operation-1",
        evidence_id="routing-evidence-1",
    )

    service.confirm_routing_evidence(
        operation_id="routing-operation-1",
        evidence_id="routing-evidence-1",
    )

    completed = service.complete_success(
        operation_id="routing-operation-1",
        provider_execution_required=True,
        long_document_audit_id="audit-1",
    )

    assert (
        completed.long_document_audit_id
        == "audit-1"
    )
