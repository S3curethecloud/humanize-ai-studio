from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingOperationKind,
    EnterpriseProviderRoutingOperationStatus,
    EnterpriseWorkspaceProviderRoutingOperation,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    EnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.services.enterprise_provider_routing_operation_service import (
    EnterpriseProviderRoutingOperationService,
)
from app.v2.services.enterprise_provider_routing_policy_runtime_service import (
    EnterpriseProviderRoutingPolicyRuntimeService,
)
from app.v2.services.enterprise_routing_aware_provider import (
    EnterpriseProviderRoutingProviderContext,
    EnterpriseRoutingAwareRewriteProvider,
)


ENTERPRISE_ROUTING_OPERATION_SCOPE_FAILURE_CODE = (
    "enterprise_routing_operation_scope_failed"
)

ENTERPRISE_ROUTING_OPERATION_MISSING_SUCCESS_TERMINALIZATION_FAILURE_CODE = (
    "enterprise_routing_operation_missing_success_terminalization"
)


class EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
    RuntimeError,
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseProviderRoutingOperationScope:
    operation_id: str
    workspace_id: str
    user_id: str
    operation_kind: EnterpriseProviderRoutingOperationKind
    policy_id: str
    policy_revision: int
    required_capabilities: frozenset[
        ProviderCapability
    ]


class EnterpriseProviderRoutingOperationCoordinator:
    def __init__(
        self,
        *,
        policy_runtime: EnterpriseProviderRoutingPolicyRuntimeService,
        operations: EnterpriseProviderRoutingOperationService,
        operation_repository: (
            EnterpriseWorkspaceProviderRoutingOperationRepository
        ),
        provider: EnterpriseRoutingAwareRewriteProvider,
    ) -> None:
        self._policy_runtime = policy_runtime
        self._operations = operations
        self._operation_repository = (
            operation_repository
        )
        self._provider = provider

    @contextmanager
    def use_routing_operation(
        self,
        *,
        workspace_id: str,
        user_id: str,
        operation_kind: EnterpriseProviderRoutingOperationKind,
        required_capabilities: frozenset[
            ProviderCapability
        ],
    ) -> Iterator[
        EnterpriseProviderRoutingOperationScope | None
    ]:
        runtime_context = (
            self._policy_runtime.resolve(
                workspace_id=workspace_id,
                user_id=user_id,
            )
        )

        if runtime_context is None:
            yield None
            return

        if (
            runtime_context.workspace_id
            != workspace_id
        ):
            raise (
                EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                    "enterprise routing policy runtime "
                    "workspace scope mismatch"
                )
            )

        operation = self._operations.start(
            workspace_id=workspace_id,
            user_id=user_id,
            operation_kind=operation_kind,
            policy_id=(
                runtime_context.policy_id
            ),
            policy_revision=(
                runtime_context.policy_revision
            ),
            required_capabilities=(
                required_capabilities
            ),
        )

        scope = EnterpriseProviderRoutingOperationScope(
            operation_id=operation.operation_id,
            workspace_id=operation.workspace_id,
            user_id=operation.user_id,
            operation_kind=operation.operation_kind,
            policy_id=operation.policy_id,
            policy_revision=operation.policy_revision,
            required_capabilities=(
                operation.required_capabilities
            ),
        )

        self._require_scope_operation(
            scope
        )

        provider_context = (
            EnterpriseProviderRoutingProviderContext(
                operation_id=operation.operation_id,
                execution_policy=(
                    runtime_context.execution_policy
                ),
                required_capabilities=(
                    required_capabilities
                ),
            )
        )

        try:
            with self._provider.use_routing_context(
                provider_context
            ):
                yield scope

        except BaseException:
            self._terminalize_body_failure(
                scope
            )
            raise

        else:
            current = self._require_scope_operation(
                scope
            )

            if (
                current.status
                is EnterpriseProviderRoutingOperationStatus.OPEN
            ):
                try:
                    self._operations.complete_failure(
                        operation_id=scope.operation_id,
                        failure_code=(
                            ENTERPRISE_ROUTING_OPERATION_MISSING_SUCCESS_TERMINALIZATION_FAILURE_CODE
                        ),
                    )
                except Exception as exc:
                    raise (
                        EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                            "enterprise routing operation "
                            "missing-success terminalization failed"
                        )
                    ) from exc

                raise (
                    EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                        "active enterprise routing operation "
                        "exited without success terminalization"
                    )
                )

            if current.status not in {
                EnterpriseProviderRoutingOperationStatus.SUCCEEDED,
                EnterpriseProviderRoutingOperationStatus.NO_PROVIDER_EXECUTION,
            }:
                raise (
                    EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                        "active enterprise routing operation "
                        "exited with a non-success terminal status"
                    )
                )

    def complete_success(
        self,
        *,
        scope: EnterpriseProviderRoutingOperationScope,
        rewrite_history_id: str | None = None,
        long_document_audit_id: str | None = None,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        current = self._require_scope_operation(
            scope
        )

        if (
            current.status
            is not EnterpriseProviderRoutingOperationStatus.OPEN
        ):
            raise (
                EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                    "enterprise routing operation must be "
                    "open before success terminalization"
                )
            )

        provider_execution_required = bool(
            current.routing_evidence_bindings
        )

        return self._operations.complete_success(
            operation_id=scope.operation_id,
            provider_execution_required=(
                provider_execution_required
            ),
            rewrite_history_id=rewrite_history_id,
            long_document_audit_id=(
                long_document_audit_id
            ),
        )

    def _terminalize_body_failure(
        self,
        scope: EnterpriseProviderRoutingOperationScope,
    ) -> None:
        current = self._require_scope_operation(
            scope
        )

        if (
            current.status
            is EnterpriseProviderRoutingOperationStatus.OPEN
        ):
            try:
                self._operations.complete_failure(
                    operation_id=scope.operation_id,
                    failure_code=(
                        ENTERPRISE_ROUTING_OPERATION_SCOPE_FAILURE_CODE
                    ),
                )
            except Exception as exc:
                raise (
                    EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                        "enterprise routing operation "
                        "failure terminalization failed"
                    )
                ) from exc

            return

        if (
            current.status
            is EnterpriseProviderRoutingOperationStatus.FAILED
        ):
            return

        raise (
            EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                "workspace operation failed after enterprise "
                "routing operation was already terminalized "
                "as successful"
            )
        )

    def _require_scope_operation(
        self,
        scope: EnterpriseProviderRoutingOperationScope,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        try:
            operation = (
                self._operation_repository.get(
                    scope.operation_id
                )
            )
        except Exception as exc:
            raise (
                EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                    "enterprise routing operation "
                    "state resolution failed"
                )
            ) from exc

        if operation is None:
            raise (
                EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                    "enterprise routing operation "
                    "state is unavailable"
                )
            )

        if (
            operation.workspace_id
            != scope.workspace_id
            or operation.user_id
            != scope.user_id
            or operation.operation_kind
            is not scope.operation_kind
            or operation.policy_id
            != scope.policy_id
            or operation.policy_revision
            != scope.policy_revision
            or operation.required_capabilities
            != scope.required_capabilities
        ):
            raise (
                EnterpriseProviderRoutingOperationCoordinatorIntegrityError(
                    "enterprise routing operation "
                    "scope integrity mismatch"
                )
            )

        return operation
