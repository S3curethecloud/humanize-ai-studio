from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.v2.domain.provider_routing import (
    ProviderModelTarget,
)


class ProviderCatalogRepository(Protocol):
    def create(
        self,
        target: ProviderModelTarget,
    ) -> ProviderModelTarget: ...

    def get(
        self,
        target_id: str,
    ) -> ProviderModelTarget | None: ...

    def list_targets(
        self,
        *,
        enabled_only: bool = False,
        limit: int = 1000,
    ) -> tuple[
        ProviderModelTarget,
        ...,
    ]: ...


class InMemoryProviderCatalogRepository:
    def __init__(self) -> None:
        self._targets: dict[
            str,
            ProviderModelTarget,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        target: ProviderModelTarget,
    ) -> ProviderModelTarget:
        with self._lock:
            if target.target_id in self._targets:
                raise ValueError(
                    "provider catalog target already exists: "
                    f"{target.target_id}"
                )

            _require_unique_provider_model(
                stored_targets=self._targets.values(),
                candidate=target,
            )

            candidate_targets = dict(self._targets)
            candidate_targets[target.target_id] = target
            self._targets = candidate_targets

        return target

    def get(
        self,
        target_id: str,
    ) -> ProviderModelTarget | None:
        with self._lock:
            return self._targets.get(target_id)

    def list_targets(
        self,
        *,
        enabled_only: bool = False,
        limit: int = 1000,
    ) -> tuple[
        ProviderModelTarget,
        ...,
    ]:
        _require_list_limit(limit)

        with self._lock:
            matches = (
                target
                for target in self._targets.values()
                if (
                    not enabled_only
                    or target.enabled
                )
            )

            ordered = sorted(
                matches,
                key=lambda target: target.target_id,
            )

            return tuple(ordered[:limit])


class SQLiteProviderCatalogRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        target: ProviderModelTarget,
    ) -> ProviderModelTarget:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            if _sqlite_target_id_exists(
                connection=connection,
                target_id=target.target_id,
            ):
                raise ValueError(
                    "provider catalog target already exists: "
                    f"{target.target_id}"
                )

            if _sqlite_provider_model_exists(
                connection=connection,
                target=target,
            ):
                raise ValueError(
                    "provider catalog provider/model pair "
                    "already exists"
                )

            connection.execute(
                """
                INSERT INTO provider_catalog_targets (
                    target_id,
                    provider_id,
                    model_id,
                    enabled,
                    payload
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    target.target_id,
                    target.provider.provider_id,
                    target.model.model_id,
                    1 if target.enabled else 0,
                    target.model_dump_json(),
                ),
            )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return target

    def get(
        self,
        target_id: str,
    ) -> ProviderModelTarget | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM provider_catalog_targets
                WHERE target_id = ?
                """,
                (target_id,),
            ).fetchone()

        if row is None:
            return None

        return ProviderModelTarget.model_validate_json(
            row["payload"]
        )

    def list_targets(
        self,
        *,
        enabled_only: bool = False,
        limit: int = 1000,
    ) -> tuple[
        ProviderModelTarget,
        ...,
    ]:
        _require_list_limit(limit)

        where_clause = (
            "WHERE enabled = 1"
            if enabled_only
            else ""
        )

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload
                FROM provider_catalog_targets
                {where_clause}
                ORDER BY target_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return tuple(
            ProviderModelTarget.model_validate_json(
                row["payload"]
            )
            for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    provider_catalog_targets (
                        target_id TEXT PRIMARY KEY,
                        provider_id TEXT NOT NULL,
                        model_id TEXT NOT NULL,
                        enabled INTEGER NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE UNIQUE INDEX IF NOT EXISTS
                    uq_provider_catalog_provider_model
                ON provider_catalog_targets (
                    provider_id,
                    model_id
                );

                CREATE INDEX IF NOT EXISTS
                    idx_provider_catalog_enabled_target
                ON provider_catalog_targets (
                    enabled,
                    target_id ASC
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


def _require_unique_provider_model(
    *,
    stored_targets: Iterable[ProviderModelTarget],
    candidate: ProviderModelTarget,
) -> None:
    targets: tuple[ProviderModelTarget, ...] = tuple(
        stored_targets
    )

    if any(
        target.provider.provider_id
        == candidate.provider.provider_id
        and target.model.model_id
        == candidate.model.model_id
        for target in targets
    ):
        raise ValueError(
            "provider catalog provider/model pair already exists"
        )


def _sqlite_target_id_exists(
    *,
    connection: sqlite3.Connection,
    target_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM provider_catalog_targets
        WHERE target_id = ?
        LIMIT 1
        """,
        (target_id,),
    ).fetchone()

    return row is not None


def _sqlite_provider_model_exists(
    *,
    connection: sqlite3.Connection,
    target: ProviderModelTarget,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM provider_catalog_targets
        WHERE provider_id = ?
          AND model_id = ?
        LIMIT 1
        """,
        (
            target.provider.provider_id,
            target.model.model_id,
        ),
    ).fetchone()

    return row is not None


def _require_list_limit(
    limit: int,
) -> None:
    if limit < 1 or limit > 10000:
        raise ValueError(
            "provider catalog list limit must be "
            "between 1 and 10000"
        )
