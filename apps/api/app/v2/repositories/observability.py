from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol

from app.v2.domain.observability import (
    PersistentObservabilityEvent,
)


class ObservabilityEventRepository(Protocol):
    def create(
        self,
        event: PersistentObservabilityEvent,
    ) -> PersistentObservabilityEvent: ...

    def get(
        self,
        event_id: str,
    ) -> PersistentObservabilityEvent | None: ...

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        limit: int = 1000,
    ) -> tuple[
        PersistentObservabilityEvent,
        ...,
    ]: ...


class InMemoryObservabilityEventRepository:
    def __init__(self) -> None:
        self._events: dict[
            str,
            PersistentObservabilityEvent,
        ] = {}

    def create(
        self,
        event: PersistentObservabilityEvent,
    ) -> PersistentObservabilityEvent:
        if event.event_id in self._events:
            raise ValueError(f"observability event already exists: {event.event_id}")

        self._events[event.event_id] = event

        return event

    def get(
        self,
        event_id: str,
    ) -> PersistentObservabilityEvent | None:
        return self._events.get(event_id)

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        limit: int = 1000,
    ) -> tuple[
        PersistentObservabilityEvent,
        ...,
    ]:
        _require_query_window(
            period_start=period_start,
            period_end=period_end,
            limit=limit,
        )

        events = (
            event
            for event in self._events.values()
            if (
                event.workspace_id == workspace_id
                and period_start <= event.occurred_at < period_end
            )
        )

        ordered = sorted(
            events,
            key=lambda event: (
                event.occurred_at,
                event.event_id,
            ),
        )

        return tuple(ordered[:limit])


class SQLiteObservabilityEventRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        event: PersistentObservabilityEvent,
    ) -> PersistentObservabilityEvent:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO observability_events (
                        event_id,
                        workspace_id,
                        user_id,
                        operation,
                        outcome,
                        occurred_at,
                        payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.workspace_id,
                        event.user_id,
                        event.operation.value,
                        event.outcome.value,
                        event.occurred_at.isoformat(),
                        event.model_dump_json(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"observability event already exists: {event.event_id}") from exc

        return event

    def get(
        self,
        event_id: str,
    ) -> PersistentObservabilityEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM observability_events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

        if row is None:
            return None

        return PersistentObservabilityEvent.model_validate_json(row["payload"])

    def list_for_workspace(
        self,
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        limit: int = 1000,
    ) -> tuple[
        PersistentObservabilityEvent,
        ...,
    ]:
        _require_query_window(
            period_start=period_start,
            period_end=period_end,
            limit=limit,
        )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM observability_events
                WHERE workspace_id = ?
                  AND occurred_at >= ?
                  AND occurred_at < ?
                ORDER BY
                    occurred_at ASC,
                    event_id ASC
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
            PersistentObservabilityEvent.model_validate_json(row["payload"]) for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    observability_events (
                        event_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_observability_events_workspace_time
                ON observability_events (
                    workspace_id,
                    occurred_at ASC,
                    event_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_observability_events_workspace_operation_time
                ON observability_events (
                    workspace_id,
                    operation,
                    occurred_at ASC
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path))
        connection.row_factory = sqlite3.Row

        return connection


def _require_query_window(
    *,
    period_start: datetime,
    period_end: datetime,
    limit: int,
) -> None:
    for value in (
        period_start,
        period_end,
    ):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observability query timestamps must be timezone-aware")

    if period_end <= period_start:
        raise ValueError("observability query period_end must be after period_start")

    if limit < 1:
        raise ValueError("observability query limit must be at least 1")
