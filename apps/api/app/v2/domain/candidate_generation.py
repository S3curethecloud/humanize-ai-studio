from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class CandidateGenerationStrategy(StrEnum):
    BALANCED = "balanced"
    CONCISE = "concise"
    STRUCTURAL = "structural"
    FLOW = "flow"
    DIRECT = "direct"


class CandidateGenerationVariant(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(
        ge=1,
    )
    strategy: CandidateGenerationStrategy
    instruction: str = Field(
        min_length=1,
        max_length=1000,
    )


class CandidateGenerationPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_version: str = Field(
        default="candidate-generation-plan-v1",
        min_length=1,
        max_length=200,
    )
    candidate_set_id: str = Field(
        min_length=1,
        max_length=200,
    )
    candidate_count: int = Field(
        ge=2,
        le=5,
    )
    variants: tuple[
        CandidateGenerationVariant,
        ...,
    ] = Field(
        min_length=2,
        max_length=5,
    )

    @model_validator(mode="after")
    def require_plan_integrity(
        self,
    ) -> CandidateGenerationPlan:
        if len(self.variants) != self.candidate_count:
            raise ValueError("candidate_count must match variants length")

        candidate_ids = tuple(variant.candidate_id for variant in self.variants)

        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate generation IDs must be unique")

        ordinals = tuple(variant.ordinal for variant in self.variants)

        expected_ordinals = tuple(
            range(
                1,
                self.candidate_count + 1,
            )
        )

        if ordinals != expected_ordinals:
            raise ValueError("candidate generation ordinals must be contiguous and ordered from 1")

        strategies = tuple(variant.strategy for variant in self.variants)

        if len(set(strategies)) != len(strategies):
            raise ValueError("candidate generation strategies must be unique")

        return self
