from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.v2.domain.models import (
    RewriteHistoryRecord,
    RewriteRecordStatus,
    UserRecord,
    WorkspaceMembership,
    WorkspaceRecord,
    WorkspaceRole,
)


def _connect(
    database_path: str | Path,
) -> sqlite3.Connection:
    connection = sqlite3.connect(str(database_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(
    database_path: str | Path,
) -> None:
    with _connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_by_user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (
                    created_by_user_id
                )
                REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS memberships (
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (
                    workspace_id,
                    user_id
                ),
                FOREIGN KEY (
                    workspace_id
                )
                REFERENCES workspaces(workspace_id),
                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS rewrite_history (
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
                fallback_used INTEGER NOT NULL,
                verification_decision TEXT NOT NULL,
                editorial_quality_decision TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (
                    workspace_id
                )
                REFERENCES workspaces(workspace_id),
                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS
                idx_rewrite_history_workspace_created
            ON rewrite_history (
                workspace_id,
                created_at DESC
            );
            """
        )


class SQLiteUserRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        user: UserRecord,
    ) -> UserRecord:
        with _connect(self._database_path) as connection:
            connection.execute(
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

    def get(
        self,
        user_id: str,
    ) -> UserRecord | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    email,
                    display_name,
                    created_at
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return UserRecord(
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteWorkspaceRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        workspace: WorkspaceRecord,
    ) -> WorkspaceRecord:
        with _connect(self._database_path) as connection:
            connection.execute(
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

    def get(
        self,
        workspace_id: str,
    ) -> WorkspaceRecord | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    workspace_id,
                    name,
                    created_by_user_id,
                    created_at
                FROM workspaces
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        if row is None:
            return None

        return WorkspaceRecord(
            workspace_id=row["workspace_id"],
            name=row["name"],
            created_by_user_id=(row["created_by_user_id"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteMembershipRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership:
        with _connect(self._database_path) as connection:
            connection.execute(
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

    def get(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceMembership | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    workspace_id,
                    user_id,
                    role,
                    created_at
                FROM memberships
                WHERE workspace_id = ?
                  AND user_id = ?
                """,
                (
                    workspace_id,
                    user_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return WorkspaceMembership(
            workspace_id=row["workspace_id"],
            user_id=row["user_id"],
            role=WorkspaceRole(row["role"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteRewriteHistoryRepository:
    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self._database_path = database_path
        initialize_database(database_path)

    def create(
        self,
        record: RewriteHistoryRecord,
    ) -> RewriteHistoryRecord:
        with _connect(self._database_path) as connection:
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
                    (record.editorial_quality_decision),
                    record.status.value,
                    record.created_at.isoformat(),
                ),
            )

        return record

    def get(
        self,
        rewrite_id: str,
    ) -> RewriteHistoryRecord | None:
        with _connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM rewrite_history
                WHERE rewrite_id = ?
                """,
                (rewrite_id,),
            ).fetchone()

        if row is None:
            return None

        return self._to_record(row)

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 50,
    ) -> tuple[RewriteHistoryRecord, ...]:
        with _connect(self._database_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM rewrite_history
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    workspace_id,
                    limit,
                ),
            ).fetchall()

        return tuple(self._to_record(row) for row in rows)

    def _to_record(
        self,
        row: sqlite3.Row,
    ) -> RewriteHistoryRecord:
        return RewriteHistoryRecord(
            rewrite_id=row["rewrite_id"],
            workspace_id=row["workspace_id"],
            user_id=row["user_id"],
            trace_id=row["trace_id"],
            source_text=row["source_text"],
            rewritten_text=row["rewritten_text"],
            document_type=row["document_type"],
            audience=row["audience"],
            tone=row["tone"],
            intensity=row["intensity"],
            provider_name=row["provider_name"],
            model_name=row["model_name"],
            prompt_version=row["prompt_version"],
            fallback_used=bool(row["fallback_used"]),
            verification_decision=(row["verification_decision"]),
            editorial_quality_decision=(row["editorial_quality_decision"]),
            status=RewriteRecordStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
