from tests.v2.test_support_authorization_gate import allow_all_workspace_authorization_gate
from pathlib import Path

from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.repositories.sqlite import (
    SQLiteMembershipRepository,
    SQLiteRewriteHistoryRepository,
    SQLiteUserRepository,
    SQLiteWorkspaceRepository,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)


def _build_services(
    database_path: Path,
) -> tuple[
    WorkspaceService,
    RewriteHistoryService,
]:
    users = SQLiteUserRepository(database_path)
    workspaces = SQLiteWorkspaceRepository(database_path)
    memberships = SQLiteMembershipRepository(database_path)
    history = SQLiteRewriteHistoryRepository(database_path)

    workspace_service = WorkspaceService(
        users=users,
        workspaces=workspaces,
        memberships=memberships,
    )

    history_service = RewriteHistoryService(
        history=history,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    return (
        workspace_service,
        history_service,
    )


def _history_record(
    *,
    rewrite_id: str,
    workspace_id: str,
    user_id: str,
    trace_id: str,
) -> RewriteHistoryRecord:
    return RewriteHistoryRecord(
        rewrite_id=rewrite_id,
        workspace_id=workspace_id,
        user_id=user_id,
        trace_id=trace_id,
        source_text="Original text.",
        rewritten_text="Improved text.",
        document_type="general",
        audience="general audience",
        tone="natural",
        intensity="natural_rewrite",
        provider_name="cloudflare-workers-ai",
        model_name="test-model",
        prompt_version="test-v1",
        fallback_used=False,
        verification_decision="pass",
        editorial_quality_decision="pass",
    )


def test_user_survives_repository_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    first = SQLiteUserRepository(database_path)

    from app.v2.domain.models import UserRecord

    user = UserRecord(
        user_id="user-1",
        email="user@example.com",
        display_name="Example User",
    )

    first.create(user)

    second = SQLiteUserRepository(database_path)

    assert second.get("user-1") == user


def test_workspace_and_membership_are_persistent(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    workspace_service, _ = _build_services(database_path)

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Persistent Workspace",
    )

    reloaded_service, _ = _build_services(database_path)

    membership = reloaded_service.require_membership(
        workspace_id=(workspace.workspace_id),
        user_id=user.user_id,
    )

    assert membership.role.value == "owner"


def test_rewrite_history_survives_reopen(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    workspace_service, _ = _build_services(database_path)

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Persistent Workspace",
    )

    repository = SQLiteRewriteHistoryRepository(database_path)

    record = _history_record(
        rewrite_id="history-1",
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        trace_id="trace-1",
    )

    repository.create(record)

    reopened = SQLiteRewriteHistoryRepository(database_path)

    assert reopened.get("history-1") == record


def test_rewrite_history_remains_workspace_scoped(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    workspace_service, _ = _build_services(database_path)

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    first_workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="First Workspace",
    )

    second_workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Second Workspace",
    )

    repository = SQLiteRewriteHistoryRepository(database_path)

    first_record = _history_record(
        rewrite_id="history-1",
        workspace_id=(first_workspace.workspace_id),
        user_id=user.user_id,
        trace_id="trace-1",
    )

    second_record = _history_record(
        rewrite_id="history-2",
        workspace_id=(second_workspace.workspace_id),
        user_id=user.user_id,
        trace_id="trace-2",
    )

    repository.create(first_record)
    repository.create(second_record)

    assert repository.list_for_workspace(workspace_id=(first_workspace.workspace_id)) == (
        first_record,
    )

    assert repository.list_for_workspace(workspace_id=(second_workspace.workspace_id)) == (
        second_record,
    )


def test_history_limit_is_enforced(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    workspace_service, _ = _build_services(database_path)

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Persistent Workspace",
    )

    repository = SQLiteRewriteHistoryRepository(database_path)

    first = _history_record(
        rewrite_id="history-1",
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        trace_id="trace-1",
    )

    second = _history_record(
        rewrite_id="history-2",
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        trace_id="trace-2",
    )

    repository.create(first)
    repository.create(second)

    records = repository.list_for_workspace(
        workspace_id=workspace.workspace_id,
        limit=1,
    )

    assert len(records) == 1


def test_claim_lock_history_evidence_survives_reopen(
    tmp_path: Path,
) -> None:
    from app.v2.domain.claim_lock import (
        ClaimLock,
        ClaimLockEnforcementMode,
        ClaimLockOrigin,
        ClaimLockProvenance,
        ProtectedClaim,
    )
    from app.v2.domain.claim_lock_audit import (
        ClaimLockValidationAuditCheck,
        ClaimLockValidationAuditSnapshot,
    )

    database_path = tmp_path / "claim-lock-history.db"

    workspace_service, _ = _build_services(database_path)

    user = workspace_service.create_user(
        email="claim-lock@example.com",
        display_name="Claim Lock Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Claim Lock Persistence",
    )

    claim_lock = ClaimLock(
        lock_id="lock-sqlite-1",
        enforcement_mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
        claims=(
            ProtectedClaim(
                claim_id="claim-sqlite-1",
                text=("Deployment completed successfully."),
                provenance=ClaimLockProvenance(
                    origin=(ClaimLockOrigin.REQUEST),
                    source_reference=("rewrite-request"),
                ),
            ),
        ),
    )

    validation = ClaimLockValidationAuditSnapshot(
        validator_version=("claim-lock-validator-v1"),
        lock_id=claim_lock.lock_id,
        enforcement_mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
        decision="pass",
        checks=(
            ClaimLockValidationAuditCheck(
                item_id="claim-sqlite-1",
                item_type="claim",
                expected_text=("Deployment completed successfully."),
                status="not_evaluated",
                reason=("semantic claim preservation is not deterministically evaluated"),
            ),
        ),
    )

    record = RewriteHistoryRecord(
        rewrite_id="history-claim-lock-sqlite",
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        trace_id="trace-claim-lock-sqlite",
        source_text=("Deployment completed successfully."),
        rewritten_text=("The deployment completed successfully."),
        document_type="general",
        audience="general audience",
        tone="natural",
        intensity="natural_rewrite",
        provider_name="cloudflare-workers-ai",
        model_name="test-model",
        prompt_version="test-v1",
        claim_lock_snapshot=claim_lock,
        claim_lock_validation=validation,
        claim_lock_enforcement_mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
        fallback_used=False,
        verification_decision="pass",
        editorial_quality_decision="pass",
    )

    first = SQLiteRewriteHistoryRepository(database_path)

    first.create(record)

    reopened = SQLiteRewriteHistoryRepository(database_path)

    loaded = reopened.get("history-claim-lock-sqlite")

    assert loaded == record
    assert loaded is not None
    assert loaded.claim_lock_snapshot == claim_lock
    assert loaded.claim_lock_validation == validation
    assert loaded.claim_lock_enforcement_mode is ClaimLockEnforcementMode.AUDIT_ONLY


def test_initialize_database_migrates_legacy_history_for_claim_lock(
    tmp_path: Path,
) -> None:
    import sqlite3

    from app.v2.repositories.sqlite import (
        initialize_database,
    )

    database_path = tmp_path / "legacy-claim-lock-history.db"

    connection = sqlite3.connect(database_path)

    connection.execute(
        """
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
            voice_profile_id TEXT,
            voice_guidance_version TEXT,
            voice_analysis_snapshot TEXT,
            voice_analysis_binding TEXT,
            voice_analysis_authenticity TEXT,
            fallback_used INTEGER NOT NULL,
            verification_decision TEXT NOT NULL,
            editorial_quality_decision TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()

    initialize_database(database_path)

    connection = sqlite3.connect(database_path)

    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(rewrite_history)").fetchall()
    }

    connection.close()

    assert "claim_lock_snapshot" in columns
    assert "claim_lock_validation" in columns
    assert "claim_lock_enforcement_mode" in columns


def test_historical_sqlite_history_without_claim_lock_remains_readable(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "historical-no-claim-lock.db"

    workspace_service, _ = _build_services(database_path)

    user = workspace_service.create_user(
        email="historical@example.com",
        display_name="Historical User",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Historical Workspace",
    )

    record = _history_record(
        rewrite_id="history-no-claim-lock",
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        trace_id="trace-no-claim-lock",
    )

    repository = SQLiteRewriteHistoryRepository(database_path)

    repository.create(record)

    loaded = repository.get("history-no-claim-lock")

    assert loaded == record
    assert loaded is not None
    assert loaded.claim_lock_snapshot is None
    assert loaded.claim_lock_validation is None
    assert loaded.claim_lock_enforcement_mode is None
    assert loaded.claim_lock_workspace_policy is None


def test_workspace_policy_history_evidence_survives_reopen_without_v23_tuple(
    tmp_path: Path,
) -> None:
    import json
    import sqlite3

    from app.v2.domain.claim_lock import (
        ClaimLockEnforcementMode,
    )
    from app.v2.domain.enterprise_claim_lock_runtime import (
        EnterpriseClaimLockWorkspacePolicyExecutionEvidence,
    )

    database_path = (
        tmp_path / "workspace-policy-history.db"
    )

    workspace_service, _ = _build_services(
        database_path
    )

    user = workspace_service.create_user(
        email="workspace-policy@example.com",
        display_name="Workspace Policy Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Workspace Policy Persistence",
    )

    evidence = (
        EnterpriseClaimLockWorkspacePolicyExecutionEvidence(
            policy_id="policy-sqlite-i8",
            policy_revision=3,
            enforcement_mode=(
                ClaimLockEnforcementMode.STRICT
            ),
            applicable_term_ids=(),
        )
    )

    base_record = _history_record(
        rewrite_id="history-workspace-policy-i8",
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        trace_id="trace-workspace-policy-i8",
    )

    record = base_record.model_copy(
        update={
            "claim_lock_workspace_policy": evidence,
        }
    )

    first = SQLiteRewriteHistoryRepository(
        database_path
    )

    first.create(record)

    connection = sqlite3.connect(database_path)

    stored = connection.execute(
        """
        SELECT claim_lock_workspace_policy
        FROM rewrite_history
        WHERE rewrite_id = ?
        """,
        (record.rewrite_id,),
    ).fetchone()

    connection.close()

    assert stored is not None
    assert stored[0] is not None
    assert json.loads(stored[0]) == evidence.model_dump(
        mode="json"
    )

    reopened = SQLiteRewriteHistoryRepository(
        database_path
    )

    loaded = reopened.get(record.rewrite_id)

    assert loaded == record
    assert loaded is not None

    assert (
        loaded.claim_lock_workspace_policy
        == evidence
    )

    assert loaded.claim_lock_snapshot is None
    assert loaded.claim_lock_validation is None
    assert loaded.claim_lock_enforcement_mode is None


def test_initialize_database_migrates_pre_i8_history_and_preserves_null_policy_evidence(
    tmp_path: Path,
) -> None:
    import sqlite3

    from app.v2.repositories.sqlite import (
        SQLiteRewriteHistoryRepository,
        initialize_database,
    )

    database_path = (
        tmp_path / "pre-i8-history.db"
    )

    record = _history_record(
        rewrite_id="history-pre-i8",
        workspace_id="workspace-pre-i8",
        user_id="user-pre-i8",
        trace_id="trace-pre-i8",
    )

    connection = sqlite3.connect(database_path)

    connection.execute(
        """
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
            voice_profile_id TEXT,
            voice_guidance_version TEXT,
            voice_analysis_snapshot TEXT,
            voice_analysis_binding TEXT,
            voice_analysis_authenticity TEXT,
            claim_lock_snapshot TEXT,
            claim_lock_validation TEXT,
            claim_lock_enforcement_mode TEXT,
            candidate_set_id TEXT,
            candidate_audit_snapshot TEXT,
            selected_candidate_id TEXT,
            fallback_used INTEGER NOT NULL,
            verification_decision TEXT NOT NULL,
            editorial_quality_decision TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
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
            voice_profile_id,
            voice_guidance_version,
            voice_analysis_snapshot,
            voice_analysis_binding,
            voice_analysis_authenticity,
            claim_lock_snapshot,
            claim_lock_validation,
            claim_lock_enforcement_mode,
            candidate_set_id,
            candidate_audit_snapshot,
            selected_candidate_id,
            fallback_used,
            verification_decision,
            editorial_quality_decision,
            status,
            created_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            record.rewrite_id,
            record.workspace_id,
            record.user_id,
            record.trace_id,
            record.source_text,
            record.rewritten_text,
            record.document_type,
            record.audience,
            record.tone,
            record.intensity,
            record.provider_name,
            record.model_name,
            record.prompt_version,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            int(record.fallback_used),
            record.verification_decision,
            record.editorial_quality_decision,
            record.status.value,
            record.created_at.isoformat(),
        ),
    )

    connection.commit()
    connection.close()

    initialize_database(database_path)

    connection = sqlite3.connect(database_path)

    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(rewrite_history)"
        ).fetchall()
    }

    stored_policy = connection.execute(
        """
        SELECT claim_lock_workspace_policy
        FROM rewrite_history
        WHERE rewrite_id = ?
        """,
        (record.rewrite_id,),
    ).fetchone()

    connection.close()

    assert "claim_lock_workspace_policy" in columns

    assert stored_policy is not None
    assert stored_policy[0] is None

    reopened = SQLiteRewriteHistoryRepository(
        database_path
    )

    loaded = reopened.get(record.rewrite_id)

    assert loaded == record
    assert loaded is not None
    assert loaded.claim_lock_workspace_policy is None
