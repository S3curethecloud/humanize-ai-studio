from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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


NOW = datetime(
    2026,
    9,
    2,
    18,
    0,
    tzinfo=UTC,
)


def _binding(
    *,
    ordinal: int = 1,
    evidence_id: str = "routing-evidence-1",
    status: (
        EnterpriseProviderRoutingEvidenceBindingStatus
    ) = (
        EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
    ),
) -> EnterpriseProviderRoutingEvidenceBinding:
    return EnterpriseProviderRoutingEvidenceBinding(
        ordinal=ordinal,
        evidence_id=evidence_id,
        status=status,
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
        "policy_revision": 4,
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


def test_operation_requires_rewrite_capability() -> None:
    with pytest.raises(
        ValidationError,
        match="requires rewrite capability",
    ):
        _operation(
            required_capabilities=frozenset(
                {
                    ProviderCapability.CLAIM_LOCK,
                }
            )
        )


def test_multi_candidate_operation_requires_capability() -> None:
    with pytest.raises(
        ValidationError,
        match="requires multi_candidate capability",
    ):
        _operation(
            operation_kind=(
                EnterpriseProviderRoutingOperationKind
                .MULTI_CANDIDATE_REWRITE
            ),
            required_capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        )


def test_successful_operation_requires_recorded_binding() -> None:
    operation = _operation(
        routing_evidence_bindings=(
            _binding(),
        ),
        status=(
            EnterpriseProviderRoutingOperationStatus.SUCCEEDED
        ),
        rewrite_history_id="history-1",
    )

    assert (
        operation.routing_evidence_bindings[0].status
        is EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
    )


def test_success_rejects_reserved_binding() -> None:
    with pytest.raises(
        ValidationError,
        match="recorded routing evidence bindings",
    ):
        _operation(
            routing_evidence_bindings=(
                _binding(
                    status=(
                        EnterpriseProviderRoutingEvidenceBindingStatus
                        .RESERVED
                    )
                ),
            ),
            status=(
                EnterpriseProviderRoutingOperationStatus.SUCCEEDED
            ),
            rewrite_history_id="history-1",
        )


def test_no_provider_execution_requires_zero_bindings() -> None:
    operation = _operation(
        status=(
            EnterpriseProviderRoutingOperationStatus
            .NO_PROVIDER_EXECUTION
        ),
        rewrite_history_id="history-1",
    )

    assert (
        operation.routing_evidence_bindings
        == ()
    )


def test_long_document_success_requires_audit_linkage() -> None:
    operation = _operation(
        operation_kind=(
            EnterpriseProviderRoutingOperationKind
            .LONG_DOCUMENT_REWRITE
        ),
        required_capabilities=frozenset(
            {
                ProviderCapability.REWRITE,
                ProviderCapability.LONG_DOCUMENT,
            }
        ),
        routing_evidence_bindings=(
            _binding(),
        ),
        status=(
            EnterpriseProviderRoutingOperationStatus.SUCCEEDED
        ),
        long_document_audit_id="audit-1",
    )

    assert (
        operation.long_document_audit_id
        == "audit-1"
    )


def test_failed_operation_can_preserve_reserved_binding() -> None:
    operation = _operation(
        routing_evidence_bindings=(
            _binding(
                status=(
                    EnterpriseProviderRoutingEvidenceBindingStatus
                    .RESERVED
                )
            ),
        ),
        status=(
            EnterpriseProviderRoutingOperationStatus.FAILED
        ),
        failure_code="routing_provider_failure",
    )

    assert (
        operation.routing_evidence_bindings[0].status
        is EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
    )
