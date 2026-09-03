from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

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
    EvaluationMetric,
    EvaluationRunOutcome,
)
from app.v2.repositories.enterprise_evaluation_operations import (
    EnterpriseEvaluationOperationNotFoundError,
    EnterpriseEvaluationOperationTerminalError,
    EnterpriseWorkspaceEvaluationOperationRepository,
)
from app.v2.services.routing_eval_evidence_query_service import (
    EvaluationEvidenceNotFoundError,
    EvaluationEvidenceQueryService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


class EnterpriseEvaluationEvidenceBindingNotFoundError(
    LookupError
):
    pass


class EnterpriseEvaluationEvidenceBindingStateError(
    ValueError
):
    pass


class EnterpriseEvaluationEvidenceIntegrityError(
    RuntimeError
):
    pass


class EnterpriseEvaluationOperationService:
    def __init__(
        self,
        *,
        repository: EnterpriseWorkspaceEvaluationOperationRepository,
        authorization_gate: WorkspaceAuthorizationGate,
        evaluation_evidence: EvaluationEvidenceQueryService,
        operation_id_factory: Callable[[], str] | None = None,
        binding_id_factory: Callable[[], str] | None = None,
        evidence_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._authorization_gate = authorization_gate
        self._evaluation_evidence = evaluation_evidence

        self._operation_id_factory = (
            operation_id_factory
            or _default_operation_id
        )
        self._binding_id_factory = (
            binding_id_factory
            or _default_binding_id
        )
        self._evidence_id_factory = (
            evidence_id_factory
            or _default_evidence_id
        )
        self._clock = (
            clock
            or _utc_now
        )

    def start(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        run_id: str,
        dataset_id: str,
        dataset_version: str,
        target_id: str,
        requested_metrics: tuple[
            EvaluationMetric,
            ...,
        ],
    ) -> EnterpriseWorkspaceEvaluationOperation:
        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=actor_user_id,
            permission=EnterprisePermission.EVALUATION_RUN,
        )

        now = self._clock()

        operation = (
            EnterpriseWorkspaceEvaluationOperation(
                operation_id=(
                    self._operation_id_factory()
                ),
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                run_id=run_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                target_id=target_id,
                requested_metrics=requested_metrics,
                status=(
                    EnterpriseEvaluationOperationStatus.OPEN
                ),
                created_at=now,
                updated_at=now,
                revision=1,
            )
        )

        return self._repository.create(
            operation
        )

    def reserve_run_evidence(
        self,
        *,
        operation_id: str,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        operation = self._require_open(
            operation_id
        )

        if any(
            binding.evidence_kind
            is EnterpriseEvaluationEvidenceKind.RUN
            for binding in operation.evidence_bindings
        ):
            raise EnterpriseEvaluationEvidenceBindingStateError(
                "enterprise evaluation operation "
                "already has a run evidence binding"
            )

        return self._reserve_binding(
            operation=operation,
            evidence_kind=(
                EnterpriseEvaluationEvidenceKind.RUN
            ),
            gate_id=None,
        )

    def reserve_gate_evidence(
        self,
        *,
        operation_id: str,
        gate_id: str,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        operation = self._require_open(
            operation_id
        )

        run_bindings = tuple(
            binding
            for binding in operation.evidence_bindings
            if (
                binding.evidence_kind
                is EnterpriseEvaluationEvidenceKind.RUN
            )
        )

        if (
            len(run_bindings) != 1
            or run_bindings[0].status
            is not EnterpriseEvaluationEvidenceBindingStatus.RECORDED
        ):
            raise EnterpriseEvaluationEvidenceBindingStateError(
                "gate evidence reservation requires "
                "a recorded run evidence binding"
            )

        normalized_gate_id = gate_id.strip()

        if not normalized_gate_id:
            raise ValueError(
                "gate_id must be non-empty"
            )

        if any(
            binding.evidence_kind
            is EnterpriseEvaluationEvidenceKind.GATE
            and binding.gate_id == normalized_gate_id
            for binding in operation.evidence_bindings
        ):
            raise EnterpriseEvaluationEvidenceBindingStateError(
                "enterprise evaluation operation "
                "already has evidence for gate: "
                f"{normalized_gate_id}"
            )

        return self._reserve_binding(
            operation=operation,
            evidence_kind=(
                EnterpriseEvaluationEvidenceKind.GATE
            ),
            gate_id=normalized_gate_id,
        )

    def confirm_evidence(
        self,
        *,
        operation_id: str,
        binding_id: str,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        operation = self._require_open(
            operation_id
        )

        match_index = None

        for index, binding in enumerate(
            operation.evidence_bindings
        ):
            if binding.binding_id == binding_id:
                match_index = index
                break

        if match_index is None:
            raise EnterpriseEvaluationEvidenceBindingNotFoundError(
                "enterprise evaluation evidence "
                "binding not found: "
                f"{binding_id}"
            )

        current = operation.evidence_bindings[
            match_index
        ]

        if (
            current.status
            is EnterpriseEvaluationEvidenceBindingStatus.RECORDED
        ):
            raise EnterpriseEvaluationEvidenceBindingStateError(
                "enterprise evaluation evidence "
                "binding is already recorded"
            )

        try:
            evidence = self._evaluation_evidence.get(
                evidence_id=current.evidence_id,
            )
        except EvaluationEvidenceNotFoundError as exc:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "reserved enterprise evaluation evidence "
                "does not exist in platform evidence"
            ) from exc

        self._validate_platform_evidence(
            operation=operation,
            binding=current,
            evidence=evidence,
        )

        now = self._clock()

        payload = current.model_dump(
            mode="python"
        )
        payload.update(
            {
                "status": (
                    EnterpriseEvaluationEvidenceBindingStatus
                    .RECORDED
                ),
                "recorded_at": now,
            }
        )

        bindings = list(
            operation.evidence_bindings
        )
        bindings[
            match_index
        ] = (
            EnterpriseWorkspaceEvaluationEvidenceBinding
            .model_validate(
                payload
            )
        )

        candidate = _replace_operation(
            operation,
            evidence_bindings=tuple(
                bindings
            ),
            updated_at=now,
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
    ) -> EnterpriseWorkspaceEvaluationOperation:
        operation = self._require_open(
            operation_id
        )

        run_bindings = tuple(
            binding
            for binding in operation.evidence_bindings
            if (
                binding.evidence_kind
                is EnterpriseEvaluationEvidenceKind.RUN
            )
        )

        if (
            len(run_bindings) != 1
            or run_bindings[0].status
            is not EnterpriseEvaluationEvidenceBindingStatus.RECORDED
        ):
            raise EnterpriseEvaluationEvidenceBindingStateError(
                "enterprise evaluation operation success "
                "requires one recorded run evidence binding"
            )

        if any(
            binding.status
            is not EnterpriseEvaluationEvidenceBindingStatus.RECORDED
            for binding in operation.evidence_bindings
        ):
            raise EnterpriseEvaluationEvidenceBindingStateError(
                "enterprise evaluation operation success "
                "requires all evidence bindings to be recorded"
            )

        candidate = _replace_operation(
            operation,
            status=(
                EnterpriseEvaluationOperationStatus.SUCCEEDED
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
    ) -> EnterpriseWorkspaceEvaluationOperation:
        operation = self._require_open(
            operation_id
        )

        candidate = _replace_operation(
            operation,
            status=(
                EnterpriseEvaluationOperationStatus.FAILED
            ),
            updated_at=self._clock(),
            revision=operation.revision + 1,
        )

        return self._repository.update(
            candidate,
            expected_revision=operation.revision,
        )

    def _reserve_binding(
        self,
        *,
        operation: EnterpriseWorkspaceEvaluationOperation,
        evidence_kind: EnterpriseEvaluationEvidenceKind,
        gate_id: str | None,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        now = self._clock()

        binding = (
            EnterpriseWorkspaceEvaluationEvidenceBinding(
                binding_id=(
                    self._binding_id_factory()
                ),
                operation_id=operation.operation_id,
                workspace_id=operation.workspace_id,
                evidence_id=(
                    self._evidence_id_factory()
                ),
                evidence_kind=evidence_kind,
                run_id=operation.run_id,
                gate_id=gate_id,
                status=(
                    EnterpriseEvaluationEvidenceBindingStatus
                    .RESERVED
                ),
                created_at=now,
            )
        )

        candidate = _replace_operation(
            operation,
            evidence_bindings=(
                operation.evidence_bindings
                + (
                    binding,
                )
            ),
            updated_at=now,
            revision=operation.revision + 1,
        )

        return self._repository.update(
            candidate,
            expected_revision=operation.revision,
        )

    def _validate_platform_evidence(
        self,
        *,
        operation: EnterpriseWorkspaceEvaluationOperation,
        binding: EnterpriseWorkspaceEvaluationEvidenceBinding,
        evidence: object,
    ) -> None:
        evidence_id = getattr(
            evidence,
            "evidence_id",
            None,
        )

        if evidence_id != binding.evidence_id:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "platform evaluation evidence identity "
                "does not match reserved evidence"
            )

        observed_at = getattr(
            evidence,
            "observed_at",
            None,
        )

        if (
            not isinstance(
                observed_at,
                datetime,
            )
            or observed_at.tzinfo is None
            or observed_at.utcoffset() is None
        ):
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "platform evaluation evidence observed_at "
                "must be timezone-aware"
            )

        if observed_at < binding.created_at:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "platform evaluation evidence observed_at "
                "predates reserved binding"
            )

        run = getattr(
            evidence,
            "run",
            None,
        )

        run_identity = getattr(
            run,
            "identity",
            None,
        )

        run_id = getattr(
            run_identity,
            "run_id",
            None,
        )

        if (
            run_id != operation.run_id
            or run_id != binding.run_id
        ):
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "platform evaluation evidence run identity "
                "does not match enterprise operation"
            )

        dataset = getattr(
            run_identity,
            "dataset",
            None,
        )

        dataset_id = getattr(
            dataset,
            "dataset_id",
            None,
        )

        dataset_version = getattr(
            dataset,
            "dataset_version",
            None,
        )

        if (
            dataset_id != operation.dataset_id
            or dataset_version != operation.dataset_version
        ):
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "platform evaluation evidence dataset identity "
                "does not match enterprise operation"
            )

        target_id = getattr(
            run_identity,
            "target_id",
            None,
        )

        if target_id != operation.target_id:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "platform evaluation evidence target identity "
                "does not match enterprise operation"
            )

        metric_results = getattr(
            run,
            "metric_results",
            (),
        )

        actual_metrics = frozenset(
            getattr(
                result,
                "metric",
                None,
            )
            for result in metric_results
        )

        expected_metrics = frozenset(
            operation.requested_metrics
        )

        if None in actual_metrics:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "platform evaluation evidence contains "
                "an invalid metric identity"
            )

        if not actual_metrics.issubset(
            expected_metrics
        ):
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "platform evaluation evidence contains "
                "metrics not requested by enterprise operation"
            )

        run_outcome = getattr(
            run,
            "outcome",
            None,
        )

        if (
            run_outcome
            is EvaluationRunOutcome.SUCCEEDED
            and actual_metrics != expected_metrics
        ):
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "successful platform evaluation evidence "
                "metrics do not match enterprise operation request"
            )

        gate_result = getattr(
            evidence,
            "gate_result",
            None,
        )

        if (
            binding.evidence_kind
            is EnterpriseEvaluationEvidenceKind.RUN
        ):
            if gate_result is not None:
                raise EnterpriseEvaluationEvidenceIntegrityError(
                    "run evidence binding resolved "
                    "to gate evidence"
                )

            return

        if gate_result is None:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "gate evidence binding resolved "
                "to run-only evidence"
            )

        gate_result_run_id = getattr(
            gate_result,
            "run_id",
            None,
        )

        if gate_result_run_id != operation.run_id:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "gate evidence run identity "
                "does not match enterprise operation"
            )

        gate = getattr(
            gate_result,
            "gate",
            None,
        )

        gate_id = getattr(
            gate,
            "gate_id",
            None,
        )

        if gate_id != binding.gate_id:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "gate evidence identity "
                "does not match reserved gate"
            )

    def _require_open(
        self,
        operation_id: str,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        operation = self._repository.get(
            operation_id
        )

        if operation is None:
            raise EnterpriseEvaluationOperationNotFoundError(
                "enterprise evaluation operation "
                "not found: "
                f"{operation_id}"
            )

        if (
            operation.status
            is not EnterpriseEvaluationOperationStatus.OPEN
        ):
            raise EnterpriseEvaluationOperationTerminalError(
                "enterprise evaluation operation "
                "is terminal"
            )

        return operation


def _replace_operation(
    operation: EnterpriseWorkspaceEvaluationOperation,
    **updates: object,
) -> EnterpriseWorkspaceEvaluationOperation:
    payload = operation.model_dump(
        mode="python"
    )
    payload.update(
        updates
    )

    return (
        EnterpriseWorkspaceEvaluationOperation
        .model_validate(
            payload
        )
    )


def _default_operation_id() -> str:
    return (
        "enterprise_evaluation_operation_"
        f"{uuid4().hex}"
    )


def _default_binding_id() -> str:
    return (
        "enterprise_evaluation_binding_"
        f"{uuid4().hex}"
    )


def _default_evidence_id() -> str:
    return (
        "enterprise_evaluation_evidence_"
        f"{uuid4().hex}"
    )


def _utc_now() -> datetime:
    return datetime.now(
        UTC
    )
