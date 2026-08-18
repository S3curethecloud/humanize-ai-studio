from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.v2.domain.long_document_audit import (
    LONG_DOCUMENT_AUDIT_VERSION,
    LongDocumentAuditRecord,
)
from app.v2.domain.long_documents import (
    DocumentReconstruction,
    SectionRewriteDisposition,
    SectionRewriteResult,
)
from app.v2.repositories.long_document_audit import (
    InMemoryLongDocumentAuditRepository,
    SQLiteLongDocumentAuditRepository,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
)
from app.v2.services.document_reconstructor import (
    DocumentReconstructor,
)
from app.v2.services.document_structure_detector import (
    DocumentStructureDetector,
)
from app.v2.services.long_document_audit_service import (
    LongDocumentAuditIntegrityError,
    LongDocumentAuditService,
)
from app.v2.services.long_document_control_evaluator import (
    CrossSectionConsistencyResult,
    LongDocumentControlEvaluation,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteExecution,
)
from app.v2.services.section_rewrite_planner import (
    SectionRewritePlanner,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)

SOURCE = "# Overview\r\nAlpha remains unchanged.\r\n\r\n## Summary\r\nBeta remains unchanged.\r\n"


def _workspace_service() -> tuple[
    WorkspaceService,
    str,
    str,
]:
    users = InMemoryUserRepository()
    workspaces = InMemoryWorkspaceRepository()
    memberships = InMemoryMembershipRepository()

    service = WorkspaceService(
        users=users,
        workspaces=workspaces,
        memberships=memberships,
    )

    user = service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = service.create_workspace(
        user_id=user.user_id,
        name="Long Document Workspace",
    )

    return (
        service,
        workspace.workspace_id,
        user.user_id,
    )


def _execution() -> SectionRewriteExecution:
    structure = DocumentStructureDetector().detect(
        source_text=SOURCE,
    )

    generated_plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    preserve_entries = tuple(
        entry.model_copy(
            update={
                "disposition": (SectionRewriteDisposition.PRESERVE),
                "rationale": ("Preserved for audit persistence test."),
            }
        )
        for entry in generated_plan.entries
    )

    plan = generated_plan.model_copy(
        update={
            "entries": preserve_entries,
        }
    )

    results = tuple(
        SectionRewriteResult(
            section_id=section.section_id,
            ordinal=section.ordinal,
            disposition=(SectionRewriteDisposition.PRESERVE),
            source_text=section.source_text,
            rewritten_text=section.source_text,
        )
        for section in structure.sections
    )

    return SectionRewriteExecution(
        structure=structure,
        plan=plan,
        results=results,
        rewrite_responses=(),
    )


def _evaluation(
    *,
    execution: SectionRewriteExecution | None = None,
    v1_failed_section_ids: tuple[
        str,
        ...,
    ] = (),
) -> LongDocumentControlEvaluation:
    resolved = execution or _execution()

    return LongDocumentControlEvaluation(
        execution=resolved,
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        cross_section_consistency=(
            CrossSectionConsistencyResult(
                decision=(ClaimLockValidationDecision.PASS),
                checks=(),
            )
        ),
        v1_failed_section_ids=(v1_failed_section_ids),
    )


def _artifacts() -> tuple[
    LongDocumentControlEvaluation,
    DocumentReconstruction,
]:
    evaluation = _evaluation()

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    return evaluation, reconstruction


def _record(
    *,
    audit_id: str = "audit_test",
    workspace_id: str = "workspace_test",
    user_id: str = "user_test",
) -> LongDocumentAuditRecord:
    evaluation, reconstruction = _artifacts()

    return LongDocumentAuditRecord(
        audit_id=audit_id,
        workspace_id=workspace_id,
        user_id=user_id,
        structure=(evaluation.execution.structure),
        plan=evaluation.execution.plan,
        reconstruction=reconstruction,
        claim_lock_validation=(evaluation.claim_lock_validation),
        cross_section_consistency={
            "decision": "pass",
            "checks": (),
        },
    )


def test_audit_version_is_frozen() -> None:
    assert LONG_DOCUMENT_AUDIT_VERSION == "long-document-audit-v1"


def test_service_persists_exact_a_to_f_artifacts() -> None:
    (
        workspace_service,
        workspace_id,
        user_id,
    ) = _workspace_service()

    repository = InMemoryLongDocumentAuditRepository()

    evaluation, reconstruction = _artifacts()

    record = LongDocumentAuditService(
        workspace_service=workspace_service,
        repository=repository,
    ).record(
        workspace_id=workspace_id,
        user_id=user_id,
        evaluation=evaluation,
        reconstruction=reconstruction,
    )

    assert record.structure == evaluation.execution.structure

    assert record.plan == evaluation.execution.plan

    assert record.reconstruction == reconstruction


def test_service_persists_control_evidence_without_rerun() -> None:
    (
        workspace_service,
        workspace_id,
        user_id,
    ) = _workspace_service()

    evaluation, reconstruction = _artifacts()

    record = LongDocumentAuditService(
        workspace_service=workspace_service,
        repository=(InMemoryLongDocumentAuditRepository()),
    ).record(
        workspace_id=workspace_id,
        user_id=user_id,
        evaluation=evaluation,
        reconstruction=reconstruction,
    )

    assert record.claim_lock_validation == evaluation.claim_lock_validation

    assert record.cross_section_consistency.decision == "pass"


def test_service_requires_workspace_membership() -> None:
    (
        workspace_service,
        workspace_id,
        _,
    ) = _workspace_service()

    evaluation, reconstruction = _artifacts()

    with pytest.raises(
        PermissionError,
        match="not a member",
    ):
        LongDocumentAuditService(
            workspace_service=workspace_service,
            repository=(InMemoryLongDocumentAuditRepository()),
        ).record(
            workspace_id=workspace_id,
            user_id="user_intruder",
            evaluation=evaluation,
            reconstruction=reconstruction,
        )


def test_v1_failure_evidence_blocks_persistence() -> None:
    (
        workspace_service,
        workspace_id,
        user_id,
    ) = _workspace_service()

    execution = _execution()

    evaluation = _evaluation(
        execution=execution,
        v1_failed_section_ids=(execution.results[0].section_id,),
    )

    reconstruction = execution.structure.model_copy()

    with pytest.raises(
        LongDocumentAuditIntegrityError,
        match="authoritative V1 failures",
    ):
        LongDocumentAuditService(
            workspace_service=workspace_service,
            repository=(InMemoryLongDocumentAuditRepository()),
        ).record(
            workspace_id=workspace_id,
            user_id=user_id,
            evaluation=evaluation,
            reconstruction=reconstruction,  # type: ignore[arg-type]
        )


def test_mismatched_reconstruction_structure_fails() -> None:
    (
        workspace_service,
        workspace_id,
        user_id,
    ) = _workspace_service()

    evaluation, reconstruction = _artifacts()

    other_structure = DocumentStructureDetector().detect(
        source_text="# Other\nDifferent.\n",
    )

    tampered = reconstruction.model_copy(
        update={
            "structure": other_structure,
        }
    )

    with pytest.raises(
        LongDocumentAuditIntegrityError,
        match="structure must match",
    ):
        LongDocumentAuditService(
            workspace_service=workspace_service,
            repository=(InMemoryLongDocumentAuditRepository()),
        ).record(
            workspace_id=workspace_id,
            user_id=user_id,
            evaluation=evaluation,
            reconstruction=tampered,
        )


def test_mismatched_reconstruction_results_fail() -> None:
    (
        workspace_service,
        workspace_id,
        user_id,
    ) = _workspace_service()

    evaluation, reconstruction = _artifacts()

    bad_result = reconstruction.section_results[0].model_copy(
        update={
            "section_id": "wrong-section",
        }
    )

    tampered = reconstruction.model_copy(
        update={
            "section_results": (
                bad_result,
                reconstruction.section_results[1],
            ),
        }
    )

    with pytest.raises(
        LongDocumentAuditIntegrityError,
        match="results must match",
    ):
        LongDocumentAuditService(
            workspace_service=workspace_service,
            repository=(InMemoryLongDocumentAuditRepository()),
        ).record(
            workspace_id=workspace_id,
            user_id=user_id,
            evaluation=evaluation,
            reconstruction=tampered,
        )


def test_in_memory_repository_round_trip() -> None:
    repository = InMemoryLongDocumentAuditRepository()

    record = _record()

    repository.create(record)

    assert repository.get(record.audit_id) == record


def test_in_memory_repository_rejects_duplicate_id() -> None:
    repository = InMemoryLongDocumentAuditRepository()

    record = _record()

    repository.create(record)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        repository.create(record)


def test_sqlite_repository_round_trip(
    tmp_path: Path,
) -> None:
    repository = SQLiteLongDocumentAuditRepository(
        database_path=(tmp_path / "audit.sqlite3"),
    )

    record = _record()

    repository.create(record)

    loaded = repository.get(record.audit_id)

    assert loaded == record


def test_sqlite_round_trip_preserves_crlf_bytes(
    tmp_path: Path,
) -> None:
    repository = SQLiteLongDocumentAuditRepository(
        database_path=(tmp_path / "audit.sqlite3"),
    )

    record = _record()

    repository.create(record)

    loaded = repository.get(record.audit_id)

    assert loaded is not None

    assert loaded.structure.source_text == SOURCE

    assert "\r\n" in (loaded.reconstruction.reconstructed_text)


def test_sqlite_repository_workspace_isolation(
    tmp_path: Path,
) -> None:
    repository = SQLiteLongDocumentAuditRepository(
        database_path=(tmp_path / "audit.sqlite3"),
    )

    first = _record(
        audit_id="audit_one",
        workspace_id="workspace_one",
    )

    second = _record(
        audit_id="audit_two",
        workspace_id="workspace_two",
    )

    repository.create(first)
    repository.create(second)

    assert repository.list_for_workspace(workspace_id="workspace_one") == (first,)


def test_sqlite_repository_orders_newest_first(
    tmp_path: Path,
) -> None:
    repository = SQLiteLongDocumentAuditRepository(
        database_path=(tmp_path / "audit.sqlite3"),
    )

    older = _record(
        audit_id="audit_older",
    ).model_copy(
        update={
            "created_at": datetime(
                2026,
                1,
                1,
                tzinfo=UTC,
            )
        }
    )

    newer = _record(
        audit_id="audit_newer",
    ).model_copy(
        update={
            "created_at": datetime(
                2026,
                1,
                2,
                tzinfo=UTC,
            )
        }
    )

    repository.create(older)
    repository.create(newer)

    assert repository.list_for_workspace(workspace_id="workspace_test") == (
        newer,
        older,
    )


def test_sqlite_repository_rejects_duplicate_id(
    tmp_path: Path,
) -> None:
    repository = SQLiteLongDocumentAuditRepository(
        database_path=(tmp_path / "audit.sqlite3"),
    )

    record = _record()

    repository.create(record)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        repository.create(record)


def test_service_get_is_workspace_scoped() -> None:
    (
        workspace_service,
        workspace_id,
        user_id,
    ) = _workspace_service()

    repository = InMemoryLongDocumentAuditRepository()

    evaluation, reconstruction = _artifacts()

    service = LongDocumentAuditService(
        workspace_service=workspace_service,
        repository=repository,
    )

    record = service.record(
        workspace_id=workspace_id,
        user_id=user_id,
        evaluation=evaluation,
        reconstruction=reconstruction,
    )

    assert (
        service.get(
            workspace_id=workspace_id,
            user_id=user_id,
            audit_id=record.audit_id,
        )
        == record
    )


def test_service_does_not_mutate_validated_artifacts() -> None:
    (
        workspace_service,
        workspace_id,
        user_id,
    ) = _workspace_service()

    evaluation, reconstruction = _artifacts()

    structure_before = evaluation.execution.structure.model_dump(mode="json")

    plan_before = evaluation.execution.plan.model_dump(mode="json")

    reconstruction_before = reconstruction.model_dump(mode="json")

    LongDocumentAuditService(
        workspace_service=workspace_service,
        repository=(InMemoryLongDocumentAuditRepository()),
    ).record(
        workspace_id=workspace_id,
        user_id=user_id,
        evaluation=evaluation,
        reconstruction=reconstruction,
    )

    assert evaluation.execution.structure.model_dump(mode="json") == structure_before

    assert evaluation.execution.plan.model_dump(mode="json") == plan_before

    assert reconstruction.model_dump(mode="json") == reconstruction_before
