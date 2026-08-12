from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Protocol

from app.v2.domain.long_document_audit import (
    LongDocumentAuditRecord,
)


class LongDocumentAuditRepository(Protocol):
    def create(
        self,
        record: LongDocumentAuditRecord,
    ) -> LongDocumentAuditRecord: ...

    def get(
        self,
        audit_id: str,
    ) -> LongDocumentAuditRecord | None: ...

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 50,
    ) -> tuple[
        LongDocumentAuditRecord,
        ...,
    ]: ...


class InMemoryLongDocumentAuditRepository:
    def __init__(self) -> None:
        self._records: dict[
            str,
            LongDocumentAuditRecord,
        ] = {}

    def create(
        self,
        record: LongDocumentAuditRecord,
    ) -> LongDocumentAuditRecord:
        if record.audit_id in self._records:
            raise ValueError(f"long-document audit already exists: {record.audit_id}")

        self._records[record.audit_id] = record

        return record

    def get(
        self,
        audit_id: str,
    ) -> LongDocumentAuditRecord | None:
        return self._records.get(audit_id)

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 50,
    ) -> tuple[
        LongDocumentAuditRecord,
        ...,
    ]:
        records = tuple(
            record for record in self._records.values() if record.workspace_id == workspace_id
        )

        ordered = sorted(
            records,
            key=lambda record: record.created_at,
            reverse=True,
        )

        return tuple(ordered[:limit])


class SQLiteLongDocumentAuditRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)

        self._initialize()

    def create(
        self,
        record: LongDocumentAuditRecord,
    ) -> LongDocumentAuditRecord:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO long_document_audit (
                        audit_id,
                        workspace_id,
                        user_id,
                        payload,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record.audit_id,
                        record.workspace_id,
                        record.user_id,
                        record.model_dump_json(),
                        record.created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"long-document audit already exists: {record.audit_id}") from exc

        return record

    def get(
        self,
        audit_id: str,
    ) -> LongDocumentAuditRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM long_document_audit
                WHERE audit_id = ?
                """,
                (audit_id,),
            ).fetchone()

        if row is None:
            return None

        return LongDocumentAuditRecord.model_validate_json(row["payload"])

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        limit: int = 50,
    ) -> tuple[
        LongDocumentAuditRecord,
        ...,
    ]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM long_document_audit
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    workspace_id,
                    limit,
                ),
            ).fetchall()

        return tuple(LongDocumentAuditRecord.model_validate_json(row["payload"]) for row in rows)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    long_document_audit (
                        audit_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_long_document_audit_workspace_created
                ON long_document_audit (
                    workspace_id,
                    created_at DESC
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path))
        connection.row_factory = sqlite3.Row

        return connection
