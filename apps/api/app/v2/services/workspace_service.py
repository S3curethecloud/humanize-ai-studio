from __future__ import annotations

from uuid import uuid4

from app.v2.domain.models import (
    UserRecord,
    WorkspaceMembership,
    WorkspaceRecord,
    WorkspaceRole,
)
from app.v2.repositories.interfaces import (
    MembershipRepository,
    UserRepository,
    WorkspaceRepository,
)
from app.v2.repositories.uow_interfaces import (
    UnitOfWork,
)


class WorkspaceService:
    def __init__(
        self,
        *,
        users: UserRepository,
        workspaces: WorkspaceRepository,
        memberships: MembershipRepository,
        unit_of_work: UnitOfWork | None = None,
    ) -> None:
        self._users = users
        self._workspaces = workspaces
        self._memberships = memberships
        self._unit_of_work = unit_of_work

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
    ) -> UserRecord:
        user = UserRecord(
            user_id=f"user_{uuid4().hex}",
            email=email,
            display_name=display_name,
        )
        return self._users.create(user)

    def create_workspace(
        self,
        *,
        user_id: str,
        name: str,
    ) -> WorkspaceRecord:
        user = self._users.get(user_id)

        if user is None:
            raise ValueError(f"Unknown user: {user_id}")

        workspace = WorkspaceRecord(
            workspace_id=(f"workspace_{uuid4().hex}"),
            name=name,
            created_by_user_id=user_id,
        )

        membership = WorkspaceMembership(
            workspace_id=workspace.workspace_id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
        )

        if self._unit_of_work is not None:
            with self._unit_of_work as uow:
                uow.workspaces.create(workspace)
                uow.memberships.create(membership)

            return workspace

        workspace = self._workspaces.create(workspace)
        self._memberships.create(membership)

        return workspace

    def require_membership(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceMembership:
        membership = self._memberships.get(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        if membership is None:
            raise PermissionError(f"User is not a member of workspace {workspace_id}.")

        return membership
