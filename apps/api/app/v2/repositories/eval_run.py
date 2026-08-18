from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.v2.domain.eval_ops import EvaluationRunRecord


class EvaluationRunRepository(Protocol):
    def create(
        self,
        record: EvaluationRunRecord,
    ) -> EvaluationRunRecord: ...

    def get(
        self,
        run_id: str,
    ) -> EvaluationRunRecord | None: ...

    def list_runs(
        self,
        *,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationRunRecord, ...]: ...


class InMemoryEvaluationRunRepository:
    def __init__(self) -> None:
        self._records: dict[
            str,
            EvaluationRunRecord,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        record: EvaluationRunRecord,
    ) -> EvaluationRunRecord:
        run_id = record.identity.run_id

        with self._lock:
            if run_id in self._records:
                raise ValueError(
                    "evaluation run already exists: "
                    f"{run_id}"
                )

            candidate = dict(self._records)
            candidate[run_id] = record
            self._records = candidate

        return record

    def get(
        self,
        run_id: str,
    ) -> EvaluationRunRecord | None:
        with self._lock:
            return self._records.get(run_id)

    def list_runs(
        self,
        *,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationRunRecord, ...]:
        _require_list_limit(limit)

        with self._lock:
            matches = (
                record
                for record in self._records.values()
                if _matches_filters(
                    record=record,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    target_id=target_id,
                )
            )

            ordered = sorted(
                matches,
                key=lambda record: record.identity.run_id,
            )

            return tuple(ordered[:limit])


class SQLiteEvaluationRunRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        record: EvaluationRunRecord,
    ) -> EvaluationRunRecord:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            if _sqlite_run_exists(
                connection=connection,
                run_id=record.identity.run_id,
            ):
                raise ValueError(
                    "evaluation run already exists: "
                    f"{record.identity.run_id}"
                )

            connection.execute(
                """
                INSERT INTO evaluation_runs (
                    run_id,
                    dataset_id,
                    dataset_version,
                    target_id,
                    outcome,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.identity.run_id,
                    record.identity.dataset.dataset_id,
                    record.identity.dataset.dataset_version,
                    record.identity.target_id,
                    record.outcome.value,
                    record.model_dump_json(),
                ),
            )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return record

    def get(
        self,
        run_id: str,
    ) -> EvaluationRunRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM evaluation_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        return EvaluationRunRecord.model_validate_json(
            row["payload"]
        )

    def list_runs(
        self,
        *,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationRunRecord, ...]:
        _require_list_limit(limit)

        conditions: list[str] = []
        parameters: list[object] = []

        if dataset_id is not None:
            conditions.append("dataset_id = ?")
            parameters.append(dataset_id)

        if dataset_version is not None:
            conditions.append("dataset_version = ?")
            parameters.append(dataset_version)

        if target_id is not None:
            conditions.append("target_id = ?")
            parameters.append(target_id)

        where_clause = (
            "WHERE " + " AND ".join(conditions)
            if conditions
            else ""
        )

        parameters.append(limit)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload
                FROM evaluation_runs
                {where_clause}
                ORDER BY run_id ASC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()

        return tuple(
            EvaluationRunRecord.model_validate_json(
                row["payload"]
            )
            for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    evaluation_runs (
                        run_id TEXT PRIMARY KEY,
                        dataset_id TEXT NOT NULL,
                        dataset_version TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        payload TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_evaluation_runs_dataset
                ON evaluation_runs (
                    dataset_id ASC,
                    dataset_version ASC,
                    run_id ASC
                );

                CREATE INDEX IF NOT EXISTS
                    idx_evaluation_runs_target
                ON evaluation_runs (
                    target_id ASC,
                    run_id ASC
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


def _matches_filters(
    *,
    record: EvaluationRunRecord,
    dataset_id: str | None,
    dataset_version: str | None,
    target_id: str | None,
) -> bool:
    dataset = record.identity.dataset

    if (
        dataset_id is not None
        and dataset.dataset_id != dataset_id
    ):
        return False

    if (
        dataset_version is not None
        and dataset.dataset_version != dataset_version
    ):
        return False

    return not (
        target_id is not None
        and record.identity.target_id != target_id
    )


def _sqlite_run_exists(
    *,
    connection: sqlite3.Connection,
    run_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM evaluation_runs
        WHERE run_id = ?
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()

    return row is not None


def _require_list_limit(
    limit: int,
) -> None:
    if limit < 1 or limit > 10000:
        raise ValueError(
            "evaluation run list limit must be "
            "between 1 and 10000"
        )
