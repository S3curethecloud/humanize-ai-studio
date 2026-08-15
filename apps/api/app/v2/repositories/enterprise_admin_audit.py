from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditEvent,
)


class EnterpriseAdminAuditRepository(Protocol):
    def create(
        self,
        event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseAdminAuditEvent: ...

    def get(
        self,
        audit_event_id: str,
    ) -> EnterpriseAdminAuditEvent | None: ...

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseAdminAuditEvent,
        ...,
    ]: ...


class InMemoryEnterpriseAdminAuditRepository:
    def __init__(self) -> None:
        self._events: dict[
            str,
            EnterpriseAdminAuditEvent,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseAdminAuditEvent:
        with self._lock:
            if event.audit_event_id in self._events:
                raise ValueError(
                    "enterprise admin audit event "
                    f"already exists: {event.audit_event_id}"
                )

            self._events[event.audit_event_id] = event

        return event

    def get(
        self,
        audit_event_id: str,
    ) -> EnterpriseAdminAuditEvent | None:
        with self._lock:
            return self._events.get(audit_event_id)

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseAdminAuditEvent,
        ...,
    ]:
        _require_query(
            period_start=period_start,
            period_end=period_end,
            limit=limit,
        )

        with self._lock:
            matches = (
                event
                for event in self._events.values()
                if (
                    event.workspace_id == workspace_id
                    and period_start
                    <= event.occurred_at
                    < period_end
                )
            )

            ordered = sorted(
                matches,
                key=lambda event: (
                    event.occurred_at,
                    event.audit_event_id,
                ),
            )

            return tuple(ordered[:limit])


class SQLiteEnterpriseAdminAuditRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseAdminAuditEvent:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO enterprise_admin_audit_events (
                        audit_event_id,
                        workspace_id,
                        actor_user_id,
                        action,
                        outcome,
                        occurred_at,
                        payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.audit_event_id,
                        event.workspace_id,
                        event.actor_user_id,
                        event.action.value,
                        event.outcome.value,
                        event.occurred_at.isoformat(),
                        event.model_dump_json(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "enterprise admin audit event "
                f"already exists: {event.audit_event_id}"
            ) from exc

        return event

    def get(
        self,
        audit_event_id: str,
    ) -> EnterpriseAdminAuditEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_admin_audit_events
                WHERE audit_event_id = ?
                """,
                (audit_event_id,),
            ).fetchone()

        if row is None:
            return None

        return EnterpriseAdminAuditEvent.model_validate_json(
            row["payload"]
        )

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseAdminAuditEvent,
        ...,
    ]:
        _require_query(
            period_start=period_start,
            period_end=period_end,
            limit=limit,
        )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM enterprise_admin_audit_events
                WHERE workspace_id = ?
                  AND occurred_at >= ?
                  AND occurred_at < ?
                ORDER BY
                    occurred_at ASC,
                    audit_event_id ASC
                LIMIT ?
                """,
                (
                    workspace_id,
                    period_start.isoformat(),
                    period_end.isoformat(),
                    limit,
                ),
            ).fetchall()

        return tuple(
            EnterpriseAdminAuditEvent.model_validate_json(
                row["payload"]
            )
            for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    enterprise_admin_audit_events (
                        audit_event_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        actor_user_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_admin_audit_workspace_time
                ON enterprise_admin_audit_events (
                    workspace_id,
                    occurred_at ASC,
                    audit_event_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_admin_audit_workspace_actor_time
                ON enterprise_admin_audit_events (
                    workspace_id,
                    actor_user_id,
                    occurred_at ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_admin_audit_workspace_action_time
                ON enterprise_admin_audit_events (
                    workspace_id,
                    action,
                    occurred_at ASC
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self._database_path)
        )
        connection.row_factory = sqlite3.Row

        return connection


def _require_query(
    *,
    period_start: datetime,
    period_end: datetime,
    limit: int,
) -> None:
    for value in (
        period_start,
        period_end,
    ):
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "enterprise admin audit query timestamps "
                "must be timezone-aware"
            )

    if period_end <= period_start:
        raise ValueError(
            "enterprise admin audit period_end "
            "must be after period_start"
        )

    if limit < 1 or limit > 10000:
        raise ValueError(
            "enterprise admin audit limit "
            "must be between 1 and 10000"
        )
