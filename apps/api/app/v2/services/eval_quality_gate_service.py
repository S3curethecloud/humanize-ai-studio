from __future__ import annotations

from app.v2.domain.eval_ops import (
    EvaluationComparator,
    EvaluationGateDecision,
    EvaluationGateResult,
    EvaluationMetricResult,
    EvaluationQualityGate,
    EvaluationRunOutcome,
    EvaluationRunRecord,
    EvaluationThreshold,
)
from app.v2.repositories.eval_run import (
    EvaluationRunRepository,
)


class EvaluationGateRunResolutionError(
    RuntimeError
):
    pass


class EvaluationGateRunNotComparableError(
    RuntimeError
):
    pass


class EvaluationQualityGateService:
    def __init__(
        self,
        *,
        runs: EvaluationRunRepository,
    ) -> None:
        self._runs = runs

    def evaluate(
        self,
        *,
        gate: EvaluationQualityGate,
        run_id: str,
    ) -> EvaluationGateResult:
        run = self._resolve_run(
            run_id=run_id
        )

        self._require_comparable_run(
            run=run
        )

        result_by_metric = {
            result.metric: result
            for result in run.metric_results
        }

        gate_metric_results: list[
            EvaluationMetricResult
        ] = []

        passed = True

        for threshold in gate.thresholds:
            result = result_by_metric.get(
                threshold.metric
            )

            if result is None:
                raise EvaluationGateRunNotComparableError(
                    "evaluation run does not contain "
                    "required gate metric: "
                    f"{threshold.metric.value}"
                )

            gate_metric_results.append(result)

            if not _threshold_passes(
                threshold=threshold,
                value=result.value,
            ):
                passed = False

        return EvaluationGateResult(
            gate=gate,
            run_id=run.identity.run_id,
            decision=(
                EvaluationGateDecision.PASSED
                if passed
                else EvaluationGateDecision.FAILED
            ),
            metric_results=tuple(
                gate_metric_results
            ),
        )

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
            raise EvaluationGateRunResolutionError(
                "evaluation run lookup failed"
            ) from exc

        if run is None:
            raise EvaluationGateRunResolutionError(
                "evaluation run does not exist: "
                f"{run_id}"
            )

        if run.identity.run_id != run_id:
            raise EvaluationGateRunResolutionError(
                "evaluation run repository returned "
                "a different run identity"
            )

        return run

    @staticmethod
    def _require_comparable_run(
        *,
        run: EvaluationRunRecord,
    ) -> None:
        if (
            run.outcome
            is not EvaluationRunOutcome.SUCCEEDED
        ):
            raise EvaluationGateRunNotComparableError(
                "quality gate requires a successful "
                "evaluation run"
            )

        if not run.metric_results:
            raise EvaluationGateRunNotComparableError(
                "quality gate requires evaluation "
                "run metrics"
            )


def _threshold_passes(
    *,
    threshold: EvaluationThreshold,
    value: float,
) -> bool:
    if (
        threshold.comparator
        is EvaluationComparator.AT_LEAST
    ):
        return value >= threshold.threshold

    return value <= threshold.threshold
