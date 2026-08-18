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
        workspace_service=workspace_service,
        history=history,
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
