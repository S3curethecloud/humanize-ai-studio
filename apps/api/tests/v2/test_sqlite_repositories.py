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
