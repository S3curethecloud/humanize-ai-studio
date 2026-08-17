from __future__ import annotations

from datetime import datetime

from app.v2.domain.provider_routing import (
    RoutingDecision,
    RoutingDecisionStatus,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceExecutionOutcome,
    RoutingEvidenceRecord,
)
from app.v2.repositories.routing_eval_evidence import (
    RoutingEvidenceRepository,
)
from app.v2.services.routing_eval_evidence_telemetry import (
    RoutingEvalEvidenceTelemetry,
    record_routing_telemetry_best_effort,
)


class RoutingDecisionEvidenceIntegrityError(RuntimeError):
    pass


class RoutingDecisionEvidenceService:
    def __init__(
        self,
        *,
        repository: RoutingEvidenceRepository,
        telemetry: RoutingEvalEvidenceTelemetry | None = None,
    ) -> None:
        self._repository = repository
        self._telemetry = telemetry

    def record_not_executed(
        self,
        *,
        evidence_id: str,
        policy: RoutingPolicy,
        decision: RoutingDecision,
        observed_at: datetime,
    ) -> RoutingEvidenceRecord:
        if (
            decision.status
            is not RoutingDecisionStatus.NO_ELIGIBLE_TARGET
        ):
            raise RoutingDecisionEvidenceIntegrityError(
                "not-executed routing evidence requires "
                "a no-eligible-target routing decision"
            )

        record = RoutingEvidenceRecord(
            evidence_id=evidence_id,
            policy=policy,
            decision=decision,
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.NOT_EXECUTED
            ),
            observed_at=observed_at,
        )

        persisted = self._repository.create(record)

        record_routing_telemetry_best_effort(
            telemetry=self._telemetry,
            record=persisted,
        )

        return persisted
