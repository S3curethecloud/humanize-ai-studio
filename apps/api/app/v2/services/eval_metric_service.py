from __future__ import annotations

from difflib import SequenceMatcher

from app.v2.domain.eval_dataset import (
    EvaluationDatasetCase,
    EvaluationReferenceKind,
)
from app.v2.domain.eval_metrics import (
    EvaluationCaseExecutionEvidence,
    EvaluationMetricMeasurement,
    EvaluationMetricMethod,
)
from app.v2.domain.eval_ops import (
    EvaluationMetric,
    EvaluationMetricResult,
)


class EvaluationMetricEvidenceUnavailableError(
    RuntimeError
):
    pass


class DeterministicEvaluationMetricService:
    def evaluate(
        self,
        *,
        case: EvaluationDatasetCase,
        evidence: EvaluationCaseExecutionEvidence,
        metric: EvaluationMetric,
    ) -> EvaluationMetricMeasurement:
        self._require_case_identity(
            case=case,
            evidence=evidence,
        )

        if metric is EvaluationMetric.CLAIM_PRESERVATION:
            value = self._claim_preservation(
                case=case,
                evidence=evidence,
            )
            method = (
                EvaluationMetricMethod.CLAIM_REFERENCE_CHECKS
            )

        elif metric is EvaluationMetric.NATURALNESS:
            value = self._naturalness(
                evidence=evidence
            )
            method = (
                EvaluationMetricMethod.EXPLICIT_NATURALNESS_SCORE
            )

        elif metric is EvaluationMetric.REWRITE_DISTANCE:
            value = self._rewrite_distance(
                case=case,
                evidence=evidence,
            )
            method = (
                EvaluationMetricMethod.CHARACTER_SEQUENCE_DISTANCE
            )

        elif metric is EvaluationMetric.LATENCY_MS:
            value = self._latency(
                evidence=evidence
            )
            method = (
                EvaluationMetricMethod.EXECUTION_LATENCY
            )

        elif metric is EvaluationMetric.PROVIDER_ERROR_RATE:
            value = (
                1.0
                if evidence.provider_error
                else 0.0
            )
            method = (
                EvaluationMetricMethod.PROVIDER_ERROR_INDICATOR
            )

        else:
            raise RuntimeError(
                "unsupported evaluation metric: "
                f"{metric}"
            )

        return EvaluationMetricMeasurement(
            case_id=case.case_id,
            result=EvaluationMetricResult(
                metric=metric,
                value=value,
            ),
            method=method,
        )

    def evaluate_many(
        self,
        *,
        case: EvaluationDatasetCase,
        evidence: EvaluationCaseExecutionEvidence,
        metrics: tuple[EvaluationMetric, ...],
    ) -> tuple[EvaluationMetricMeasurement, ...]:
        if not metrics:
            raise ValueError(
                "evaluation metric request requires "
                "at least one metric"
            )

        if len(set(metrics)) != len(metrics):
            raise ValueError(
                "evaluation metric request metrics "
                "must be unique"
            )

        return tuple(
            self.evaluate(
                case=case,
                evidence=evidence,
                metric=metric,
            )
            for metric in metrics
        )

    @staticmethod
    def _require_case_identity(
        *,
        case: EvaluationDatasetCase,
        evidence: EvaluationCaseExecutionEvidence,
    ) -> None:
        if evidence.case_id != case.case_id:
            raise ValueError(
                "evaluation execution evidence case_id "
                "does not match dataset case"
            )

    @staticmethod
    def _claim_preservation(
        *,
        case: EvaluationDatasetCase,
        evidence: EvaluationCaseExecutionEvidence,
    ) -> float:
        if evidence.output_text is None:
            raise EvaluationMetricEvidenceUnavailableError(
                "claim preservation requires output text"
            )

        claim_references = tuple(
            reference
            for reference in case.references
            if reference.kind
            in {
                EvaluationReferenceKind.REQUIRED_CLAIM,
                EvaluationReferenceKind.FORBIDDEN_CLAIM,
            }
        )

        if not claim_references:
            raise EvaluationMetricEvidenceUnavailableError(
                "claim preservation requires at least "
                "one claim reference"
            )

        normalized_output = _normalize_text(
            evidence.output_text
        )

        passed = 0

        for reference in claim_references:
            normalized_claim = _normalize_text(
                reference.value
            )
            present = normalized_claim in normalized_output

            if (
                reference.kind
                is EvaluationReferenceKind.REQUIRED_CLAIM
                and present
            ) or (
                reference.kind
                is EvaluationReferenceKind.FORBIDDEN_CLAIM
                and not present
            ):
                passed += 1

        return passed / len(claim_references)

    @staticmethod
    def _naturalness(
        *,
        evidence: EvaluationCaseExecutionEvidence,
    ) -> float:
        if evidence.naturalness_score is None:
            raise EvaluationMetricEvidenceUnavailableError(
                "naturalness requires explicit "
                "naturalness score evidence"
            )

        return evidence.naturalness_score

    @staticmethod
    def _rewrite_distance(
        *,
        case: EvaluationDatasetCase,
        evidence: EvaluationCaseExecutionEvidence,
    ) -> float:
        if evidence.output_text is None:
            raise EvaluationMetricEvidenceUnavailableError(
                "rewrite distance requires output text"
            )

        similarity = SequenceMatcher(
            None,
            case.input.text,
            evidence.output_text,
            autojunk=False,
        ).ratio()

        return 1.0 - similarity

    @staticmethod
    def _latency(
        *,
        evidence: EvaluationCaseExecutionEvidence,
    ) -> float:
        if evidence.latency_ms is None:
            raise EvaluationMetricEvidenceUnavailableError(
                "latency metric requires latency evidence"
            )

        return evidence.latency_ms


def _normalize_text(
    value: str,
) -> str:
    return " ".join(
        value.casefold().split()
    )
