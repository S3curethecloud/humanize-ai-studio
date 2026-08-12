from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.domain.models import (
    EditorialQualityDecision,
    ReleaseDecision,
)
from app.v2.domain.candidate_audit import (
    CANDIDATE_AUDIT_VERSION,
    CandidateAuditSnapshot,
    CandidateClaimLockControlSnapshot,
    CandidateControlAuditSnapshot,
)
from app.v2.domain.candidate_ranking import (
    CandidateEligibility,
    CandidateRankingResult,
    CandidateSelectionDecision,
    CandidateSelectionEvidence,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.rewrite_candidates import (
    RewriteCandidate,
    RewriteCandidateSet,
)
from app.v2.services.candidate_audit_builder import (
    CandidateAuditBuilder,
    CandidateAuditBuildError,
)
from app.v2.services.candidate_control_enforcement import (
    CandidateControlEvidence,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
)


def _validation(
    *,
    decision: ClaimLockValidationDecision = (ClaimLockValidationDecision.PASS),
    mode: ClaimLockEnforcementMode = (ClaimLockEnforcementMode.STRICT),
) -> ClaimLockValidationResult:
    return ClaimLockValidationResult(
        lock_id="lock_test",
        enforcement_mode=mode,
        decision=decision,
        checks=(),
    )


def _ranking_result(
    *,
    candidate_id: str,
    ordinal: int,
    rank: int,
) -> CandidateRankingResult:
    return CandidateRankingResult(
        candidate_id=candidate_id,
        ordinal=ordinal,
        rank=rank,
        eligibility=CandidateEligibility.ELIGIBLE,
        ineligibility_reasons=(),
        v1_release_decision=ReleaseDecision.PASS,
        claim_lock_validation_decision=(ClaimLockValidationDecision.PASS),
        claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
        editorial_quality_decision=(EditorialQualityDecision.PASS),
        naturalness_score=0.9,
        remaining_flag_count=0,
        changed_segment_count=2,
    )


def _selection() -> CandidateSelectionEvidence:
    return CandidateSelectionEvidence(
        candidate_set_id="candidate-set-1",
        decision=(CandidateSelectionDecision.SELECTED),
        selected_candidate_id="candidate-1",
        ranked_candidates=(
            _ranking_result(
                candidate_id="candidate-1",
                ordinal=1,
                rank=1,
            ),
            _ranking_result(
                candidate_id="candidate-2",
                ordinal=2,
                rank=2,
            ),
        ),
    )


def _controlled_execution() -> Any:
    candidates = RewriteCandidateSet(
        candidate_set_id="candidate-set-1",
        source_text="Source.",
        candidates=(
            RewriteCandidate(
                candidate_id="candidate-1",
                ordinal=1,
                rewritten_text="Candidate one.",
            ),
            RewriteCandidate(
                candidate_id="candidate-2",
                ordinal=2,
                rewritten_text="Candidate two.",
            ),
        ),
    )

    controls = (
        CandidateControlEvidence(
            candidate_id="candidate-1",
            ordinal=1,
            v1_release_decision=(ReleaseDecision.PASS),
            claim_lock_validation=_validation(),
        ),
        CandidateControlEvidence(
            candidate_id="candidate-2",
            ordinal=2,
            v1_release_decision=(ReleaseDecision.WARN),
            claim_lock_validation=_validation(),
        ),
    )

    return SimpleNamespace(
        generation=SimpleNamespace(
            candidate_set=candidates,
        ),
        controls=controls,
    )


def test_candidate_audit_builder_preserves_set_identity() -> None:
    snapshot = CandidateAuditBuilder().build(
        controlled_execution=_controlled_execution(),
        selection=_selection(),
    )

    assert snapshot.audit_version == CANDIDATE_AUDIT_VERSION
    assert snapshot.candidate_set_id == "candidate-set-1"


def test_candidate_audit_builder_preserves_control_order() -> None:
    snapshot = CandidateAuditBuilder().build(
        controlled_execution=_controlled_execution(),
        selection=_selection(),
    )

    assert tuple(control.candidate_id for control in snapshot.controls) == (
        "candidate-1",
        "candidate-2",
    )

    assert tuple(control.ordinal for control in snapshot.controls) == (
        1,
        2,
    )


def test_candidate_audit_preserves_v1_decisions() -> None:
    snapshot = CandidateAuditBuilder().build(
        controlled_execution=_controlled_execution(),
        selection=_selection(),
    )

    assert tuple(control.v1_release_decision for control in snapshot.controls) == (
        ReleaseDecision.PASS,
        ReleaseDecision.WARN,
    )


def test_candidate_audit_preserves_claim_lock_evidence() -> None:
    snapshot = CandidateAuditBuilder().build(
        controlled_execution=_controlled_execution(),
        selection=_selection(),
    )

    control = snapshot.controls[0]

    assert control.claim_lock.lock_id == "lock_test"
    assert control.claim_lock.enforcement_mode is ClaimLockEnforcementMode.STRICT
    assert control.claim_lock.decision is ClaimLockValidationDecision.PASS


def test_candidate_audit_preserves_selection_linkage() -> None:
    snapshot = CandidateAuditBuilder().build(
        controlled_execution=_controlled_execution(),
        selection=_selection(),
    )

    assert snapshot.selected_candidate_id == "candidate-1"
    assert snapshot.selection.selected_candidate_id == "candidate-1"


def test_candidate_audit_rejects_selection_set_mismatch() -> None:
    selection = _selection().model_copy(
        update={
            "candidate_set_id": "other-set",
        }
    )

    with pytest.raises(
        CandidateAuditBuildError,
        match="does not match",
    ):
        CandidateAuditBuilder().build(
            controlled_execution=(_controlled_execution()),
            selection=selection,
        )


def test_candidate_audit_rejects_missing_control() -> None:
    controlled = _controlled_execution()
    controlled.controls = (controlled.controls[0],)

    with pytest.raises(
        CandidateAuditBuildError,
        match="one control",
    ):
        CandidateAuditBuilder().build(
            controlled_execution=controlled,
            selection=_selection(),
        )


def test_candidate_audit_domain_rejects_candidate_id_mismatch() -> None:
    controls = (
        CandidateControlAuditSnapshot(
            candidate_id="candidate-1",
            ordinal=1,
            v1_release_decision=(ReleaseDecision.PASS),
            claim_lock=(
                CandidateClaimLockControlSnapshot(
                    validator_version=("claim-lock-validator-v1"),
                    lock_id="lock_test",
                    enforcement_mode=(ClaimLockEnforcementMode.STRICT),
                    decision=(ClaimLockValidationDecision.PASS),
                )
            ),
        ),
        CandidateControlAuditSnapshot(
            candidate_id="candidate-X",
            ordinal=2,
            v1_release_decision=(ReleaseDecision.PASS),
            claim_lock=(
                CandidateClaimLockControlSnapshot(
                    validator_version=("claim-lock-validator-v1"),
                    lock_id="lock_test",
                    enforcement_mode=(ClaimLockEnforcementMode.STRICT),
                    decision=(ClaimLockValidationDecision.PASS),
                )
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="must match",
    ):
        CandidateAuditSnapshot(
            candidate_set_id="candidate-set-1",
            controls=controls,
            selection=_selection(),
            selected_candidate_id="candidate-1",
        )


def test_no_claim_lock_snapshot_requires_empty_pass() -> None:
    snapshot = CandidateClaimLockControlSnapshot(
        validator_version=("claim-lock-validator-v1"),
        lock_id=None,
        enforcement_mode=None,
        decision=ClaimLockValidationDecision.PASS,
        violating_item_ids=(),
        unevaluated_claim_ids=(),
    )

    assert snapshot.lock_id is None


def test_no_claim_lock_snapshot_rejects_violation() -> None:
    with pytest.raises(
        ValueError,
        match="empty pass",
    ):
        CandidateClaimLockControlSnapshot(
            validator_version=("claim-lock-validator-v1"),
            lock_id=None,
            enforcement_mode=None,
            decision=(ClaimLockValidationDecision.VIOLATION),
            violating_item_ids=("term-1",),
        )
