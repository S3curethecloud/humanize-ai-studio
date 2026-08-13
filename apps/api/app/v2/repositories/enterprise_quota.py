from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaAccountingEntry,
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
)


class EnterpriseQuotaAccountingRepository(Protocol):
    def create(
        self,
        entry: EnterpriseQuotaAccountingEntry,
    ) -> EnterpriseQuotaAccountingEntry: ...

    def get(
        self,
        accounting_entry_id: str,
    ) -> EnterpriseQuotaAccountingEntry | None: ...

    def list_for_workspace_dimension_window(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseQuotaAccountingEntry,
        ...,
    ]: ...

    def sum_usage(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
    ) -> int: ...


class InMemoryEnterpriseQuotaAccountingRepository:
    def __init__(self) -> None:
        self._entries: dict[
            str,
            EnterpriseQuotaAccountingEntry,
        ] = {}

    def create(
        self,
        entry: EnterpriseQuotaAccountingEntry,
    ) -> EnterpriseQuotaAccountingEntry:
        if entry.accounting_entry_id in self._entries:
            raise ValueError(
                f"enterprise quota accounting entry already exists: {entry.accounting_entry_id}"
            )

        self._entries[entry.accounting_entry_id] = entry

        return entry

    def get(
        self,
        accounting_entry_id: str,
    ) -> EnterpriseQuotaAccountingEntry | None:
        return self._entries.get(accounting_entry_id)

    def list_for_workspace_dimension_window(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseQuotaAccountingEntry,
        ...,
    ]:
        _require_list_limit(limit)

        entries = (
            entry
            for entry in self._entries.values()
            if (
                entry.workspace_id == workspace_id
                and entry.dimension is dimension
                and _windows_match(
                    entry.window,
                    window,
                )
            )
        )

        ordered = sorted(
            entries,
            key=lambda entry: (
                entry.occurred_at,
                entry.accounting_entry_id,
            ),
        )

        return tuple(ordered[:limit])

    def sum_usage(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
    ) -> int:
        return sum(
            entry.quantity
            for entry in self._entries.values()
            if (
                entry.workspace_id == workspace_id
                and entry.dimension is dimension
                and _windows_match(
                    entry.window,
                    window,
                )
            )
        )


class SQLiteEnterpriseQuotaAccountingRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        entry: EnterpriseQuotaAccountingEntry,
    ) -> EnterpriseQuotaAccountingEntry:
        window_start = _canonical_timestamp(entry.window.window_start)
        window_end = _canonical_timestamp(entry.window.window_end)

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO enterprise_quota_accounting (
                        accounting_entry_id,
                        accounting_group_id,
                        workspace_id,
                        operation,
                        dimension,
                        quantity,
                        window_start,
                        window_end,
                        occurred_at,
                        payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.accounting_entry_id,
                        entry.accounting_group_id,
                        entry.workspace_id,
                        entry.operation.value,
                        entry.dimension.value,
                        entry.quantity,
                        window_start,
                        window_end,
                        _canonical_timestamp(entry.occurred_at),
                        entry.model_dump_json(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"enterprise quota accounting entry already exists: {entry.accounting_entry_id}"
            ) from exc

        return entry

    def get(
        self,
        accounting_entry_id: str,
    ) -> EnterpriseQuotaAccountingEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_quota_accounting
                WHERE accounting_entry_id = ?
                """,
                (accounting_entry_id,),
            ).fetchone()

        if row is None:
            return None

        return EnterpriseQuotaAccountingEntry.model_validate_json(row["payload"])

    def list_for_workspace_dimension_window(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseQuotaAccountingEntry,
        ...,
    ]:
        _require_list_limit(limit)

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM enterprise_quota_accounting
                WHERE workspace_id = ?
                  AND dimension = ?
                  AND window_start = ?
                  AND window_end = ?
                ORDER BY
                    occurred_at ASC,
                    accounting_entry_id ASC
                LIMIT ?
                """,
                (
                    workspace_id,
                    dimension.value,
                    _canonical_timestamp(window.window_start),
                    _canonical_timestamp(window.window_end),
                    limit,
                ),
            ).fetchall()

        return tuple(
            EnterpriseQuotaAccountingEntry.model_validate_json(row["payload"]) for row in rows
        )

    def sum_usage(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
    ) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) AS usage
                FROM enterprise_quota_accounting
                WHERE workspace_id = ?
                  AND dimension = ?
                  AND window_start = ?
                  AND window_end = ?
                """,
                (
                    workspace_id,
                    dimension.value,
                    _canonical_timestamp(window.window_start),
                    _canonical_timestamp(window.window_end),
                ),
            ).fetchone()

        if row is None:
            raise RuntimeError("enterprise quota usage query returned no aggregate row")

        usage = row["usage"]

        if not isinstance(usage, int):
            raise RuntimeError("enterprise quota usage aggregate must be an integer")

        return usage

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    enterprise_quota_accounting (
                        accounting_entry_id TEXT PRIMARY KEY,
                        accounting_group_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        dimension TEXT NOT NULL,
                        quantity INTEGER NOT NULL,
                        window_start TEXT NOT NULL,
                        window_end TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_quota_workspace_dimension_window
                ON enterprise_quota_accounting (
                    workspace_id,
                    dimension,
                    window_start,
                    window_end,
                    occurred_at ASC,
                    accounting_entry_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_quota_accounting_group
                ON enterprise_quota_accounting (
                    workspace_id,
                    accounting_group_id,
                    accounting_entry_id ASC
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path))
        connection.row_factory = sqlite3.Row

        return connection


def _windows_match(
    left: EnterpriseQuotaWindow,
    right: EnterpriseQuotaWindow,
) -> bool:
    return _canonical_timestamp(left.window_start) == _canonical_timestamp(
        right.window_start
    ) and _canonical_timestamp(left.window_end) == _canonical_timestamp(right.window_end)


def _canonical_timestamp(
    value: datetime,
) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("enterprise quota repository timestamps must be timezone-aware")

    return value.astimezone(UTC).isoformat()


def _require_list_limit(
    limit: int,
) -> None:
    if limit < 1 or limit > 10000:
        raise ValueError("enterprise quota accounting list limit must be between 1 and 10000")
