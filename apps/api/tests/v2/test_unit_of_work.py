import sqlite3
from pathlib import Path

import pytest

from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    WorkspaceMembership,
    WorkspaceRecord,
    WorkspaceRole,
)
from app.v2.repositories.sqlite import (
    SQLiteMembershipRepository,
    SQLiteRewriteHistoryRepository,
    SQLiteUserRepository,
    SQLiteWorkspaceRepository,
)
from app.v2.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)
from app.v2.services.transaction_service import (
    TransactionService,
)


def test_unit_of_work_commits_all_records(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    service = TransactionService(SQLiteUnitOfWork(database_path))

    user, workspace, membership = service.create_user_and_workspace(
        email="owner@example.com",
        display_name="Owner",
        workspace_name="Enterprise Workspace",
    )

    users = SQLiteUserRepository(database_path)
    workspaces = SQLiteWorkspaceRepository(database_path)
    memberships = SQLiteMembershipRepository(database_path)

    assert users.get(user.user_id) == user

    assert workspaces.get(workspace.workspace_id) == workspace

    assert (
        memberships.get(
            workspace_id=workspace.workspace_id,
            user_id=user.user_id,
        )
        == membership
    )


def test_unit_of_work_rolls_back_on_failure(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    user = UserRecord(
        user_id="user-rollback",
        email="rollback@example.com",
        display_name="Rollback User",
    )

    workspace = WorkspaceRecord(
        workspace_id="workspace-rollback",
        name="Rollback Workspace",
        created_by_user_id=user.user_id,
    )

    invalid_membership = WorkspaceMembership(
        workspace_id="missing-workspace",
        user_id=user.user_id,
        role=WorkspaceRole.OWNER,
    )

    with pytest.raises(sqlite3.IntegrityError), SQLiteUnitOfWork(database_path) as uow:
        uow.users.create(user)
        uow.workspaces.create(workspace)
        uow.memberships.create(invalid_membership)

    users = SQLiteUserRepository(database_path)
    workspaces = SQLiteWorkspaceRepository(database_path)

    assert users.get(user.user_id) is None

    assert workspaces.get(workspace.workspace_id) is None


def test_explicit_rollback_discards_changes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    user = UserRecord(
        user_id="user-explicit-rollback",
        email="rollback@example.com",
        display_name="Rollback User",
    )

    with SQLiteUnitOfWork(database_path) as uow:
        uow.users.create(user)
        uow.rollback()

    repository = SQLiteUserRepository(database_path)

    assert repository.get(user.user_id) is None


def test_history_can_commit_transactionally(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    service = TransactionService(SQLiteUnitOfWork(database_path))

    user, workspace, _ = service.create_user_and_workspace(
        email="owner@example.com",
        display_name="Owner",
        workspace_name="History Workspace",
    )

    record = RewriteHistoryRecord(
        rewrite_id="history-transaction",
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        trace_id="trace-transaction",
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

    service.record_history(record=record)

    repository = SQLiteRewriteHistoryRepository(database_path)

    assert repository.get(record.rewrite_id) == record


def test_history_foreign_key_failure_rolls_back(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    record = RewriteHistoryRecord(
        rewrite_id="history-invalid",
        workspace_id="missing-workspace",
        user_id="missing-user",
        trace_id="trace-invalid",
        source_text="Original.",
        rewritten_text="Improved.",
        document_type="general",
        audience="general audience",
        tone="natural",
        intensity="natural_rewrite",
        provider_name="test",
        model_name="test",
        prompt_version="test",
        fallback_used=False,
        verification_decision="pass",
        editorial_quality_decision="pass",
    )

    repository = SQLiteRewriteHistoryRepository(database_path)

    with pytest.raises(sqlite3.IntegrityError), SQLiteUnitOfWork(database_path) as uow:
        uow.history.create(record)

    assert repository.get(record.rewrite_id) is None
