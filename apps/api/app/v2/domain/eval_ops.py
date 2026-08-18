from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

EVAL_OPS_VERSION: Literal["eval-ops-v1"] = "eval-ops-v1"


class EvaluationMetric(StrEnum):
    CLAIM_PRESERVATION = "claim_preservation"
    NATURALNESS = "naturalness"
    REWRITE_DISTANCE = "rewrite_distance"
    LATENCY_MS = "latency_ms"
    PROVIDER_ERROR_RATE = "provider_error_rate"


class EvaluationComparator(StrEnum):
    AT_LEAST = "at_least"
    AT_MOST = "at_most"


class EvaluationRunOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EvaluationGateDecision(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class EvaluationDatasetIdentity(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    dataset_id: str = Field(
        min_length=1,
        max_length=200,
    )
    dataset_version: str = Field(
        min_length=1,
        max_length=200,
    )


class EvaluationRunIdentity(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    run_id: str = Field(
        min_length=1,
        max_length=200,
    )
    dataset: EvaluationDatasetIdentity
    target_id: str = Field(
        min_length=1,
        max_length=200,
    )


class EvaluationMetricResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    metric: EvaluationMetric
    value: float


class EvaluationRunRecord(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    identity: EvaluationRunIdentity
    outcome: EvaluationRunOutcome
    evaluated_case_count: int = Field(
        ge=0,
    )
    failed_case_count: int = Field(
        ge=0,
    )
    metric_results: tuple[
        EvaluationMetricResult,
        ...,
    ] = ()
    failure_reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def require_run_integrity(
        self,
    ) -> EvaluationRunRecord:
        if self.failed_case_count > self.evaluated_case_count:
            raise ValueError(
                "failed evaluation case count cannot exceed "
                "evaluated case count"
            )

        metrics = tuple(
            result.metric
            for result in self.metric_results
        )

        if len(set(metrics)) != len(metrics):
            raise ValueError(
                "evaluation run metric results must be unique"
            )

        if self.outcome is EvaluationRunOutcome.SUCCEEDED:
            if self.evaluated_case_count < 1:
                raise ValueError(
                    "successful evaluation run requires "
                    "at least one evaluated case"
                )

            if not self.metric_results:
                raise ValueError(
                    "successful evaluation run requires "
                    "metric results"
                )

            if self.failure_reason is not None:
                raise ValueError(
                    "successful evaluation run cannot contain "
                    "failure_reason"
                )

        else:
            if self.failure_reason is None:
                raise ValueError(
                    "failed evaluation run requires failure_reason"
                )

        return self


class EvaluationThreshold(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    metric: EvaluationMetric
    comparator: EvaluationComparator
    threshold: float


class EvaluationQualityGate(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    gate_id: str = Field(
        min_length=1,
        max_length=200,
    )
    thresholds: tuple[
        EvaluationThreshold,
        ...,
    ] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def require_gate_integrity(
        self,
    ) -> EvaluationQualityGate:
        metrics = tuple(
            threshold.metric
            for threshold in self.thresholds
        )

        if len(set(metrics)) != len(metrics):
            raise ValueError(
                "evaluation quality gate metrics must be unique"
            )

        return self


class EvaluationGateResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    gate: EvaluationQualityGate
    run_id: str = Field(
        min_length=1,
        max_length=200,
    )
    decision: EvaluationGateDecision
    metric_results: tuple[
        EvaluationMetricResult,
        ...,
    ] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def require_gate_result_integrity(
        self,
    ) -> EvaluationGateResult:
        result_by_metric = {
            result.metric: result
            for result in self.metric_results
        }

        if len(result_by_metric) != len(self.metric_results):
            raise ValueError(
                "evaluation gate metric results must be unique"
            )

        threshold_metrics = {
            threshold.metric
            for threshold in self.gate.thresholds
        }

        if set(result_by_metric) != threshold_metrics:
            raise ValueError(
                "evaluation gate result metrics must exactly "
                "match gate thresholds"
            )

        passed = all(
            _threshold_passes(
                threshold=threshold,
                value=result_by_metric[
                    threshold.metric
                ].value,
            )
            for threshold in self.gate.thresholds
        )

        expected_decision = (
            EvaluationGateDecision.PASSED
            if passed
            else EvaluationGateDecision.FAILED
        )

        if self.decision is not expected_decision:
            raise ValueError(
                "evaluation gate decision does not match "
                "threshold results"
            )

        return self


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
