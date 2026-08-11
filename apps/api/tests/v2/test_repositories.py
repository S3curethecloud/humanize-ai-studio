from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    WorkspaceMembership,
    WorkspaceRecord,
    WorkspaceRole,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)


def test_user_repository_round_trip() -> None:
    repository = InMemoryUserRepository()

    user = UserRecord(
        user_id="user-1",
        email="user@example.com",
        display_name="Example User",
    )

    repository.create(user)

    assert repository.get("user-1") == user


def test_workspace_repository_round_trip() -> None:
    repository = InMemoryWorkspaceRepository()

    workspace = WorkspaceRecord(
        workspace_id="workspace-1",
        name="Example Workspace",
        created_by_user_id="user-1",
    )

    repository.create(workspace)

    assert repository.get("workspace-1") == workspace


def test_membership_repository_round_trip() -> None:
    repository = InMemoryMembershipRepository()

    membership = WorkspaceMembership(
        workspace_id="workspace-1",
        user_id="user-1",
        role=WorkspaceRole.OWNER,
    )

    repository.create(membership)

    assert (
        repository.get(
            workspace_id="workspace-1",
            user_id="user-1",
        )
        == membership
    )


def test_rewrite_history_is_workspace_scoped() -> None:
    repository = InMemoryRewriteHistoryRepository()

    record = RewriteHistoryRecord(
        rewrite_id="rewrite-1",
        workspace_id="workspace-1",
        user_id="user-1",
        trace_id="trace-1",
        source_text="Original",
        rewritten_text="Rewritten",
        document_type="general",
        audience="general",
        tone="natural",
        intensity="natural_rewrite",
        provider_name="cloudflare-workers-ai",
        model_name="example-model",
        prompt_version="example-v1",
        fallback_used=False,
        verification_decision="pass",
        editorial_quality_decision="pass",
    )

    repository.create(record)

    assert repository.get("rewrite-1") == record

    assert repository.list_for_workspace(workspace_id="workspace-1") == (record,)

    assert repository.list_for_workspace(workspace_id="workspace-2") == ()
