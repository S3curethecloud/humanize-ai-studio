from __future__ import annotations

from datetime import datetime

from app.v2.domain.eval_execution import (
    EvaluationRunRequest,
)
from app.v2.domain.eval_ops import (
    EvaluationRunRecord,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)
from app.v2.services.eval_run_execution_service import (
    EvaluationRunExecutionService,
)


class GovernedEvaluationRunExecutionService:
    def __init__(
        self,
        *,
        execution: EvaluationRunExecutionService,
        evidence: EvaluationEvidenceService,
    ) -> None:
        self._execution = execution
        self._evidence = evidence

    def execute(
        self,
        *,
        evidence_id: str,
        request: EvaluationRunRequest,
        observed_at: datetime,
    ) -> EvaluationRunRecord:
        run = self._execution.execute(request)

        self._evidence.record_run(
            evidence_id=evidence_id,
            run=run,
            observed_at=observed_at,
        )

        return run
