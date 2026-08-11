from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    WorkspaceMembership,
    WorkspaceRecord,
)


class TransactionalUserWriter(Protocol):
    def create(
        self,
        user: UserRecord,
    ) -> UserRecord: ...


class TransactionalWorkspaceWriter(Protocol):
    def create(
        self,
        workspace: WorkspaceRecord,
    ) -> WorkspaceRecord: ...


class TransactionalMembershipWriter(Protocol):
    def create(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership: ...


class TransactionalHistoryWriter(Protocol):
    def create(
        self,
        record: RewriteHistoryRecord,
    ) -> RewriteHistoryRecord: ...


class UnitOfWork(Protocol):
    @property
    def users(
        self,
    ) -> TransactionalUserWriter: ...

    @property
    def workspaces(
        self,
    ) -> TransactionalWorkspaceWriter: ...

    @property
    def memberships(
        self,
    ) -> TransactionalMembershipWriter: ...

    @property
    def history(
        self,
    ) -> TransactionalHistoryWriter: ...

    def __enter__(
        self,
    ) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
