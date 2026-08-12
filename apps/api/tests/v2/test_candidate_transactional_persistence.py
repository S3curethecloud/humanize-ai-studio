from __future__ import annotations

from pathlib import Path

from app.domain.models import (
    EditorialQualityDecision,
    ReleaseDecision,
)
from app.v2.domain.candidate_audit import (
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
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.repositories.sqlite import (
    SQLiteRewriteHistoryRepository,
)
from app.v2.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
)
from app.v2.services.transaction_service import (
    TransactionService,
)


def _candidate_audit() -> CandidateAuditSnapshot:
    controls = (
        CandidateControlAuditSnapshot(
            candidate_id="candidate-1",
            ordinal=1,
            v1_release_decision=ReleaseDecision.PASS,
            claim_lock=(
                CandidateClaimLockControlSnapshot(
                    validator_version=("claim-lock-validator-v1"),
                    lock_id="lock_transactional",
                    enforcement_mode=(ClaimLockEnforcementMode.STRICT),
                    decision=(ClaimLockValidationDecision.PASS),
                )
            ),
        ),
        CandidateControlAuditSnapshot(
            candidate_id="candidate-2",
            ordinal=2,
            v1_release_decision=ReleaseDecision.WARN,
            claim_lock=(
                CandidateClaimLockControlSnapshot(
                    validator_version=("claim-lock-validator-v1"),
                    lock_id="lock_transactional",
                    enforcement_mode=(ClaimLockEnforcementMode.STRICT),
                    decision=(ClaimLockValidationDecision.PASS),
                )
            ),
        ),
    )

    ranking = (
        CandidateRankingResult(
            candidate_id="candidate-1",
            ordinal=1,
            rank=1,
            eligibility=CandidateEligibility.ELIGIBLE,
            ineligibility_reasons=(),
            v1_release_decision=ReleaseDecision.PASS,
            claim_lock_validation_decision=(ClaimLockValidationDecision.PASS),
            claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
            editorial_quality_decision=(EditorialQualityDecision.PASS),
            naturalness_score=0.95,
            remaining_flag_count=0,
            changed_segment_count=2,
        ),
        CandidateRankingResult(
            candidate_id="candidate-2",
            ordinal=2,
            rank=2,
            eligibility=CandidateEligibility.ELIGIBLE,
            ineligibility_reasons=(),
            v1_release_decision=ReleaseDecision.WARN,
            claim_lock_validation_decision=(ClaimLockValidationDecision.PASS),
            claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
            editorial_quality_decision=(EditorialQualityDecision.PASS),
            naturalness_score=0.90,
            remaining_flag_count=0,
            changed_segment_count=3,
        ),
    )

    selection = CandidateSelectionEvidence(
        candidate_set_id="candidate-set-transactional",
        decision=CandidateSelectionDecision.SELECTED,
        selected_candidate_id="candidate-1",
        ranked_candidates=ranking,
    )

    return CandidateAuditSnapshot(
        candidate_set_id="candidate-set-transactional",
        controls=controls,
        selection=selection,
        selected_candidate_id="candidate-1",
    )


def _record(
    *,
    workspace_id: str,
    user_id: str,
    candidate_audit_snapshot: (CandidateAuditSnapshot | None),
) -> RewriteHistoryRecord:
    return RewriteHistoryRecord(
        rewrite_id=(
            "history-transactional-candidate"
            if candidate_audit_snapshot is not None
            else "history-transactional-single"
        ),
        workspace_id=workspace_id,
        user_id=user_id,
        trace_id=(
            "trace-transactional-candidate"
            if candidate_audit_snapshot is not None
            else "trace-transactional-single"
        ),
        source_text="Original text.",
        rewritten_text="Selected rewrite.",
        document_type="general",
        audience="general audience",
        tone="natural",
        intensity="natural_rewrite",
        provider_name="test-provider",
        model_name="test-model",
        prompt_version="test-v1",
        candidate_set_id=(
            candidate_audit_snapshot.candidate_set_id
            if candidate_audit_snapshot is not None
            else None
        ),
        candidate_audit_snapshot=(candidate_audit_snapshot),
        selected_candidate_id=(
            candidate_audit_snapshot.selected_candidate_id
            if candidate_audit_snapshot is not None
            else None
        ),
        fallback_used=False,
        verification_decision="pass",
        editorial_quality_decision="pass",
    )


def _workspace(
    database_path: Path,
) -> tuple[
    TransactionService,
    str,
    str,
]:
    service = TransactionService(SQLiteUnitOfWork(database_path))

    user, workspace, _ = service.create_user_and_workspace(
        email="candidate@example.com",
        display_name="Candidate Owner",
        workspace_name="Candidate Workspace",
    )

    return (
        service,
        workspace.workspace_id,
        user.user_id,
    )


def test_candidate_audit_persists_transactionally(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "candidate-transactional.db"

    service, workspace_id, user_id = _workspace(database_path)

    audit = _candidate_audit()

    record = _record(
        workspace_id=workspace_id,
        user_id=user_id,
        candidate_audit_snapshot=audit,
    )

    service.record_history(record=record)

    repository = SQLiteRewriteHistoryRepository(database_path)

    loaded = repository.get(record.rewrite_id)

    assert loaded == record


def test_transactional_candidate_selection_linkage_survives_reopen(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "candidate-selection.db"

    service, workspace_id, user_id = _workspace(database_path)

    audit = _candidate_audit()

    record = _record(
        workspace_id=workspace_id,
        user_id=user_id,
        candidate_audit_snapshot=audit,
    )

    service.record_history(record=record)

    reopened = SQLiteRewriteHistoryRepository(database_path)

    loaded = reopened.get(record.rewrite_id)

    assert loaded is not None
    assert loaded.candidate_set_id == "candidate-set-transactional"
    assert loaded.selected_candidate_id == "candidate-1"
    assert loaded.candidate_audit_snapshot == audit


def test_single_result_history_remains_transactionally_compatible(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "single-transactional.db"

    service, workspace_id, user_id = _workspace(database_path)

    record = _record(
        workspace_id=workspace_id,
        user_id=user_id,
        candidate_audit_snapshot=None,
    )

    service.record_history(record=record)

    repository = SQLiteRewriteHistoryRepository(database_path)

    loaded = repository.get(record.rewrite_id)

    assert loaded == record
    assert loaded is not None
    assert loaded.candidate_set_id is None
    assert loaded.candidate_audit_snapshot is None
    assert loaded.selected_candidate_id is None
