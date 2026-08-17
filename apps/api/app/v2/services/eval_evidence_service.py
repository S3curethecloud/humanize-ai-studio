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


class EvaluationEvidenceService:
    def __init__(
        self,
        *,
        repository: EvaluationEvidenceRepository,
    ) -> None:
        self._repository = repository

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

        return self._repository.create(record)

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

        return self._repository.create(record)
