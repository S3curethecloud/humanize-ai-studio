from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaAccountingEntry,
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.services.enterprise_quota_decision_service import (
    EnterpriseQuotaDecisionEvidence,
    EnterpriseQuotaDecisionService,
)


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseQuotaAtomicConsumeResult:
    consumed: bool
    decisions: tuple[
        EnterpriseQuotaDecisionEvidence,
        ...,
    ]


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

    def check_and_consume_group(
        self,
        *,
        entries: tuple[
            EnterpriseQuotaAccountingEntry,
            ...,
        ],
        limits: tuple[
            EnterpriseWorkspaceQuotaLimit,
            ...,
        ],
        decision_service: EnterpriseQuotaDecisionService,
    ) -> EnterpriseQuotaAtomicConsumeResult: ...


class InMemoryEnterpriseQuotaAccountingRepository:
    def __init__(self) -> None:
        self._entries: dict[
            str,
            EnterpriseQuotaAccountingEntry,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        entry: EnterpriseQuotaAccountingEntry,
    ) -> EnterpriseQuotaAccountingEntry:
        with self._lock:
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
        with self._lock:
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

        with self._lock:
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
        with self._lock:
            return self._sum_usage_locked(
                workspace_id=workspace_id,
                dimension=dimension,
                window=window,
            )

    def check_and_consume_group(
        self,
        *,
        entries: tuple[
            EnterpriseQuotaAccountingEntry,
            ...,
        ],
        limits: tuple[
            EnterpriseWorkspaceQuotaLimit,
            ...,
        ],
        decision_service: EnterpriseQuotaDecisionService,
    ) -> EnterpriseQuotaAtomicConsumeResult:
        (
            ordered_entries,
            limit_by_dimension,
        ) = _prepare_atomic_group(
            entries=entries,
            limits=limits,
        )

        workspace_id = ordered_entries[0].workspace_id
        accounting_group_id = ordered_entries[0].accounting_group_id
        window = ordered_entries[0].window

        with self._lock:
            _require_memory_group_absent(
                stored_entries=self._entries,
                workspace_id=workspace_id,
                accounting_group_id=(accounting_group_id),
            )

            _require_memory_entry_ids_absent(
                stored_entries=self._entries,
                entries=ordered_entries,
            )

            decisions = tuple(
                decision_service.evaluate(
                    workspace_id=workspace_id,
                    dimension=entry.dimension,
                    window=window,
                    limit=limit_by_dimension.get(entry.dimension),
                    current_usage=(
                        self._sum_usage_locked(
                            workspace_id=(workspace_id),
                            dimension=(entry.dimension),
                            window=window,
                        )
                    ),
                    requested_quantity=(entry.quantity),
                )
                for entry in ordered_entries
            )

            if not all(decision.allowed for decision in decisions):
                return EnterpriseQuotaAtomicConsumeResult(
                    consumed=False,
                    decisions=decisions,
                )

            candidate_entries = dict(self._entries)

            for entry in ordered_entries:
                candidate_entries[entry.accounting_entry_id] = entry

            self._entries = candidate_entries

            return EnterpriseQuotaAtomicConsumeResult(
                consumed=True,
                decisions=decisions,
            )

    def _sum_usage_locked(
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
        try:
            with self._connect() as connection:
                _insert_entry(
                    connection=connection,
                    entry=entry,
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
            return _sqlite_sum_usage(
                connection=connection,
                workspace_id=workspace_id,
                dimension=dimension,
                window=window,
            )

    def check_and_consume_group(
        self,
        *,
        entries: tuple[
            EnterpriseQuotaAccountingEntry,
            ...,
        ],
        limits: tuple[
            EnterpriseWorkspaceQuotaLimit,
            ...,
        ],
        decision_service: EnterpriseQuotaDecisionService,
    ) -> EnterpriseQuotaAtomicConsumeResult:
        (
            ordered_entries,
            limit_by_dimension,
        ) = _prepare_atomic_group(
            entries=entries,
            limits=limits,
        )

        workspace_id = ordered_entries[0].workspace_id
        accounting_group_id = ordered_entries[0].accounting_group_id
        window = ordered_entries[0].window

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            _require_sqlite_group_absent(
                connection=connection,
                workspace_id=workspace_id,
                accounting_group_id=(accounting_group_id),
            )

            _require_sqlite_entry_ids_absent(
                connection=connection,
                entries=ordered_entries,
            )

            decisions = tuple(
                decision_service.evaluate(
                    workspace_id=workspace_id,
                    dimension=entry.dimension,
                    window=window,
                    limit=limit_by_dimension.get(entry.dimension),
                    current_usage=(
                        _sqlite_sum_usage(
                            connection=connection,
                            workspace_id=(workspace_id),
                            dimension=(entry.dimension),
                            window=window,
                        )
                    ),
                    requested_quantity=(entry.quantity),
                )
                for entry in ordered_entries
            )

            if not all(decision.allowed for decision in decisions):
                connection.rollback()

                return EnterpriseQuotaAtomicConsumeResult(
                    consumed=False,
                    decisions=decisions,
                )

            for entry in ordered_entries:
                _insert_entry(
                    connection=connection,
                    entry=entry,
                )

            connection.commit()

            return EnterpriseQuotaAtomicConsumeResult(
                consumed=True,
                decisions=decisions,
            )
        except sqlite3.IntegrityError as exc:
            connection.rollback()

            raise ValueError(
                "enterprise quota atomic accounting group conflicts with existing accounting"
            ) from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

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


def _prepare_atomic_group(
    *,
    entries: tuple[
        EnterpriseQuotaAccountingEntry,
        ...,
    ],
    limits: tuple[
        EnterpriseWorkspaceQuotaLimit,
        ...,
    ],
) -> tuple[
    tuple[
        EnterpriseQuotaAccountingEntry,
        ...,
    ],
    dict[
        EnterpriseQuotaDimension,
        EnterpriseWorkspaceQuotaLimit,
    ],
]:
    if not entries:
        raise ValueError("enterprise quota atomic accounting group must not be empty")

    first = entries[0]

    entry_ids: set[str] = set()
    dimensions: set[EnterpriseQuotaDimension] = set()

    for entry in entries:
        if entry.accounting_entry_id in entry_ids:
            raise ValueError(
                "enterprise quota atomic accounting group contains duplicate entry ids"
            )

        entry_ids.add(entry.accounting_entry_id)

        if entry.dimension in dimensions:
            raise ValueError(
                "enterprise quota atomic accounting group contains duplicate dimensions"
            )

        dimensions.add(entry.dimension)

        if entry.workspace_id != first.workspace_id:
            raise ValueError("enterprise quota atomic accounting group must use one workspace")

        if entry.accounting_group_id != first.accounting_group_id:
            raise ValueError(
                "enterprise quota atomic accounting group must use one accounting_group_id"
            )

        if entry.operation is not first.operation:
            raise ValueError("enterprise quota atomic accounting group must use one operation")

        if not _windows_match(
            entry.window,
            first.window,
        ):
            raise ValueError("enterprise quota atomic accounting group must use one window")

    limit_by_dimension: dict[
        EnterpriseQuotaDimension,
        EnterpriseWorkspaceQuotaLimit,
    ] = {}

    for limit in limits:
        if limit.dimension in limit_by_dimension:
            raise ValueError("enterprise quota atomic accounting group contains duplicate limits")

        if limit.dimension not in dimensions:
            raise ValueError(
                "enterprise quota atomic accounting "
                "group contains a limit for an "
                "unrequested dimension"
            )

        limit_by_dimension[limit.dimension] = limit

    ordered_entries = tuple(
        sorted(
            entries,
            key=lambda entry: (
                entry.dimension.value,
                entry.accounting_entry_id,
            ),
        )
    )

    return (
        ordered_entries,
        limit_by_dimension,
    )


def _require_memory_group_absent(
    *,
    stored_entries: dict[
        str,
        EnterpriseQuotaAccountingEntry,
    ],
    workspace_id: str,
    accounting_group_id: str,
) -> None:
    if any(
        entry.workspace_id == workspace_id and entry.accounting_group_id == accounting_group_id
        for entry in stored_entries.values()
    ):
        raise ValueError("enterprise quota accounting group already exists")


def _require_memory_entry_ids_absent(
    *,
    stored_entries: dict[
        str,
        EnterpriseQuotaAccountingEntry,
    ],
    entries: tuple[
        EnterpriseQuotaAccountingEntry,
        ...,
    ],
) -> None:
    if any(entry.accounting_entry_id in stored_entries for entry in entries):
        raise ValueError("enterprise quota accounting entry already exists")


def _require_sqlite_group_absent(
    *,
    connection: sqlite3.Connection,
    workspace_id: str,
    accounting_group_id: str,
) -> None:
    row = connection.execute(
        """
        SELECT 1
        FROM enterprise_quota_accounting
        WHERE workspace_id = ?
          AND accounting_group_id = ?
        LIMIT 1
        """,
        (
            workspace_id,
            accounting_group_id,
        ),
    ).fetchone()

    if row is not None:
        raise ValueError("enterprise quota accounting group already exists")


def _require_sqlite_entry_ids_absent(
    *,
    connection: sqlite3.Connection,
    entries: tuple[
        EnterpriseQuotaAccountingEntry,
        ...,
    ],
) -> None:
    for entry in entries:
        row = connection.execute(
            """
            SELECT 1
            FROM enterprise_quota_accounting
            WHERE accounting_entry_id = ?
            LIMIT 1
            """,
            (entry.accounting_entry_id,),
        ).fetchone()

        if row is not None:
            raise ValueError("enterprise quota accounting entry already exists")


def _insert_entry(
    *,
    connection: sqlite3.Connection,
    entry: EnterpriseQuotaAccountingEntry,
) -> None:
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
            _canonical_timestamp(entry.window.window_start),
            _canonical_timestamp(entry.window.window_end),
            _canonical_timestamp(entry.occurred_at),
            entry.model_dump_json(),
        ),
    )


def _sqlite_sum_usage(
    *,
    connection: sqlite3.Connection,
    workspace_id: str,
    dimension: EnterpriseQuotaDimension,
    window: EnterpriseQuotaWindow,
) -> int:
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
