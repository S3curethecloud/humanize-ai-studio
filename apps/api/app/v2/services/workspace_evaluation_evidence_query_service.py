from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
    EvaluationGateResult,
    EvaluationRunRecord,
)
from app.v2.repositories.enterprise_evaluation_operations import (
    EnterpriseWorkspaceEvaluationOperationRepository,
)
from app.v2.services.enterprise_evaluation_evidence_integrity import (
    EnterpriseEvaluationEvidenceIntegrityError,
    require_enterprise_evaluation_evidence_integrity,
)
from app.v2.services.routing_eval_evidence_query_service import (
    EvaluationEvidenceNotFoundError,
    EvaluationEvidenceQueryService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


class WorkspaceEvaluationEvidenceIntegrityError(
    RuntimeError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class WorkspaceEvaluationEvidenceProjection:
    binding_id: str
    operation_id: str
    workspace_id: str
    operation_status: EnterpriseEvaluationOperationStatus
    evidence_kind: EnterpriseEvaluationEvidenceKind
    run: EvaluationRunRecord
    gate_result: EvaluationGateResult | None
    recorded_at: datetime
    observed_at: datetime


class WorkspaceEvaluationEvidenceQueryService:
    def __init__(
        self,
        *,
        operations: EnterpriseWorkspaceEvaluationOperationRepository,
        evaluation_evidence: EvaluationEvidenceQueryService,
        authorization_gate: WorkspaceAuthorizationGate,
    ) -> None:
        self._operations = operations
        self._evaluation_evidence = evaluation_evidence
        self._authorization_gate = authorization_gate

    def get(
        self,
        *,
        workspace_id: str,
        user_id: str,
        binding_id: str,
    ) -> WorkspaceEvaluationEvidenceProjection | None:
        self._authorize(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        operation = (
            self._operations.find_by_binding_for_workspace(
                workspace_id=workspace_id,
                binding_id=binding_id,
            )
        )

        if operation is None:
            return None

        if operation.workspace_id != workspace_id:
            raise WorkspaceEvaluationEvidenceIntegrityError(
                "workspace evaluation repository returned "
                "foreign workspace operation"
            )

        binding = self._require_binding(
            operation=operation,
            binding_id=binding_id,
        )

        if (
            binding.status
            is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
        ):
            return None

        if (
            binding.status
            is not EnterpriseEvaluationEvidenceBindingStatus.RECORDED
        ):
            raise WorkspaceEvaluationEvidenceIntegrityError(
                "workspace evaluation evidence binding has "
                "an unsupported status"
            )

        return self._resolve_recorded_binding(
            operation=operation,
            binding=binding,
        )

    def list_workspace(
        self,
        *,
        workspace_id: str,
        user_id: str,
        operation_limit: int = 50,
    ) -> tuple[
        WorkspaceEvaluationEvidenceProjection,
        ...,
    ]:
        self._authorize(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        operations = self._operations.list_for_workspace(
            workspace_id=workspace_id,
            limit=operation_limit,
        )

        seen_binding_ids: set[str] = set()

        for operation in operations:
            if operation.workspace_id != workspace_id:
                raise WorkspaceEvaluationEvidenceIntegrityError(
                    "workspace evaluation repository returned "
                    "foreign workspace operation"
                )

            for binding in operation.evidence_bindings:
                if binding.binding_id in seen_binding_ids:
                    raise WorkspaceEvaluationEvidenceIntegrityError(
                        "workspace evaluation evidence binding "
                        "identity is not unique within workspace"
                    )

                seen_binding_ids.add(
                    binding.binding_id
                )

                self._operations.find_by_binding_for_workspace(
                    workspace_id=workspace_id,
                    binding_id=binding.binding_id,
                )

        projections: list[
            WorkspaceEvaluationEvidenceProjection
        ] = []

        for operation in operations:
            if operation.workspace_id != workspace_id:
                raise WorkspaceEvaluationEvidenceIntegrityError(
                    "workspace evaluation repository returned "
                    "foreign workspace operation"
                )

            for binding in operation.evidence_bindings:
                if (
                    binding.status
                    is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
                ):
                    continue

                if (
                    binding.status
                    is not EnterpriseEvaluationEvidenceBindingStatus.RECORDED
                ):
                    raise WorkspaceEvaluationEvidenceIntegrityError(
                        "workspace evaluation evidence binding has "
                        "an unsupported status"
                    )

                projections.append(
                    self._resolve_recorded_binding(
                        operation=operation,
                        binding=binding,
                    )
                )

        return tuple(
            projections
        )

    def _authorize(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> None:
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=(
                EnterprisePermission.EVALUATION_READ
            ),
        )

    def _require_binding(
        self,
        *,
        operation: EnterpriseWorkspaceEvaluationOperation,
        binding_id: str,
    ) -> EnterpriseWorkspaceEvaluationEvidenceBinding:
        matches = tuple(
            binding
            for binding in operation.evidence_bindings
            if binding.binding_id == binding_id
        )

        if len(matches) != 1:
            raise WorkspaceEvaluationEvidenceIntegrityError(
                "workspace evaluation repository binding lookup "
                "did not resolve exactly one authoritative binding"
            )

        return matches[0]

    def _resolve_recorded_binding(
        self,
        *,
        operation: EnterpriseWorkspaceEvaluationOperation,
        binding: EnterpriseWorkspaceEvaluationEvidenceBinding,
    ) -> WorkspaceEvaluationEvidenceProjection:
        if binding.recorded_at is None:
            raise WorkspaceEvaluationEvidenceIntegrityError(
                "recorded workspace evaluation evidence binding "
                "is missing recorded_at"
            )

        try:
            evidence = self._evaluation_evidence.get(
                evidence_id=binding.evidence_id,
            )
        except EvaluationEvidenceNotFoundError as exc:
            raise WorkspaceEvaluationEvidenceIntegrityError(
                "recorded workspace evaluation evidence binding "
                "is missing platform evidence"
            ) from exc

        try:
            require_enterprise_evaluation_evidence_integrity(
                operation=operation,
                binding=binding,
                evidence=evidence,
            )
        except EnterpriseEvaluationEvidenceIntegrityError as exc:
            raise WorkspaceEvaluationEvidenceIntegrityError(
                "recorded workspace evaluation evidence failed "
                "provenance integrity validation"
            ) from exc

        return WorkspaceEvaluationEvidenceProjection(
            binding_id=binding.binding_id,
            operation_id=operation.operation_id,
            workspace_id=operation.workspace_id,
            operation_status=operation.status,
            evidence_kind=binding.evidence_kind,
            run=evidence.run,
            gate_result=evidence.gate_result,
            recorded_at=binding.recorded_at,
            observed_at=evidence.observed_at,
        )
