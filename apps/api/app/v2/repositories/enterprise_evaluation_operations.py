from __future__ import annotations

from threading import RLock
from typing import Protocol

from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseEvaluationEvidenceBindingStatus,
    EnterpriseEvaluationOperationStatus,
    EnterpriseWorkspaceEvaluationOperation,
)


class EnterpriseEvaluationOperationAlreadyExistsError(
    ValueError
):
    pass


class EnterpriseEvaluationOperationNotFoundError(
    LookupError
):
    pass


class EnterpriseEvaluationOperationRevisionConflictError(
    ValueError
):
    pass


class EnterpriseEvaluationOperationIntegrityError(
    RuntimeError
):
    pass


class EnterpriseEvaluationOperationTerminalError(
    ValueError
):
    pass


class EnterpriseWorkspaceEvaluationOperationRepository(
    Protocol
):
    def create(
        self,
        operation: EnterpriseWorkspaceEvaluationOperation,
    ) -> EnterpriseWorkspaceEvaluationOperation: ...

    def get(
        self,
        operation_id: str,
    ) -> EnterpriseWorkspaceEvaluationOperation | None: ...

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseWorkspaceEvaluationOperation,
        ...,
    ]: ...

    def update(
        self,
        operation: EnterpriseWorkspaceEvaluationOperation,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceEvaluationOperation: ...


class InMemoryEnterpriseWorkspaceEvaluationOperationRepository:
    def __init__(
        self,
    ) -> None:
        self._operations: dict[
            str,
            EnterpriseWorkspaceEvaluationOperation,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        operation: EnterpriseWorkspaceEvaluationOperation,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        _require_creatable_operation(
            operation
        )

        with self._lock:
            if (
                operation.operation_id
                in self._operations
            ):
                raise (
                    EnterpriseEvaluationOperationAlreadyExistsError(
                        "enterprise evaluation operation "
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
    ) -> EnterpriseWorkspaceEvaluationOperation | None:
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
        EnterpriseWorkspaceEvaluationOperation,
        ...,
    ]:
        if (
            not workspace_id
            or workspace_id != workspace_id.strip()
        ):
            raise ValueError(
                "enterprise evaluation operation "
                "workspace_id must be normalized"
            )

        if limit < 1 or limit > 1000:
            raise ValueError(
                "enterprise evaluation operation "
                "list limit must be between 1 and 1000"
            )

        with self._lock:
            matches = tuple(
                operation
                for operation in self._operations.values()
                if operation.workspace_id == workspace_id
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
        operation: EnterpriseWorkspaceEvaluationOperation,
        *,
        expected_revision: int,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        with self._lock:
            stored = self._operations.get(
                operation.operation_id
            )

            if stored is None:
                raise (
                    EnterpriseEvaluationOperationNotFoundError(
                        "enterprise evaluation operation "
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
    operation: EnterpriseWorkspaceEvaluationOperation,
) -> None:
    if operation.revision != 1:
        raise EnterpriseEvaluationOperationIntegrityError(
            "enterprise evaluation operation "
            "must be created at revision 1"
        )

    if (
        operation.status
        is not EnterpriseEvaluationOperationStatus.OPEN
    ):
        raise EnterpriseEvaluationOperationIntegrityError(
            "enterprise evaluation operation "
            "must be created open"
        )

    if operation.evidence_bindings:
        raise EnterpriseEvaluationOperationIntegrityError(
            "enterprise evaluation operation "
            "must be created without evidence bindings"
        )


def _validate_update_candidate(
    *,
    stored: EnterpriseWorkspaceEvaluationOperation,
    candidate: EnterpriseWorkspaceEvaluationOperation,
    expected_revision: int,
) -> None:
    if (
        stored.status
        is not EnterpriseEvaluationOperationStatus.OPEN
    ):
        raise EnterpriseEvaluationOperationTerminalError(
            "enterprise evaluation operation "
            "is terminal and cannot be updated"
        )

    if stored.revision != expected_revision:
        raise EnterpriseEvaluationOperationRevisionConflictError(
            "enterprise evaluation operation "
            "revision conflict: "
            f"expected {expected_revision}, "
            f"stored {stored.revision}"
        )

    if candidate.revision != expected_revision + 1:
        raise EnterpriseEvaluationOperationRevisionConflictError(
            "enterprise evaluation operation "
            "candidate revision must equal expected "
            "revision plus one"
        )

    immutable_fields = (
        "operation_version",
        "operation_id",
        "workspace_id",
        "actor_user_id",
        "run_id",
        "dataset_id",
        "dataset_version",
        "target_id",
        "requested_metrics",
        "created_at",
    )

    for field_name in immutable_fields:
        if (
            getattr(candidate, field_name)
            != getattr(stored, field_name)
        ):
            raise EnterpriseEvaluationOperationIntegrityError(
                "enterprise evaluation operation "
                f"{field_name} is immutable"
            )

    if candidate.updated_at < stored.updated_at:
        raise EnterpriseEvaluationOperationIntegrityError(
            "enterprise evaluation operation "
            "updated_at must not move backwards"
        )

    _require_binding_transition(
        stored=stored,
        candidate=candidate,
    )


def _require_binding_transition(
    *,
    stored: EnterpriseWorkspaceEvaluationOperation,
    candidate: EnterpriseWorkspaceEvaluationOperation,
) -> None:
    current = stored.evidence_bindings
    requested = candidate.evidence_bindings

    if len(requested) < len(current):
        raise EnterpriseEvaluationOperationIntegrityError(
            "enterprise evaluation evidence "
            "bindings cannot be removed"
        )

    if len(requested) > len(current) + 1:
        raise EnterpriseEvaluationOperationIntegrityError(
            "enterprise evaluation operation "
            "can reserve only one new evidence "
            "binding per revision"
        )

    status_changes = 0

    immutable_binding_fields = (
        "binding_version",
        "binding_id",
        "operation_id",
        "workspace_id",
        "evidence_id",
        "evidence_kind",
        "run_id",
        "gate_id",
        "created_at",
    )

    for existing, updated in zip(
        current,
        requested,
        strict=False,
    ):
        for field_name in immutable_binding_fields:
            if (
                getattr(existing, field_name)
                != getattr(updated, field_name)
            ):
                raise EnterpriseEvaluationOperationIntegrityError(
                    "enterprise evaluation evidence "
                    "binding identity is immutable"
                )

        if (
            existing.status
            is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
        ):
            if (
                updated.status
                is not EnterpriseEvaluationEvidenceBindingStatus.RECORDED
                or updated.recorded_at
                != existing.recorded_at
            ):
                raise EnterpriseEvaluationOperationIntegrityError(
                    "recorded enterprise evaluation evidence "
                    "binding cannot be changed"
                )

            continue

        if (
            updated.status
            is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
        ):
            status_changes += 1

    if len(requested) == len(current) + 1:
        if status_changes:
            raise EnterpriseEvaluationOperationIntegrityError(
                "enterprise evaluation operation cannot "
                "confirm an existing evidence binding and "
                "reserve a new binding in one revision"
            )

        new_binding = requested[-1]

        if (
            new_binding.status
            is not EnterpriseEvaluationEvidenceBindingStatus.RESERVED
        ):
            raise EnterpriseEvaluationOperationIntegrityError(
                "new enterprise evaluation evidence "
                "binding must begin reserved"
            )

        return

    if status_changes > 1:
        raise EnterpriseEvaluationOperationIntegrityError(
            "enterprise evaluation operation can "
            "confirm only one evidence binding per revision"
        )
