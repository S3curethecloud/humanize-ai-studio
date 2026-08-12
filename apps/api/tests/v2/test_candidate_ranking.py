from __future__ import annotations

import pytest

from app.domain.models import (
    EditorialQualityDecision,
    ReleaseDecision,
)
from app.v2.domain.candidate_ranking import (
    CANDIDATE_RANKING_VERSION,
    CandidateEligibility,
    CandidateIneligibilityReason,
    CandidateRankingInput,
    CandidateSelectionDecision,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.services.candidate_ranker import (
    CandidateRanker,
    CandidateRankingError,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
)


def _input(
    *,
    candidate_id: str,
    ordinal: int,
    v1: ReleaseDecision = ReleaseDecision.PASS,
    claim_lock: ClaimLockValidationDecision = (ClaimLockValidationDecision.PASS),
    mode: ClaimLockEnforcementMode | None = (ClaimLockEnforcementMode.STRICT),
    editorial: EditorialQualityDecision = (EditorialQualityDecision.PASS),
    naturalness: float = 0.90,
    remaining_flags: int = 0,
    changed_segments: int = 2,
) -> CandidateRankingInput:
    return CandidateRankingInput(
        candidate_id=candidate_id,
        ordinal=ordinal,
        v1_release_decision=v1,
        claim_lock_validation_decision=(claim_lock),
        claim_lock_enforcement_mode=mode,
        editorial_quality_decision=editorial,
        naturalness_score=naturalness,
        remaining_flag_count=remaining_flags,
        changed_segment_count=changed_segments,
    )


def test_ranking_is_deterministic() -> None:
    ranker = CandidateRanker()

    inputs = (
        _input(
            candidate_id="candidate-1",
            ordinal=1,
            naturalness=0.80,
        ),
        _input(
            candidate_id="candidate-2",
            ordinal=2,
            naturalness=0.95,
        ),
        _input(
            candidate_id="candidate-3",
            ordinal=3,
            naturalness=0.90,
        ),
    )

    first = ranker.rank(
        candidate_set_id="set-1",
        inputs=inputs,
    )
    second = ranker.rank(
        candidate_set_id="set-1",
        inputs=inputs,
    )

    assert first == second
    assert first.ranking_version == CANDIDATE_RANKING_VERSION


def test_v1_fail_is_ineligible() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="candidate-1",
                ordinal=1,
                v1=ReleaseDecision.FAIL,
            ),
            _input(
                candidate_id="candidate-2",
                ordinal=2,
            ),
        ),
    )

    failed = next(item for item in result.ranked_candidates if item.candidate_id == "candidate-1")

    assert failed.eligibility is CandidateEligibility.INELIGIBLE
    assert CandidateIneligibilityReason.V1_FAILED in failed.ineligibility_reasons
    assert failed.rank is None


def test_strict_claim_lock_violation_is_ineligible() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="candidate-1",
                ordinal=1,
                claim_lock=(ClaimLockValidationDecision.VIOLATION),
                mode=(ClaimLockEnforcementMode.STRICT),
            ),
            _input(
                candidate_id="candidate-2",
                ordinal=2,
            ),
        ),
    )

    blocked = next(item for item in result.ranked_candidates if item.candidate_id == "candidate-1")

    assert blocked.eligibility is CandidateEligibility.INELIGIBLE
    assert CandidateIneligibilityReason.STRICT_CLAIM_LOCK_VIOLATION in blocked.ineligibility_reasons


def test_audit_only_claim_lock_violation_remains_eligible() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="candidate-1",
                ordinal=1,
                claim_lock=(ClaimLockValidationDecision.VIOLATION),
                mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
            ),
            _input(
                candidate_id="candidate-2",
                ordinal=2,
                claim_lock=(ClaimLockValidationDecision.PASS),
            ),
        ),
    )

    audit_only = next(
        item for item in result.ranked_candidates if item.candidate_id == "candidate-1"
    )

    assert audit_only.eligibility is CandidateEligibility.ELIGIBLE
    assert audit_only.claim_lock_validation_decision is ClaimLockValidationDecision.VIOLATION


def test_v1_pass_ranks_before_v1_warn() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="warn",
                ordinal=1,
                v1=ReleaseDecision.WARN,
                naturalness=1.0,
            ),
            _input(
                candidate_id="pass",
                ordinal=2,
                v1=ReleaseDecision.PASS,
                naturalness=0.5,
            ),
        ),
    )

    assert result.selected_candidate_id == "pass"


def test_claim_lock_pass_ranks_before_audit_only_violation() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="audit",
                ordinal=1,
                claim_lock=(ClaimLockValidationDecision.VIOLATION),
                mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
                naturalness=1.0,
            ),
            _input(
                candidate_id="clean",
                ordinal=2,
                naturalness=0.5,
            ),
        ),
    )

    assert result.selected_candidate_id == "clean"


def test_editorial_pass_ranks_before_review() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="review",
                ordinal=1,
                editorial=(EditorialQualityDecision.REVIEW),
                naturalness=1.0,
            ),
            _input(
                candidate_id="pass",
                ordinal=2,
                editorial=(EditorialQualityDecision.PASS),
                naturalness=0.5,
            ),
        ),
    )

    assert result.selected_candidate_id == "pass"


def test_higher_naturalness_breaks_control_safe_tie() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="candidate-1",
                ordinal=1,
                naturalness=0.80,
            ),
            _input(
                candidate_id="candidate-2",
                ordinal=2,
                naturalness=0.95,
            ),
        ),
    )

    assert result.selected_candidate_id == "candidate-2"


def test_fewer_remaining_flags_breaks_naturalness_tie() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="candidate-1",
                ordinal=1,
                naturalness=0.90,
                remaining_flags=2,
            ),
            _input(
                candidate_id="candidate-2",
                ordinal=2,
                naturalness=0.90,
                remaining_flags=0,
            ),
        ),
    )

    assert result.selected_candidate_id == "candidate-2"


def test_fewer_changed_segments_breaks_quality_tie() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="candidate-1",
                ordinal=1,
                changed_segments=4,
            ),
            _input(
                candidate_id="candidate-2",
                ordinal=2,
                changed_segments=2,
            ),
        ),
    )

    assert result.selected_candidate_id == "candidate-2"


def test_ordinal_is_final_deterministic_tie_breaker() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="candidate-2",
                ordinal=2,
            ),
            _input(
                candidate_id="candidate-1",
                ordinal=1,
            ),
        ),
    )

    assert result.selected_candidate_id == "candidate-1"


def test_none_eligible_produces_explicit_selection_evidence() -> None:
    result = CandidateRanker().rank(
        candidate_set_id="set-1",
        inputs=(
            _input(
                candidate_id="candidate-1",
                ordinal=1,
                v1=ReleaseDecision.FAIL,
            ),
            _input(
                candidate_id="candidate-2",
                ordinal=2,
                v1=ReleaseDecision.FAIL,
            ),
        ),
    )

    assert result.decision is CandidateSelectionDecision.NONE_ELIGIBLE
    assert result.selected_candidate_id is None
    assert all(item.rank is None for item in result.ranked_candidates)


@pytest.mark.parametrize(
    "input_count",
    (
        1,
        6,
    ),
)
def test_ranker_rejects_unsupported_candidate_count(
    input_count: int,
) -> None:
    inputs = tuple(
        _input(
            candidate_id=f"candidate-{ordinal}",
            ordinal=ordinal,
        )
        for ordinal in range(
            1,
            input_count + 1,
        )
    )

    with pytest.raises(
        CandidateRankingError,
        match="between 2 and 5",
    ):
        CandidateRanker().rank(
            candidate_set_id="set-1",
            inputs=inputs,
        )


def test_ranker_rejects_duplicate_candidate_ids() -> None:
    with pytest.raises(
        CandidateRankingError,
        match="must be unique",
    ):
        CandidateRanker().rank(
            candidate_set_id="set-1",
            inputs=(
                _input(
                    candidate_id="duplicate",
                    ordinal=1,
                ),
                _input(
                    candidate_id="duplicate",
                    ordinal=2,
                ),
            ),
        )
