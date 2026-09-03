from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

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
    EnterpriseProviderRoutingOperationNotFoundError,
    EnterpriseProviderRoutingOperationTerminalError,
    EnterpriseWorkspaceProviderRoutingOperationRepository,
)


class EnterpriseProviderRoutingEvidenceBindingNotFoundError(
    LookupError
):
    pass


class EnterpriseProviderRoutingEvidenceBindingStateError(
    ValueError
):
    pass


class EnterpriseProviderRoutingOperationService:
    def __init__(
        self,
        *,
        repository: EnterpriseWorkspaceProviderRoutingOperationRepository,
        operation_id_factory: Callable[
            [],
            str,
        ]
        | None = None,
        clock: Callable[
            [],
            datetime,
        ]
        | None = None,
    ) -> None:
        self._repository = repository
        self._operation_id_factory = (
            operation_id_factory
            or _default_operation_id
        )
        self._clock = (
            clock
            or _utc_now
        )

    def start(
        self,
        *,
        workspace_id: str,
        user_id: str,
        operation_kind: EnterpriseProviderRoutingOperationKind,
        policy_id: str,
        policy_revision: int,
        required_capabilities: frozenset[
            ProviderCapability
        ],
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        now = self._clock()

        operation = (
            EnterpriseWorkspaceProviderRoutingOperation(
                operation_id=(
                    self._operation_id_factory()
                ),
                workspace_id=workspace_id,
                user_id=user_id,
                operation_kind=operation_kind,
                policy_id=policy_id,
                policy_revision=policy_revision,
                required_capabilities=required_capabilities,
                status=(
                    EnterpriseProviderRoutingOperationStatus.OPEN
                ),
                created_at=now,
                updated_at=now,
                revision=1,
            )
        )

        return self._repository.create(
            operation
        )

    def reserve_routing_evidence(
        self,
        *,
        operation_id: str,
        evidence_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        operation = self._require_open(
            operation_id
        )

        binding = (
            EnterpriseProviderRoutingEvidenceBinding(
                ordinal=(
                    len(
                        operation.routing_evidence_bindings
                    )
                    + 1
                ),
                evidence_id=evidence_id,
                status=(
                    EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
                ),
            )
        )

        candidate = _replace_operation(
            operation,
            routing_evidence_bindings=(
                operation.routing_evidence_bindings
                + (
                    binding,
                )
            ),
            updated_at=self._clock(),
            revision=operation.revision + 1,
        )

        return self._repository.update(
            candidate,
            expected_revision=operation.revision,
        )

    def confirm_routing_evidence(
        self,
        *,
        operation_id: str,
        evidence_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        operation = self._require_open(
            operation_id
        )

        bindings = list(
            operation.routing_evidence_bindings
        )

        match_index = None

        for index, binding in enumerate(
            bindings
        ):
            if binding.evidence_id == evidence_id:
                match_index = index
                break

        if match_index is None:
            raise (
                EnterpriseProviderRoutingEvidenceBindingNotFoundError(
                    "enterprise provider routing evidence "
                    "binding not found: "
                    f"{evidence_id}"
                )
            )

        current = bindings[
            match_index
        ]

        if (
            current.status
            is EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
        ):
            raise (
                EnterpriseProviderRoutingEvidenceBindingStateError(
                    "enterprise provider routing evidence "
                    "binding is already recorded"
                )
            )

        bindings[
            match_index
        ] = EnterpriseProviderRoutingEvidenceBinding(
            ordinal=current.ordinal,
            evidence_id=current.evidence_id,
            status=(
                EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
            ),
        )

        candidate = _replace_operation(
            operation,
            routing_evidence_bindings=tuple(
                bindings
            ),
            updated_at=self._clock(),
            revision=operation.revision + 1,
        )

        return self._repository.update(
            candidate,
            expected_revision=operation.revision,
        )

    def complete_success(
        self,
        *,
        operation_id: str,
        provider_execution_required: bool,
        rewrite_history_id: str | None = None,
        long_document_audit_id: str | None = None,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        operation = self._require_open(
            operation_id
        )

        status = (
            EnterpriseProviderRoutingOperationStatus.SUCCEEDED
            if provider_execution_required
            else (
                EnterpriseProviderRoutingOperationStatus.NO_PROVIDER_EXECUTION
            )
        )

        candidate = _replace_operation(
            operation,
            status=status,
            rewrite_history_id=rewrite_history_id,
            long_document_audit_id=(
                long_document_audit_id
            ),
            updated_at=self._clock(),
            revision=operation.revision + 1,
        )

        return self._repository.update(
            candidate,
            expected_revision=operation.revision,
        )

    def complete_failure(
        self,
        *,
        operation_id: str,
        failure_code: str,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        operation = self._require_open(
            operation_id
        )

        candidate = _replace_operation(
            operation,
            status=(
                EnterpriseProviderRoutingOperationStatus.FAILED
            ),
            failure_code=failure_code,
            updated_at=self._clock(),
            revision=operation.revision + 1,
        )

        return self._repository.update(
            candidate,
            expected_revision=operation.revision,
        )

    def _require_open(
        self,
        operation_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        operation = self._repository.get(
            operation_id
        )

        if operation is None:
            raise (
                EnterpriseProviderRoutingOperationNotFoundError(
                    "enterprise provider routing operation "
                    "not found: "
                    f"{operation_id}"
                )
            )

        if (
            operation.status
            is not EnterpriseProviderRoutingOperationStatus.OPEN
        ):
            raise (
                EnterpriseProviderRoutingOperationTerminalError(
                    "enterprise provider routing operation "
                    "is terminal"
                )
            )

        return operation


def _replace_operation(
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


def _default_operation_id() -> str:
    return (
        "enterprise_routing_operation_"
        f"{uuid4().hex}"
    )


def _utc_now() -> datetime:
    return datetime.now(
        UTC
    )
