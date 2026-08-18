from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.domain.models import (
    EditorialQualityDecision,
    ReleaseDecision,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
)

CANDIDATE_RANKING_VERSION = "candidate-ranking-v1"


class CandidateEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class CandidateIneligibilityReason(StrEnum):
    V1_FAILED = "v1_failed"
    STRICT_CLAIM_LOCK_VIOLATION = "strict_claim_lock_violation"


class CandidateSelectionDecision(StrEnum):
    SELECTED = "selected"
    NONE_ELIGIBLE = "none_eligible"


class CandidateRankingInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(ge=1)

    v1_release_decision: ReleaseDecision

    claim_lock_validation_decision: ClaimLockValidationDecision
    claim_lock_enforcement_mode: ClaimLockEnforcementMode | None = None

    editorial_quality_decision: EditorialQualityDecision
    naturalness_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    remaining_flag_count: int = Field(ge=0)
    changed_segment_count: int = Field(ge=0)


class CandidateRankingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(ge=1)
    rank: int | None = Field(
        default=None,
        ge=1,
    )

    eligibility: CandidateEligibility
    ineligibility_reasons: tuple[
        CandidateIneligibilityReason,
        ...,
    ] = ()

    v1_release_decision: ReleaseDecision
    claim_lock_validation_decision: ClaimLockValidationDecision
    claim_lock_enforcement_mode: ClaimLockEnforcementMode | None

    editorial_quality_decision: EditorialQualityDecision
    naturalness_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    remaining_flag_count: int = Field(ge=0)
    changed_segment_count: int = Field(ge=0)

    @model_validator(mode="after")
    def require_eligibility_shape(
        self,
    ) -> CandidateRankingResult:
        if self.eligibility is CandidateEligibility.ELIGIBLE:
            if self.ineligibility_reasons:
                raise ValueError("eligible candidate cannot have ineligibility reasons")

            if self.rank is None:
                raise ValueError("eligible candidate requires rank")

        else:
            if not self.ineligibility_reasons:
                raise ValueError("ineligible candidate requires at least one reason")

            if self.rank is not None:
                raise ValueError("ineligible candidate cannot have rank")

        return self


class CandidateSelectionEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    ranking_version: str = Field(
        default=CANDIDATE_RANKING_VERSION,
        min_length=1,
        max_length=200,
    )
    candidate_set_id: str = Field(
        min_length=1,
        max_length=200,
    )
    decision: CandidateSelectionDecision
    selected_candidate_id: str | None = Field(
        default=None,
        max_length=200,
    )
    ranked_candidates: tuple[
        CandidateRankingResult,
        ...,
    ] = Field(
        min_length=2,
        max_length=5,
    )

    @model_validator(mode="after")
    def require_selection_integrity(
        self,
    ) -> CandidateSelectionEvidence:
        candidate_ids = tuple(candidate.candidate_id for candidate in self.ranked_candidates)

        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("ranked candidate IDs must be unique")

        eligible = tuple(
            candidate
            for candidate in self.ranked_candidates
            if (candidate.eligibility is CandidateEligibility.ELIGIBLE)
        )

        ranks = tuple(candidate.rank for candidate in eligible)

        if ranks != tuple(
            range(
                1,
                len(eligible) + 1,
            )
        ):
            raise ValueError("eligible candidate ranks must be contiguous and ordered from 1")

        if self.decision is CandidateSelectionDecision.SELECTED:
            if self.selected_candidate_id is None:
                raise ValueError("selected decision requires selected_candidate_id")

            if not eligible:
                raise ValueError("selected decision requires an eligible candidate")

            if self.selected_candidate_id != eligible[0].candidate_id:
                raise ValueError("selected candidate must be rank 1 eligible candidate")

        else:
            if self.selected_candidate_id is not None:
                raise ValueError("none_eligible decision cannot contain selected_candidate_id")

            if eligible:
                raise ValueError("none_eligible decision cannot contain eligible candidates")

        return self
