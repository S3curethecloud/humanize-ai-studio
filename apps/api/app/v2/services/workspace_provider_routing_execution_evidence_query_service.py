from __future__ import annotations

from dataclasses import dataclass

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingEvidenceBinding,
    EnterpriseProviderRoutingEvidenceBindingStatus,
    EnterpriseWorkspaceProviderRoutingOperation,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceRecord,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    EnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.services.routing_eval_evidence_query_service import (
    RoutingEvidenceNotFoundError,
    RoutingEvidenceQueryService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


class WorkspaceProviderRoutingExecutionEvidenceIntegrityError(
    RuntimeError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class WorkspaceProviderRoutingEvidenceBindingView:
    binding: EnterpriseProviderRoutingEvidenceBinding
    routing_evidence: RoutingEvidenceRecord | None


@dataclass(
    frozen=True,
    slots=True,
)
class WorkspaceProviderRoutingExecutionEvidence:
    operation: EnterpriseWorkspaceProviderRoutingOperation
    bindings: tuple[
        WorkspaceProviderRoutingEvidenceBindingView,
        ...,
    ]


class WorkspaceProviderRoutingExecutionEvidenceQueryService:
    def __init__(
        self,
        *,
        operations: (
            EnterpriseWorkspaceProviderRoutingOperationRepository
        ),
        routing_evidence: RoutingEvidenceQueryService,
        authorization_gate: WorkspaceAuthorizationGate,
    ) -> None:
        self._operations = operations
        self._routing_evidence = routing_evidence
        self._authorization_gate = authorization_gate

    def get(
        self,
        *,
        workspace_id: str,
        user_id: str,
        operation_id: str,
    ) -> WorkspaceProviderRoutingExecutionEvidence | None:
        self._authorize(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        operation = self._operations.get(
            operation_id
        )

        if operation is None:
            return None

        if operation.workspace_id != workspace_id:
            return None

        return self._resolve(
            operation
        )

    def list_workspace(
        self,
        *,
        workspace_id: str,
        user_id: str,
        limit: int = 50,
    ) -> tuple[
        WorkspaceProviderRoutingExecutionEvidence,
        ...,
    ]:
        self._authorize(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        operations = (
            self._operations.list_for_workspace(
                workspace_id=workspace_id,
                limit=limit,
            )
        )

        resolved: list[
            WorkspaceProviderRoutingExecutionEvidence
        ] = []

        for operation in operations:
            if operation.workspace_id != workspace_id:
                raise (
                    WorkspaceProviderRoutingExecutionEvidenceIntegrityError(
                        "workspace routing operation repository "
                        "returned foreign workspace evidence"
                    )
                )

            resolved.append(
                self._resolve(
                    operation
                )
            )

        return tuple(
            resolved
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
                EnterprisePermission.AUDIT_READ
            ),
        )

    def _resolve(
        self,
        operation: EnterpriseWorkspaceProviderRoutingOperation,
    ) -> WorkspaceProviderRoutingExecutionEvidence:
        bindings = tuple(
            self._resolve_binding(
                operation=operation,
                binding=binding,
            )
            for binding
            in operation.routing_evidence_bindings
        )

        return (
            WorkspaceProviderRoutingExecutionEvidence(
                operation=operation,
                bindings=bindings,
            )
        )

    def _resolve_binding(
        self,
        *,
        operation: EnterpriseWorkspaceProviderRoutingOperation,
        binding: EnterpriseProviderRoutingEvidenceBinding,
    ) -> WorkspaceProviderRoutingEvidenceBindingView:
        if (
            binding.status
            is EnterpriseProviderRoutingEvidenceBindingStatus.RESERVED
        ):
            return (
                WorkspaceProviderRoutingEvidenceBindingView(
                    binding=binding,
                    routing_evidence=None,
                )
            )

        if (
            binding.status
            is not EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
        ):
            raise (
                WorkspaceProviderRoutingExecutionEvidenceIntegrityError(
                    "workspace routing evidence binding has "
                    "an unsupported status"
                )
            )

        try:
            evidence = self._routing_evidence.get(
                evidence_id=binding.evidence_id,
            )
        except RoutingEvidenceNotFoundError as exc:
            raise (
                WorkspaceProviderRoutingExecutionEvidenceIntegrityError(
                    "recorded workspace routing evidence "
                    "binding is missing platform evidence"
                )
            ) from exc

        if (
            evidence.policy.policy_id
            != operation.policy_id
        ):
            raise (
                WorkspaceProviderRoutingExecutionEvidenceIntegrityError(
                    "workspace routing evidence policy identity "
                    "does not match enterprise operation"
                )
            )

        return (
            WorkspaceProviderRoutingEvidenceBindingView(
                binding=binding,
                routing_evidence=evidence,
            )
        )
