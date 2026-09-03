from __future__ import annotations

from threading import RLock
from typing import Protocol

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingEvidenceBindingStatus,
    EnterpriseProviderRoutingOperationStatus,
    EnterpriseWorkspaceProviderRoutingOperation,
)


class EnterpriseProviderRoutingOperationAlreadyExistsError(
    ValueError
):
    pass


class EnterpriseProviderRoutingOperationNotFoundError(
    LookupError
):
    pass


class EnterpriseProviderRoutingOperationRevisionConflictError(
    ValueError
):
    pass


class EnterpriseProviderRoutingOperationIntegrityError(
    RuntimeError
):
    pass


class EnterpriseProviderRoutingOperationTerminalError(
    ValueError
):
    pass


class EnterpriseWorkspaceProviderRoutingOperationRepository(
    Protocol
):
    def create(
        self,
        operation: EnterpriseWorkspaceProviderRoutingOperation,
    ) -> EnterpriseWorkspaceProviderRoutingOperation: ...

    def get(
        self,
        operation_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingOperation | None: ...

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseWorkspaceProviderRoutingOperation,
        ...,
    ]: ...

    def update(
        self,
        operation: EnterpriseWorkspaceProviderRoutingOperation,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceProviderRoutingOperation: ...


class InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository:
    def __init__(
        self,
    ) -> None:
        self._operations: dict[
            str,
            EnterpriseWorkspaceProviderRoutingOperation,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        operation: EnterpriseWorkspaceProviderRoutingOperation,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        _require_creatable_operation(
            operation
        )

        with self._lock:
            if (
                operation.operation_id
                in self._operations
            ):
                raise (
                    EnterpriseProviderRoutingOperationAlreadyExistsError(
                        "enterprise provider routing operation "
                        "already exists: "
                        f"{operation.operation_id}"
                    )
                )

            candidate = dict(
                self._operations
            )
            candidate[
                operation.operation_id
            ] = operation
            self._operations = candidate

        return operation

    def get(
        self,
        operation_id: str,
    ) -> EnterpriseWorkspaceProviderRoutingOperation | None:
        with self._lock:
            return self._operations.get(
                operation_id
            )

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseWorkspaceProviderRoutingOperation,
        ...,
    ]:
        if (
            not workspace_id
            or workspace_id
            != workspace_id.strip()
        ):
            raise ValueError(
                "enterprise provider routing operation "
                "workspace_id must be normalized"
            )

        if (
            limit < 1
            or limit > 1000
        ):
            raise ValueError(
                "enterprise provider routing operation "
                "list limit must be between 1 and 1000"
            )

        with self._lock:
            matches = tuple(
                operation
                for operation
                in self._operations.values()
                if (
                    operation.workspace_id
                    == workspace_id
                )
            )

        ordered = sorted(
            matches,
            key=lambda operation: (
                operation.created_at,
                operation.operation_id,
            ),
            reverse=True,
        )

        return tuple(
            ordered[:limit]
        )

    def update(
        self,
        operation: EnterpriseWorkspaceProviderRoutingOperation,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        with self._lock:
            stored = self._operations.get(
                operation.operation_id
            )

            if stored is None:
                raise (
                    EnterpriseProviderRoutingOperationNotFoundError(
                        "enterprise provider routing operation "
                        "not found: "
                        f"{operation.operation_id}"
                    )
                )

            _validate_update_candidate(
                stored=stored,
                candidate=operation,
                expected_revision=expected_revision,
            )

            candidate_operations = dict(
                self._operations
            )
            candidate_operations[
                operation.operation_id
            ] = operation
            self._operations = candidate_operations

        return operation


def _require_creatable_operation(
    operation: EnterpriseWorkspaceProviderRoutingOperation,
) -> None:
    if operation.revision != 1:
        raise EnterpriseProviderRoutingOperationIntegrityError(
            "enterprise provider routing operation "
            "must be created at revision 1"
        )

    if (
        operation.status
        is not EnterpriseProviderRoutingOperationStatus.OPEN
    ):
        raise EnterpriseProviderRoutingOperationIntegrityError(
            "enterprise provider routing operation "
            "must be created open"
        )

    if operation.routing_evidence_bindings:
        raise EnterpriseProviderRoutingOperationIntegrityError(
            "enterprise provider routing operation "
            "must be created without evidence bindings"
        )


def _validate_update_candidate(
    *,
    stored: EnterpriseWorkspaceProviderRoutingOperation,
    candidate: EnterpriseWorkspaceProviderRoutingOperation,
    expected_revision: int,
) -> None:
    if (
        stored.status
        is not EnterpriseProviderRoutingOperationStatus.OPEN
    ):
        raise EnterpriseProviderRoutingOperationTerminalError(
            "enterprise provider routing operation "
            "is terminal and cannot be updated"
        )

    if stored.revision != expected_revision:
        raise EnterpriseProviderRoutingOperationRevisionConflictError(
            "enterprise provider routing operation "
            "revision conflict: "
            f"expected {expected_revision}, "
            f"stored {stored.revision}"
        )

    if candidate.revision != expected_revision + 1:
        raise EnterpriseProviderRoutingOperationRevisionConflictError(
            "enterprise provider routing operation "
            "candidate revision must equal expected "
            "revision plus one"
        )

    immutable_fields = (
        "operation_version",
        "policy_version",
        "operation_id",
        "workspace_id",
        "user_id",
        "operation_kind",
        "policy_id",
        "policy_revision",
        "required_capabilities",
        "created_at",
    )

    for field_name in immutable_fields:
        if (
            getattr(
                candidate,
                field_name,
            )
            != getattr(
                stored,
                field_name,
            )
        ):
            raise EnterpriseProviderRoutingOperationIntegrityError(
                "enterprise provider routing operation "
                f"{field_name} is immutable"
            )

    if candidate.updated_at < stored.updated_at:
        raise EnterpriseProviderRoutingOperationIntegrityError(
            "enterprise provider routing operation "
            "updated_at must not move backwards"
        )

    _require_binding_transition(
        stored=stored,
        candidate=candidate,
    )


def _require_binding_transition(
    *,
    stored: EnterpriseWorkspaceProviderRoutingOperation,
    candidate: EnterpriseWorkspaceProviderRoutingOperation,
) -> None:
    current = stored.routing_evidence_bindings
    requested = candidate.routing_evidence_bindings

    if len(requested) < len(current):
        raise EnterpriseProviderRoutingOperationIntegrityError(
            "enterprise provider routing evidence "
            "bindings cannot be removed"
        )

    if len(requested) > len(current) + 1:
        raise EnterpriseProviderRoutingOperationIntegrityError(
            "enterprise provider routing operation "
            "can reserve only one new evidence "
            "binding per revision"
        )

    status_changes = 0

    for existing, updated in zip(
        current,
        requested,
        strict=False,
    ):
        if (
            existing.binding_version
            != updated.binding_version
            or existing.ordinal
            != updated.ordinal
            or existing.evidence_id
            != updated.evidence_id
        ):
            raise EnterpriseProviderRoutingOperationIntegrityError(
                "enterprise provider routing evidence "
                "binding identity is immutable"
            )

        if (
            existing.status
            is EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
            and updated.status
            is not EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
        ):
            raise EnterpriseProviderRoutingOperationIntegrityError(
                "recorded enterprise provider routing "
                "evidence binding cannot be downgraded"
            )

        if existing.status is not updated.status:
            status_changes += 1

    if len(requested) == len(current) + 1:
        if status_changes:
            raise EnterpriseProviderRoutingOperationIntegrityError(
                "enterprise provider routing operation cannot "
                "confirm an existing evidence binding and "
                "reserve a new binding in one revision"
            )

        new_binding = requested[-1]

        if (
            new_binding.ordinal
            != len(requested)
        ):
            raise EnterpriseProviderRoutingOperationIntegrityError(
                "new enterprise provider routing evidence "
                "binding ordinal must follow existing bindings"
            )

        if (
            new_binding.status
            is not EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
        ):
            raise EnterpriseProviderRoutingOperationIntegrityError(
                "new enterprise provider routing evidence "
                "binding must begin reserved"
            )

        return

    if status_changes > 1:
        raise EnterpriseProviderRoutingOperationIntegrityError(
            "enterprise provider routing operation can "
            "confirm only one evidence binding per revision"
        )
