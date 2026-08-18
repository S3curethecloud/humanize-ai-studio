from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.v2.domain.eval_ops import (
    EVAL_OPS_VERSION,
    EvaluationMetricResult,
)


class EvaluationMetricMethod(StrEnum):
    CLAIM_REFERENCE_CHECKS = "claim_reference_checks"
    EXPLICIT_NATURALNESS_SCORE = (
        "explicit_naturalness_score"
    )
    CHARACTER_SEQUENCE_DISTANCE = (
        "character_sequence_distance"
    )
    EXECUTION_LATENCY = "execution_latency"
    PROVIDER_ERROR_INDICATOR = (
        "provider_error_indicator"
    )


class EvaluationCaseExecutionEvidence(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    case_id: str = Field(
        min_length=1,
        max_length=200,
    )
    output_text: str | None = Field(
        default=None,
        min_length=1,
        max_length=20_000,
    )
    latency_ms: float | None = Field(
        default=None,
        ge=0.0,
    )
    provider_error: bool = False
    provider_error_category: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    naturalness_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def require_provider_error_integrity(
        self,
    ) -> EvaluationCaseExecutionEvidence:
        if (
            self.provider_error
            and self.provider_error_category is None
        ):
            raise ValueError(
                "provider error evidence requires "
                "provider_error_category"
            )

        if (
            not self.provider_error
            and self.provider_error_category is not None
        ):
            raise ValueError(
                "provider_error_category requires "
                "provider_error evidence"
            )

        return self


class EvaluationMetricMeasurement(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    case_id: str = Field(
        min_length=1,
        max_length=200,
    )
    result: EvaluationMetricResult
    method: EvaluationMetricMethod
