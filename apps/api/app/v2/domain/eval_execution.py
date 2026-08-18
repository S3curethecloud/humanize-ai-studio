from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.v2.domain.eval_metrics import (
    EvaluationCaseExecutionEvidence,
)
from app.v2.domain.eval_ops import (
    EVAL_OPS_VERSION,
    EvaluationDatasetIdentity,
    EvaluationMetric,
)


class EvaluationRunRequest(BaseModel):
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
    metrics: tuple[
        EvaluationMetric,
        ...,
    ] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def require_unique_metrics(
        self,
    ) -> EvaluationRunRequest:
        if len(set(self.metrics)) != len(self.metrics):
            raise ValueError(
                "evaluation run metrics must be unique"
            )

        return self


class EvaluationCaseExecutionResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    eval_version: Literal["eval-ops-v1"] = EVAL_OPS_VERSION

    target_id: str = Field(
        min_length=1,
        max_length=200,
    )
    evidence: EvaluationCaseExecutionEvidence
