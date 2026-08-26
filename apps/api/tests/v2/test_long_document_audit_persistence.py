from __future__ import annotations

from tests.v2.test_support_authorization_gate import (
    allow_all_workspace_authorization_gate,
    deny_all_workspace_authorization_gate,
)
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
)
from app.v2.domain.enterprise_claim_lock_runtime import (
    EnterpriseClaimLockWorkspacePolicyExecutionEvidence,
)
from app.v2.domain.long_document_audit import (
    LONG_DOCUMENT_AUDIT_V2_VERSION,
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
    ClaimLockValidator,
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
        repository=repository,
        authorization_gate=allow_all_workspace_authorization_gate(),
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
        repository=(InMemoryLongDocumentAuditRepository()),
        authorization_gate=allow_all_workspace_authorization_gate(),
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
        match="permission_not_granted",
    ):
        LongDocumentAuditService(
            repository=(InMemoryLongDocumentAuditRepository()),
            authorization_gate=deny_all_workspace_authorization_gate(),
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
            repository=(InMemoryLongDocumentAuditRepository()),
            authorization_gate=allow_all_workspace_authorization_gate(),
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
            repository=(InMemoryLongDocumentAuditRepository()),
            authorization_gate=allow_all_workspace_authorization_gate(),
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
            repository=(InMemoryLongDocumentAuditRepository()),
            authorization_gate=allow_all_workspace_authorization_gate(),
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
        repository=repository,
        authorization_gate=allow_all_workspace_authorization_gate(),
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
        repository=(InMemoryLongDocumentAuditRepository()),
        authorization_gate=allow_all_workspace_authorization_gate(),
    ).record(
        workspace_id=workspace_id,
        user_id=user_id,
        evaluation=evaluation,
        reconstruction=reconstruction,
    )

    assert evaluation.execution.structure.model_dump(mode="json") == structure_before

    assert evaluation.execution.plan.model_dump(mode="json") == plan_before

    assert reconstruction.model_dump(mode="json") == reconstruction_before


def _workspace_effective_lock(
    *,
    enforcement_mode: ClaimLockEnforcementMode = (
        ClaimLockEnforcementMode.STRICT
    ),
    source_reference: str = (
        "workspace-claim-lock-policy:"
        "policy_audit_test:revision:7"
    ),
) -> ClaimLock:
    return ClaimLock(
        lock_id="lock_audit_v2_test",
        enforcement_mode=enforcement_mode,
        terms=(
            ProtectedTerm(
                term_id="workspace_term_alpha",
                text="Alpha",
                case_sensitive=True,
                provenance=ClaimLockProvenance(
                    origin=ClaimLockOrigin.WORKSPACE,
                    source_reference=source_reference,
                ),
            ),
        ),
    )


def _workspace_policy_evidence(
    *,
    enforcement_mode: ClaimLockEnforcementMode = (
        ClaimLockEnforcementMode.STRICT
    ),
    applicable_term_ids: tuple[str, ...] = (
        "workspace_term_alpha",
    ),
) -> EnterpriseClaimLockWorkspacePolicyExecutionEvidence:
    return (
        EnterpriseClaimLockWorkspacePolicyExecutionEvidence(
            policy_id="policy_audit_test",
            policy_revision=7,
            enforcement_mode=enforcement_mode,
            applicable_term_ids=applicable_term_ids,
        )
    )


def _evaluation_for_effective_lock(
    claim_lock: ClaimLock,
) -> LongDocumentControlEvaluation:
    base = _evaluation()

    validation = ClaimLockValidator().validate(
        claim_lock=claim_lock,
        rewritten_text=SOURCE,
    )

    return LongDocumentControlEvaluation(
        execution=base.execution,
        claim_lock_validation=validation,
        cross_section_consistency=(
            base.cross_section_consistency
        ),
        v1_failed_section_ids=(),
    )


def _v2_record(
    *,
    effective_claim_lock: ClaimLock,
    workspace_policy: (
        EnterpriseClaimLockWorkspacePolicyExecutionEvidence
        | None
    ),
    audit_id: str = "audit_v2_test",
) -> LongDocumentAuditRecord:
    evaluation = _evaluation_for_effective_lock(
        effective_claim_lock
    )

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    return LongDocumentAuditRecord(
        audit_version=LONG_DOCUMENT_AUDIT_V2_VERSION,
        audit_id=audit_id,
        workspace_id="workspace_test",
        user_id="user_test",
        structure=evaluation.execution.structure,
        plan=evaluation.execution.plan,
        reconstruction=reconstruction,
        claim_lock_validation=(
            evaluation.claim_lock_validation
        ),
        effective_claim_lock=effective_claim_lock,
        claim_lock_workspace_policy=workspace_policy,
        cross_section_consistency={
            "decision": "pass",
            "checks": (),
        },
    )


def test_service_writes_v2_exact_runtime_evidence() -> None:
    effective_claim_lock = _workspace_effective_lock()
    workspace_policy = _workspace_policy_evidence()

    evaluation = _evaluation_for_effective_lock(
        effective_claim_lock
    )

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    runtime_context = SimpleNamespace(
        effective_claim_lock=effective_claim_lock,
        workspace_policy_evidence=workspace_policy,
    )

    record = LongDocumentAuditService(
        repository=(
            InMemoryLongDocumentAuditRepository()
        ),
        authorization_gate=(
            allow_all_workspace_authorization_gate()
        ),
    ).record(
        workspace_id="workspace_test",
        user_id="user_test",
        evaluation=evaluation,
        reconstruction=reconstruction,
        claim_lock_runtime_context=runtime_context,
    )

    assert (
        record.audit_version
        == LONG_DOCUMENT_AUDIT_V2_VERSION
    )

    assert (
        record.effective_claim_lock
        == effective_claim_lock
    )

    assert (
        record.claim_lock_workspace_policy
        == workspace_policy
    )

    assert (
        record.claim_lock_validation.lock_id
        == effective_claim_lock.lock_id
    )

    assert (
        record.claim_lock_validation.enforcement_mode
        is effective_claim_lock.enforcement_mode
    )


def test_v2_policy_evidence_can_exist_without_effective_lock() -> None:
    evaluation, reconstruction = _artifacts()

    workspace_policy = _workspace_policy_evidence(
        enforcement_mode=(
            ClaimLockEnforcementMode.AUDIT_ONLY
        ),
        applicable_term_ids=(),
    )

    runtime_context = SimpleNamespace(
        effective_claim_lock=None,
        workspace_policy_evidence=workspace_policy,
    )

    record = LongDocumentAuditService(
        repository=(
            InMemoryLongDocumentAuditRepository()
        ),
        authorization_gate=(
            allow_all_workspace_authorization_gate()
        ),
    ).record(
        workspace_id="workspace_test",
        user_id="user_test",
        evaluation=evaluation,
        reconstruction=reconstruction,
        claim_lock_runtime_context=runtime_context,
    )

    assert (
        record.audit_version
        == LONG_DOCUMENT_AUDIT_V2_VERSION
    )

    assert record.effective_claim_lock is None

    assert (
        record.claim_lock_workspace_policy
        == workspace_policy
    )

    assert (
        record.claim_lock_workspace_policy
        .applicable_term_ids
        == ()
    )


def test_historical_v1_json_remains_readable() -> None:
    historical = _record(
        audit_id="audit_historical_v1",
    )

    payload = historical.model_dump_json()

    loaded = LongDocumentAuditRecord.model_validate_json(
        payload
    )

    assert loaded == historical

    assert (
        loaded.audit_version
        == LONG_DOCUMENT_AUDIT_VERSION
    )

    assert loaded.effective_claim_lock is None
    assert loaded.claim_lock_workspace_policy is None


def test_sqlite_restart_round_trip_preserves_v2_evidence(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "audit-v2.sqlite3"

    effective_claim_lock = _workspace_effective_lock()
    workspace_policy = _workspace_policy_evidence()

    record = _v2_record(
        effective_claim_lock=effective_claim_lock,
        workspace_policy=workspace_policy,
        audit_id="audit_v2_restart",
    )

    first = SQLiteLongDocumentAuditRepository(
        database_path=database_path,
    )

    first.create(record)

    recreated = SQLiteLongDocumentAuditRepository(
        database_path=database_path,
    )

    loaded = recreated.get(record.audit_id)

    assert loaded == record
    assert loaded is not None

    assert (
        loaded.effective_claim_lock
        == effective_claim_lock
    )

    assert (
        loaded.claim_lock_workspace_policy
        == workspace_policy
    )

    with sqlite3.connect(str(database_path)) as connection:
        columns = tuple(
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(long_document_audit)"
            ).fetchall()
        )

    assert columns == (
        "audit_id",
        "workspace_id",
        "user_id",
        "payload",
        "created_at",
    )


def test_v2_rejects_effective_lock_id_mismatch() -> None:
    effective_claim_lock = _workspace_effective_lock()
    workspace_policy = _workspace_policy_evidence()

    valid = _v2_record(
        effective_claim_lock=effective_claim_lock,
        workspace_policy=workspace_policy,
    )

    payload = valid.model_dump(mode="python")

    payload["claim_lock_validation"] = (
        valid.claim_lock_validation.model_copy(
            update={
                "lock_id": "different_lock_id",
            }
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "effective Claim Lock ID must match validation"
        ),
    ):
        LongDocumentAuditRecord.model_validate(payload)


def test_v2_rejects_effective_lock_mode_mismatch() -> None:
    effective_claim_lock = _workspace_effective_lock()
    workspace_policy = _workspace_policy_evidence()

    valid = _v2_record(
        effective_claim_lock=effective_claim_lock,
        workspace_policy=workspace_policy,
    )

    payload = valid.model_dump(mode="python")

    payload["claim_lock_validation"] = (
        valid.claim_lock_validation.model_copy(
            update={
                "enforcement_mode": (
                    ClaimLockEnforcementMode.AUDIT_ONLY
                ),
            }
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "effective Claim Lock mode must match validation"
        ),
    ):
        LongDocumentAuditRecord.model_validate(payload)


def test_v2_rejects_workspace_term_wrong_policy_revision() -> None:
    effective_claim_lock = _workspace_effective_lock(
        source_reference=(
            "workspace-claim-lock-policy:"
            "policy_audit_test:revision:8"
        ),
    )

    workspace_policy = _workspace_policy_evidence()

    with pytest.raises(
        ValueError,
        match=(
            "workspace term provenance must match "
            "policy revision"
        ),
    ):
        _v2_record(
            effective_claim_lock=effective_claim_lock,
            workspace_policy=workspace_policy,
        )


def test_v2_rejects_applicable_term_id_mismatch() -> None:
    effective_claim_lock = _workspace_effective_lock()

    workspace_policy = _workspace_policy_evidence(
        applicable_term_ids=(
            "different_workspace_term",
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "applicable term IDs must match effective "
            "workspace contribution"
        ),
    ):
        _v2_record(
            effective_claim_lock=effective_claim_lock,
            workspace_policy=workspace_policy,
        )


def test_v2_rejects_workspace_strict_downgrade() -> None:
    effective_claim_lock = _workspace_effective_lock(
        enforcement_mode=(
            ClaimLockEnforcementMode.AUDIT_ONLY
        ),
    )

    workspace_policy = _workspace_policy_evidence(
        enforcement_mode=(
            ClaimLockEnforcementMode.STRICT
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "effective enforcement cannot weaken "
            "workspace policy"
        ),
    ):
        _v2_record(
            effective_claim_lock=effective_claim_lock,
            workspace_policy=workspace_policy,
        )


def test_v1_rejects_runtime_governance_evidence() -> None:
    effective_claim_lock = _workspace_effective_lock()

    evaluation = _evaluation_for_effective_lock(
        effective_claim_lock
    )

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    with pytest.raises(
        ValueError,
        match=(
            "long-document audit v1 cannot contain "
            "C6 Claim Lock runtime evidence"
        ),
    ):
        LongDocumentAuditRecord(
            audit_version=LONG_DOCUMENT_AUDIT_VERSION,
            audit_id="audit_invalid_v1_runtime",
            workspace_id="workspace_test",
            user_id="user_test",
            structure=evaluation.execution.structure,
            plan=evaluation.execution.plan,
            reconstruction=reconstruction,
            claim_lock_validation=(
                evaluation.claim_lock_validation
            ),
            effective_claim_lock=effective_claim_lock,
            cross_section_consistency={
                "decision": "pass",
                "checks": (),
            },
        )
