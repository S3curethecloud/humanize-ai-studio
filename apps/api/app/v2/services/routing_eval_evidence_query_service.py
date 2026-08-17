from __future__ import annotations

from app.v2.domain.eval_ops import (
    EvaluationRunOutcome,
)
from app.v2.domain.provider_routing import (
    RoutingDecisionStatus,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceExecutionOutcome,
    RoutingEvidenceRecord,
)
from app.v2.repositories.routing_eval_evidence import (
    EvaluationEvidenceRepository,
    RoutingEvidenceRepository,
)


class RoutingEvidenceNotFoundError(LookupError):
    pass


class EvaluationEvidenceNotFoundError(LookupError):
    pass


class RoutingEvidenceQueryService:
    def __init__(
        self,
        *,
        repository: RoutingEvidenceRepository,
    ) -> None:
        self._repository = repository

    def get(
        self,
        *,
        evidence_id: str,
    ) -> RoutingEvidenceRecord:
        record = self._repository.get(evidence_id)

        if record is None:
            raise RoutingEvidenceNotFoundError(
                "routing evidence does not exist: "
                f"{evidence_id}"
            )

        return record

    def list_records(
        self,
        *,
        policy_id: str | None = None,
        decision_status: RoutingDecisionStatus | None = None,
        execution_outcome: (
            RoutingEvidenceExecutionOutcome | None
        ) = None,
        executed_target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[RoutingEvidenceRecord, ...]:
        return self._repository.list_records(
            policy_id=policy_id,
            decision_status=decision_status,
            execution_outcome=execution_outcome,
            executed_target_id=executed_target_id,
            limit=limit,
        )


class EvaluationEvidenceQueryService:
    def __init__(
        self,
        *,
        repository: EvaluationEvidenceRepository,
    ) -> None:
        self._repository = repository

    def get(
        self,
        *,
        evidence_id: str,
    ) -> EvaluationEvidenceRecord:
        record = self._repository.get(evidence_id)

        if record is None:
            raise EvaluationEvidenceNotFoundError(
                "evaluation evidence does not exist: "
                f"{evidence_id}"
            )

        return record

    def list_records(
        self,
        *,
        run_id: str | None = None,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        run_outcome: EvaluationRunOutcome | None = None,
        gate_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationEvidenceRecord, ...]:
        return self._repository.list_records(
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            target_id=target_id,
            run_outcome=run_outcome,
            gate_id=gate_id,
            limit=limit,
        )
