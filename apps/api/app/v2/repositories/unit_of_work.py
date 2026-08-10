from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType

from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    WorkspaceMembership,
    WorkspaceRecord,
)
from app.v2.repositories.sqlite import (
    initialize_database,
)


class TransactionalUserRepository:
    def __init__(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        self._connection = connection

    def create(
        self,
        user: UserRecord,
    ) -> UserRecord:
        self._connection.execute(
            """
            INSERT INTO users (
                user_id,
                email,
                display_name,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user.user_id,
                user.email,
                user.display_name,
                user.created_at.isoformat(),
            ),
        )

        return user


class TransactionalWorkspaceRepository:
    def __init__(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        self._connection = connection

    def create(
        self,
        workspace: WorkspaceRecord,
    ) -> WorkspaceRecord:
        self._connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                name,
                created_by_user_id,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                workspace.workspace_id,
                workspace.name,
                workspace.created_by_user_id,
                workspace.created_at.isoformat(),
            ),
        )

        return workspace


class TransactionalMembershipRepository:
    def __init__(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        self._connection = connection

    def create(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership:
        self._connection.execute(
            """
            INSERT INTO memberships (
                workspace_id,
                user_id,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                membership.workspace_id,
                membership.user_id,
                membership.role.value,
                membership.created_at.isoformat(),
            ),
        )

        return membership


class TransactionalRewriteHistoryRepository:
    def __init__(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        self._connection = connection

    def create(
        self,
        record: RewriteHistoryRecord,
    ) -> RewriteHistoryRecord:
        self._connection.execute(
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
                fallback_used,
                verification_decision,
                editorial_quality_decision,
                status,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?,
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
                int(record.fallback_used),
                record.verification_decision,
                record.editorial_quality_decision,
                record.status.value,
                record.created_at.isoformat(),
            ),
        )

        return record


class SQLiteUnitOfWork:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        self._connection: sqlite3.Connection | None = None

        self.users: TransactionalUserRepository
        self.workspaces: TransactionalWorkspaceRepository
        self.memberships: TransactionalMembershipRepository
        self.history: TransactionalRewriteHistoryRepository

        initialize_database(database_path)

    def __enter__(
        self,
    ) -> SQLiteUnitOfWork:
        connection = sqlite3.connect(str(self._database_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")

        self._connection = connection

        self.users = TransactionalUserRepository(connection)
        self.workspaces = TransactionalWorkspaceRepository(connection)
        self.memberships = TransactionalMembershipRepository(connection)
        self.history = TransactionalRewriteHistoryRepository(connection)

        return self

    def commit(self) -> None:
        if self._connection is None:
            raise RuntimeError("Unit of work is not active.")

        self._connection.commit()

    def rollback(self) -> None:
        if self._connection is None:
            raise RuntimeError("Unit of work is not active.")

        self._connection.rollback()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_value
        del traceback

        if self._connection is None:
            return

        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
            self._connection = None
