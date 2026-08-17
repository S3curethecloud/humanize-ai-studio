from __future__ import annotations

from datetime import datetime

from app.v2.domain.eval_ops import (
    EvaluationGateResult,
    EvaluationRunRecord,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
)
from app.v2.repositories.routing_eval_evidence import (
    EvaluationEvidenceRepository,
)
from app.v2.services.routing_eval_evidence_telemetry import (
    RoutingEvalEvidenceTelemetry,
    record_evaluation_telemetry_best_effort,
)


class EvaluationEvidenceService:
    def __init__(
        self,
        *,
        repository: EvaluationEvidenceRepository,
        telemetry: RoutingEvalEvidenceTelemetry | None = None,
    ) -> None:
        self._repository = repository
        self._telemetry = telemetry

    def record_run(
        self,
        *,
        evidence_id: str,
        run: EvaluationRunRecord,
        observed_at: datetime,
    ) -> EvaluationEvidenceRecord:
        record = EvaluationEvidenceRecord(
            evidence_id=evidence_id,
            run=run,
            observed_at=observed_at,
        )

        persisted = self._repository.create(record)

        record_evaluation_telemetry_best_effort(
            telemetry=self._telemetry,
            record=persisted,
        )

        return persisted

    def record_gate(
        self,
        *,
        evidence_id: str,
        run: EvaluationRunRecord,
        gate_result: EvaluationGateResult,
        observed_at: datetime,
    ) -> EvaluationEvidenceRecord:
        record = EvaluationEvidenceRecord(
            evidence_id=evidence_id,
            run=run,
            gate_result=gate_result,
            observed_at=observed_at,
        )

        persisted = self._repository.create(record)

        record_evaluation_telemetry_best_effort(
            telemetry=self._telemetry,
            record=persisted,
        )

        return persisted
