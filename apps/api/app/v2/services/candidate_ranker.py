from __future__ import annotations

from app.domain.models import (
    EditorialQualityDecision,
    ReleaseDecision,
)
from app.v2.domain.candidate_ranking import (
    CANDIDATE_RANKING_VERSION,
    CandidateEligibility,
    CandidateIneligibilityReason,
    CandidateRankingInput,
    CandidateRankingResult,
    CandidateSelectionDecision,
    CandidateSelectionEvidence,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.rewrite_candidates import (
    RewriteCandidateDiffSet,
)
from app.v2.services.candidate_control_enforcement import (
    ControlledCandidateGenerationExecution,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
)


class CandidateRankingError(ValueError):
    pass


class CandidateRanker:
    version = CANDIDATE_RANKING_VERSION

    def build_inputs(
        self,
        *,
        controlled_execution: (ControlledCandidateGenerationExecution),
        diff_set: RewriteCandidateDiffSet,
    ) -> tuple[
        CandidateRankingInput,
        ...,
    ]:
        candidate_set = controlled_execution.generation.candidate_set

        if diff_set.candidate_set_id != candidate_set.candidate_set_id:
            raise CandidateRankingError(
                "candidate diff set does not match controlled candidate set"
            )

        candidates = candidate_set.candidates
        responses = controlled_execution.generation.responses
        controls = controlled_execution.controls
        diffs = diff_set.diffs

        expected_count = len(candidates)

        if not (len(responses) == expected_count == len(controls) == len(diffs)):
            raise CandidateRankingError(
                "candidate ranking requires aligned candidate, response, control, and diff evidence"
            )

        ranking_inputs: list[CandidateRankingInput] = []

        for (
            candidate,
            response,
            control,
            candidate_diff,
        ) in zip(
            candidates,
            responses,
            controls,
            diffs,
            strict=True,
        ):
            if (
                candidate.candidate_id != control.candidate_id
                or candidate.candidate_id != candidate_diff.candidate_id
            ):
                raise CandidateRankingError("candidate ranking evidence IDs are not aligned")

            if candidate.ordinal != control.ordinal:
                raise CandidateRankingError("candidate ranking ordinals are not aligned")

            ranking_inputs.append(
                CandidateRankingInput(
                    candidate_id=(candidate.candidate_id),
                    ordinal=candidate.ordinal,
                    v1_release_decision=(control.v1_release_decision),
                    claim_lock_validation_decision=(control.claim_lock_validation.decision),
                    claim_lock_enforcement_mode=(control.claim_lock_validation.enforcement_mode),
                    editorial_quality_decision=(response.editorial_quality.decision),
                    naturalness_score=(response.editorial_quality.naturalness_score),
                    remaining_flag_count=(response.editorial_quality.remaining_flag_count),
                    changed_segment_count=(candidate_diff.changed_segment_count),
                )
            )

        return tuple(ranking_inputs)

    def rank(
        self,
        *,
        candidate_set_id: str,
        inputs: tuple[
            CandidateRankingInput,
            ...,
        ],
    ) -> CandidateSelectionEvidence:
        if not 2 <= len(inputs) <= 5:
            raise CandidateRankingError("candidate ranking requires between 2 and 5 inputs")

        candidate_ids = tuple(item.candidate_id for item in inputs)

        if len(set(candidate_ids)) != len(candidate_ids):
            raise CandidateRankingError("candidate ranking input IDs must be unique")

        eligible_inputs: list[CandidateRankingInput] = []
        ineligible: list[
            tuple[
                CandidateRankingInput,
                tuple[
                    CandidateIneligibilityReason,
                    ...,
                ],
            ]
        ] = []

        for item in inputs:
            reasons = self._ineligibility_reasons(item)

            if reasons:
                ineligible.append(
                    (
                        item,
                        reasons,
                    )
                )
            else:
                eligible_inputs.append(item)

        ordered_eligible = sorted(
            eligible_inputs,
            key=self._ranking_key,
        )

        ranked: list[CandidateRankingResult] = []

        for rank, item in enumerate(
            ordered_eligible,
            start=1,
        ):
            ranked.append(
                self._result(
                    item=item,
                    rank=rank,
                    eligibility=(CandidateEligibility.ELIGIBLE),
                    reasons=(),
                )
            )

        for item, reasons in sorted(
            ineligible,
            key=lambda entry: entry[0].ordinal,
        ):
            ranked.append(
                self._result(
                    item=item,
                    rank=None,
                    eligibility=(CandidateEligibility.INELIGIBLE),
                    reasons=reasons,
                )
            )

        if ordered_eligible:
            decision = CandidateSelectionDecision.SELECTED
            selected_candidate_id = ordered_eligible[0].candidate_id
        else:
            decision = CandidateSelectionDecision.NONE_ELIGIBLE
            selected_candidate_id = None

        return CandidateSelectionEvidence(
            ranking_version=self.version,
            candidate_set_id=candidate_set_id,
            decision=decision,
            selected_candidate_id=(selected_candidate_id),
            ranked_candidates=tuple(ranked),
        )

    def select(
        self,
        *,
        controlled_execution: (ControlledCandidateGenerationExecution),
        diff_set: RewriteCandidateDiffSet,
    ) -> CandidateSelectionEvidence:
        inputs = self.build_inputs(
            controlled_execution=(controlled_execution),
            diff_set=diff_set,
        )

        return self.rank(
            candidate_set_id=(controlled_execution.generation.candidate_set.candidate_set_id),
            inputs=inputs,
        )

    @staticmethod
    def _ineligibility_reasons(
        item: CandidateRankingInput,
    ) -> tuple[
        CandidateIneligibilityReason,
        ...,
    ]:
        reasons: list[CandidateIneligibilityReason] = []

        if item.v1_release_decision is ReleaseDecision.FAIL:
            reasons.append(CandidateIneligibilityReason.V1_FAILED)

        if (
            item.claim_lock_validation_decision is ClaimLockValidationDecision.VIOLATION
            and item.claim_lock_enforcement_mode is ClaimLockEnforcementMode.STRICT
        ):
            reasons.append(CandidateIneligibilityReason.STRICT_CLAIM_LOCK_VIOLATION)

        return tuple(reasons)

    @staticmethod
    def _ranking_key(
        item: CandidateRankingInput,
    ) -> tuple[
        int,
        int,
        int,
        float,
        int,
        int,
        int,
    ]:
        release_priority = {
            ReleaseDecision.PASS: 0,
            ReleaseDecision.WARN: 1,
            ReleaseDecision.FAIL: 2,
        }[item.v1_release_decision]

        claim_lock_priority = (
            0 if (item.claim_lock_validation_decision is ClaimLockValidationDecision.PASS) else 1
        )

        editorial_priority = (
            0 if (item.editorial_quality_decision is EditorialQualityDecision.PASS) else 1
        )

        return (
            release_priority,
            claim_lock_priority,
            editorial_priority,
            -item.naturalness_score,
            item.remaining_flag_count,
            item.changed_segment_count,
            item.ordinal,
        )

    @staticmethod
    def _result(
        *,
        item: CandidateRankingInput,
        rank: int | None,
        eligibility: CandidateEligibility,
        reasons: tuple[
            CandidateIneligibilityReason,
            ...,
        ],
    ) -> CandidateRankingResult:
        return CandidateRankingResult(
            candidate_id=item.candidate_id,
            ordinal=item.ordinal,
            rank=rank,
            eligibility=eligibility,
            ineligibility_reasons=reasons,
            v1_release_decision=(item.v1_release_decision),
            claim_lock_validation_decision=(item.claim_lock_validation_decision),
            claim_lock_enforcement_mode=(item.claim_lock_enforcement_mode),
            editorial_quality_decision=(item.editorial_quality_decision),
            naturalness_score=(item.naturalness_score),
            remaining_flag_count=(item.remaining_flag_count),
            changed_segment_count=(item.changed_segment_count),
        )
