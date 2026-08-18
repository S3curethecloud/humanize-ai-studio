from __future__ import annotations

from datetime import datetime

from app.v2.domain.eval_ops import (
    EvaluationGateResult,
    EvaluationQualityGate,
    EvaluationRunRecord,
)
from app.v2.repositories.eval_run import (
    EvaluationRunRepository,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)
from app.v2.services.eval_quality_gate_service import (
    EvaluationQualityGateService,
)


class GovernedEvaluationGateIntegrityError(
    RuntimeError
):
    pass


class GovernedEvaluationGateRunResolutionError(
    RuntimeError
):
    pass


class GovernedEvaluationQualityGateService:
    def __init__(
        self,
        *,
        quality_gate: EvaluationQualityGateService,
        runs: EvaluationRunRepository,
        evidence: EvaluationEvidenceService,
    ) -> None:
        self._quality_gate = quality_gate
        self._runs = runs
        self._evidence = evidence

    def evaluate(
        self,
        *,
        evidence_id: str,
        gate: EvaluationQualityGate,
        run_id: str,
        observed_at: datetime,
    ) -> EvaluationGateResult:
        result = self._quality_gate.evaluate(
            gate=gate,
            run_id=run_id,
        )

        if result.run_id != run_id:
            raise GovernedEvaluationGateIntegrityError(
                "evaluation gate result run identity "
                "does not match requested run"
            )

        run = self._resolve_run(
            run_id=run_id,
        )

        self._evidence.record_gate(
            evidence_id=evidence_id,
            run=run,
            gate_result=result,
            observed_at=observed_at,
        )

        return result

    def _resolve_run(
        self,
        *,
        run_id: str,
    ) -> EvaluationRunRecord:
        try:
            run = self._runs.get(
                run_id
            )
        except Exception as exc:
            raise GovernedEvaluationGateRunResolutionError(
                "evaluation gate evidence run lookup failed"
            ) from exc

        if run is None:
            raise GovernedEvaluationGateRunResolutionError(
                "evaluation gate evidence run does not exist: "
                f"{run_id}"
            )

        if run.identity.run_id != run_id:
            raise GovernedEvaluationGateRunResolutionError(
                "evaluation gate evidence repository returned "
                "a different run identity"
            )

        return run
