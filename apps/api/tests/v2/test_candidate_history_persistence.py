from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

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
    initialize_database,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
)


def _candidate_audit() -> CandidateAuditSnapshot:
    controls = (
        CandidateControlAuditSnapshot(
            candidate_id="candidate-1",
            ordinal=1,
            v1_release_decision=ReleaseDecision.PASS,
            claim_lock=CandidateClaimLockControlSnapshot(
                validator_version="claim-lock-validator-v1",
                lock_id="lock_test",
                enforcement_mode=(ClaimLockEnforcementMode.STRICT),
                decision=ClaimLockValidationDecision.PASS,
            ),
        ),
        CandidateControlAuditSnapshot(
            candidate_id="candidate-2",
            ordinal=2,
            v1_release_decision=ReleaseDecision.WARN,
            claim_lock=CandidateClaimLockControlSnapshot(
                validator_version="claim-lock-validator-v1",
                lock_id="lock_test",
                enforcement_mode=(ClaimLockEnforcementMode.STRICT),
                decision=ClaimLockValidationDecision.PASS,
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
        candidate_set_id="candidate-set-1",
        decision=CandidateSelectionDecision.SELECTED,
        selected_candidate_id="candidate-1",
        ranked_candidates=ranking,
    )

    return CandidateAuditSnapshot(
        candidate_set_id="candidate-set-1",
        controls=controls,
        selection=selection,
        selected_candidate_id="candidate-1",
    )


def _history_record(
    *,
    candidate_audit_snapshot: (CandidateAuditSnapshot | None) = None,
) -> RewriteHistoryRecord:
    return RewriteHistoryRecord(
        rewrite_id="history-candidate",
        workspace_id="workspace-1",
        user_id="user-1",
        trace_id="trace-1",
        source_text="Original text.",
        rewritten_text="Selected candidate text.",
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


def _seed_identity(
    database_path: Path,
) -> None:
    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO users (
                user_id,
                email,
                display_name,
                created_at
            )
            VALUES (
                'user-1',
                'user@example.com',
                'User',
                '2026-01-01T00:00:00+00:00'
            )
            """
        )

        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                name,
                created_by_user_id,
                created_at
            )
            VALUES (
                'workspace-1',
                'Workspace',
                'user-1',
                '2026-01-01T00:00:00+00:00'
            )
            """
        )


def test_single_result_history_remains_valid_without_candidate_evidence() -> None:
    record = _history_record()

    assert record.candidate_set_id is None
    assert record.candidate_audit_snapshot is None
    assert record.selected_candidate_id is None


def test_candidate_history_requires_snapshot_for_set_linkage() -> None:
    base = _history_record()

    with pytest.raises(
        ValueError,
        match="requires candidate audit snapshot",
    ):
        RewriteHistoryRecord(
            **{
                **base.model_dump(),
                "candidate_set_id": "candidate-set-1",
            }
        )


def test_candidate_history_rejects_set_id_mismatch() -> None:
    audit = _candidate_audit()

    with pytest.raises(
        ValueError,
        match="set ID must match",
    ):
        RewriteHistoryRecord(
            **{
                **_history_record(candidate_audit_snapshot=audit).model_dump(),
                "candidate_set_id": "other-set",
            }
        )


def test_candidate_history_rejects_selected_candidate_mismatch() -> None:
    audit = _candidate_audit()

    with pytest.raises(
        ValueError,
        match="selected candidate linkage",
    ):
        RewriteHistoryRecord(
            **{
                **_history_record(candidate_audit_snapshot=audit).model_dump(),
                "selected_candidate_id": "candidate-2",
            }
        )


def test_candidate_history_survives_sqlite_reopen(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "candidate-history.db"
    _seed_identity(database_path)

    audit = _candidate_audit()
    record = _history_record(
        candidate_audit_snapshot=audit,
    )

    repository = SQLiteRewriteHistoryRepository(database_path)
    repository.create(record)

    reopened = SQLiteRewriteHistoryRepository(database_path)

    assert reopened.get(record.rewrite_id) == record


def test_single_result_history_survives_new_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "single-history.db"
    _seed_identity(database_path)

    record = _history_record()

    repository = SQLiteRewriteHistoryRepository(database_path)
    repository.create(record)

    reopened = SQLiteRewriteHistoryRepository(database_path)
    loaded = reopened.get(record.rewrite_id)

    assert loaded == record
    assert loaded is not None
    assert loaded.candidate_audit_snapshot is None


def test_additive_migration_preserves_legacy_history_row(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy-history.db"

    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_by_user_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE rewrite_history (
                rewrite_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                source_text TEXT NOT NULL,
                rewritten_text TEXT NOT NULL,
                document_type TEXT NOT NULL,
                audience TEXT NOT NULL,
                tone TEXT NOT NULL,
                intensity TEXT NOT NULL,
                provider_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                fallback_used INTEGER NOT NULL,
                verification_decision TEXT NOT NULL,
                editorial_quality_decision TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        connection.execute(
            """
            INSERT INTO rewrite_history (
                rewrite_id,
                workspace_id,
                user_id,
                trace_id,
                source_text,
                rewritten_text,
                document_type,
                audience,
                tone,
                intensity,
                provider_name,
                model_name,
                prompt_version,
                fallback_used,
                verification_decision,
                editorial_quality_decision,
                status,
                created_at
            )
            VALUES (
                'legacy-1',
                'workspace-1',
                'user-1',
                'trace-legacy',
                'Original.',
                'Improved.',
                'general',
                'general audience',
                'natural',
                'natural_rewrite',
                'provider',
                'model',
                'prompt',
                0,
                'pass',
                'pass',
                'completed',
                '2026-01-01T00:00:00+00:00'
            )
            """
        )

    repository = SQLiteRewriteHistoryRepository(database_path)

    loaded = repository.get("legacy-1")

    assert loaded is not None
    assert loaded.candidate_set_id is None
    assert loaded.candidate_audit_snapshot is None
    assert loaded.selected_candidate_id is None
