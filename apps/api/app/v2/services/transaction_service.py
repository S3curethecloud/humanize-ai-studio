from __future__ import annotations

from uuid import uuid4

from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    WorkspaceMembership,
    WorkspaceRecord,
    WorkspaceRole,
)
from app.v2.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)


class TransactionService:
    def __init__(
        self,
        unit_of_work: SQLiteUnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work

    def create_user_and_workspace(
        self,
        *,
        email: str,
        display_name: str,
        workspace_name: str,
    ) -> tuple[
        UserRecord,
        WorkspaceRecord,
        WorkspaceMembership,
    ]:
        user = UserRecord(
            user_id=f"user_{uuid4().hex}",
            email=email,
            display_name=display_name,
        )

        workspace = WorkspaceRecord(
            workspace_id=(f"workspace_{uuid4().hex}"),
            name=workspace_name,
            created_by_user_id=user.user_id,
        )

        membership = WorkspaceMembership(
            workspace_id=workspace.workspace_id,
            user_id=user.user_id,
            role=WorkspaceRole.OWNER,
        )

        with self._unit_of_work as uow:
            uow.users.create(user)
            uow.workspaces.create(workspace)
            uow.memberships.create(membership)

        return (
            user,
            workspace,
            membership,
        )

    def record_history(
        self,
        *,
        record: RewriteHistoryRecord,
    ) -> RewriteHistoryRecord:
        with self._unit_of_work as uow:
            uow.history.create(record)

        return record
