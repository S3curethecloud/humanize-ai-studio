from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)


class EnterpriseQuotaLimitRepository(Protocol):
    def create(
        self,
        limit: EnterpriseWorkspaceQuotaLimit,
    ) -> EnterpriseWorkspaceQuotaLimit: ...

    def get(
        self,
        quota_limit_id: str,
    ) -> EnterpriseWorkspaceQuotaLimit | None: ...

    def resolve_exact(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
    ) -> EnterpriseWorkspaceQuotaLimit | None: ...

    def list_for_workspace_dimension(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseWorkspaceQuotaLimit,
        ...,
    ]: ...


class InMemoryEnterpriseQuotaLimitRepository:
    def __init__(self) -> None:
        self._limits: dict[
            str,
            EnterpriseWorkspaceQuotaLimit,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        limit: EnterpriseWorkspaceQuotaLimit,
    ) -> EnterpriseWorkspaceQuotaLimit:
        with self._lock:
            if limit.quota_limit_id in self._limits:
                raise ValueError(f"enterprise quota limit already exists: {limit.quota_limit_id}")

            _require_no_memory_overlap(
                stored_limits=self._limits,
                candidate=limit,
            )

            candidate_limits = dict(self._limits)
            candidate_limits[limit.quota_limit_id] = limit
            self._limits = candidate_limits

        return limit

    def get(
        self,
        quota_limit_id: str,
    ) -> EnterpriseWorkspaceQuotaLimit | None:
        with self._lock:
            return self._limits.get(quota_limit_id)

    def resolve_exact(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
    ) -> EnterpriseWorkspaceQuotaLimit | None:
        with self._lock:
            matches = tuple(
                stored
                for stored in self._limits.values()
                if (
                    stored.workspace_id == workspace_id
                    and stored.dimension is dimension
                    and _windows_match(
                        stored.window,
                        window,
                    )
                )
            )

        return _require_unambiguous_resolution(matches)

    def list_for_workspace_dimension(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseWorkspaceQuotaLimit,
        ...,
    ]:
        _require_list_limit(limit)

        with self._lock:
            matches = (
                stored
                for stored in self._limits.values()
                if (stored.workspace_id == workspace_id and stored.dimension is dimension)
            )

            ordered = sorted(
                matches,
                key=_limit_sort_key,
            )

            return tuple(ordered[:limit])


class SQLiteEnterpriseQuotaLimitRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        limit: EnterpriseWorkspaceQuotaLimit,
    ) -> EnterpriseWorkspaceQuotaLimit:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            if _sqlite_limit_id_exists(
                connection=connection,
                quota_limit_id=(limit.quota_limit_id),
            ):
                raise ValueError(f"enterprise quota limit already exists: {limit.quota_limit_id}")

            if _sqlite_overlap_exists(
                connection=connection,
                candidate=limit,
            ):
                raise ValueError("enterprise quota limit overlaps existing authority")

            _insert_limit(
                connection=connection,
                limit=limit,
            )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return limit

    def get(
        self,
        quota_limit_id: str,
    ) -> EnterpriseWorkspaceQuotaLimit | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM enterprise_quota_limits
                WHERE quota_limit_id = ?
                """,
                (quota_limit_id,),
            ).fetchone()

        if row is None:
            return None

        return EnterpriseWorkspaceQuotaLimit.model_validate_json(row["payload"])

    def resolve_exact(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        window: EnterpriseQuotaWindow,
    ) -> EnterpriseWorkspaceQuotaLimit | None:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM enterprise_quota_limits
                WHERE workspace_id = ?
                  AND dimension = ?
                  AND window_start = ?
                  AND window_end = ?
                ORDER BY quota_limit_id ASC
                LIMIT 2
                """,
                (
                    workspace_id,
                    dimension.value,
                    _canonical_timestamp(window.window_start),
                    _canonical_timestamp(window.window_end),
                ),
            ).fetchall()

        matches = tuple(
            EnterpriseWorkspaceQuotaLimit.model_validate_json(row["payload"]) for row in rows
        )

        return _require_unambiguous_resolution(matches)

    def list_for_workspace_dimension(
        self,
        *,
        workspace_id: str,
        dimension: EnterpriseQuotaDimension,
        limit: int = 1000,
    ) -> tuple[
        EnterpriseWorkspaceQuotaLimit,
        ...,
    ]:
        _require_list_limit(limit)

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM enterprise_quota_limits
                WHERE workspace_id = ?
                  AND dimension = ?
                ORDER BY
                    window_start ASC,
                    window_end ASC,
                    quota_limit_id ASC
                LIMIT ?
                """,
                (
                    workspace_id,
                    dimension.value,
                    limit,
                ),
            ).fetchall()

        return tuple(
            EnterpriseWorkspaceQuotaLimit.model_validate_json(row["payload"]) for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    enterprise_quota_limits (
                        quota_limit_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        dimension TEXT NOT NULL,
                        window_start TEXT NOT NULL,
                        window_end TEXT NOT NULL,
                        configured_limit INTEGER NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_enterprise_quota_limit_exact_scope
                ON enterprise_quota_limits (
                    workspace_id,
                    dimension,
                    window_start,
                    window_end
                );

                CREATE INDEX IF NOT EXISTS
                    idx_enterprise_quota_limit_scope
                ON enterprise_quota_limits (
                    workspace_id,
                    dimension,
                    window_start ASC,
                    window_end ASC,
                    quota_limit_id ASC
                );
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._database_path))
        connection.row_factory = sqlite3.Row

        return connection


def _require_no_memory_overlap(
    *,
    stored_limits: dict[
        str,
        EnterpriseWorkspaceQuotaLimit,
    ],
    candidate: EnterpriseWorkspaceQuotaLimit,
) -> None:
    if any(
        stored.workspace_id == candidate.workspace_id
        and stored.dimension is candidate.dimension
        and _windows_overlap(
            stored.window,
            candidate.window,
        )
        for stored in stored_limits.values()
    ):
        raise ValueError("enterprise quota limit overlaps existing authority")


def _sqlite_limit_id_exists(
    *,
    connection: sqlite3.Connection,
    quota_limit_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM enterprise_quota_limits
        WHERE quota_limit_id = ?
        LIMIT 1
        """,
        (quota_limit_id,),
    ).fetchone()

    return row is not None


def _sqlite_overlap_exists(
    *,
    connection: sqlite3.Connection,
    candidate: EnterpriseWorkspaceQuotaLimit,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM enterprise_quota_limits
        WHERE workspace_id = ?
          AND dimension = ?
          AND window_start < ?
          AND window_end > ?
        LIMIT 1
        """,
        (
            candidate.workspace_id,
            candidate.dimension.value,
            _canonical_timestamp(candidate.window.window_end),
            _canonical_timestamp(candidate.window.window_start),
        ),
    ).fetchone()

    return row is not None


def _insert_limit(
    *,
    connection: sqlite3.Connection,
    limit: EnterpriseWorkspaceQuotaLimit,
) -> None:
    connection.execute(
        """
        INSERT INTO enterprise_quota_limits (
            quota_limit_id,
            workspace_id,
            dimension,
            window_start,
            window_end,
            configured_limit,
            payload
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            limit.quota_limit_id,
            limit.workspace_id,
            limit.dimension.value,
            _canonical_timestamp(limit.window.window_start),
            _canonical_timestamp(limit.window.window_end),
            limit.limit,
            limit.model_dump_json(),
        ),
    )


def _require_unambiguous_resolution(
    matches: tuple[
        EnterpriseWorkspaceQuotaLimit,
        ...,
    ],
) -> EnterpriseWorkspaceQuotaLimit | None:
    if not matches:
        return None

    if len(matches) != 1:
        raise RuntimeError("enterprise quota limit resolution is ambiguous")

    return matches[0]


def _windows_overlap(
    left: EnterpriseQuotaWindow,
    right: EnterpriseQuotaWindow,
) -> bool:
    return _canonical_datetime(left.window_start) < _canonical_datetime(
        right.window_end
    ) and _canonical_datetime(left.window_end) > _canonical_datetime(right.window_start)


def _windows_match(
    left: EnterpriseQuotaWindow,
    right: EnterpriseQuotaWindow,
) -> bool:
    return _canonical_datetime(left.window_start) == _canonical_datetime(
        right.window_start
    ) and _canonical_datetime(left.window_end) == _canonical_datetime(right.window_end)


def _limit_sort_key(
    limit: EnterpriseWorkspaceQuotaLimit,
) -> tuple[
    datetime,
    datetime,
    str,
]:
    return (
        _canonical_datetime(limit.window.window_start),
        _canonical_datetime(limit.window.window_end),
        limit.quota_limit_id,
    )


def _canonical_datetime(
    value: datetime,
) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("enterprise quota limit repository timestamps must be timezone-aware")

    return value.astimezone(UTC)


def _canonical_timestamp(
    value: datetime,
) -> str:
    return _canonical_datetime(value).isoformat()


def _require_list_limit(
    limit: int,
) -> None:
    if limit < 1 or limit > 10000:
        raise ValueError("enterprise quota limit list limit must be between 1 and 10000")
