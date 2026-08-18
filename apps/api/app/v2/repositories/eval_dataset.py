from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Protocol

from app.v2.domain.eval_dataset import EvaluationDataset
from app.v2.domain.eval_ops import EvaluationDatasetIdentity


class EvaluationDatasetRepository(Protocol):
    def create(
        self,
        dataset: EvaluationDataset,
    ) -> EvaluationDataset: ...

    def get(
        self,
        identity: EvaluationDatasetIdentity,
    ) -> EvaluationDataset | None: ...

    def list_datasets(
        self,
        *,
        dataset_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationDataset, ...]: ...


class InMemoryEvaluationDatasetRepository:
    def __init__(self) -> None:
        self._datasets: dict[
            tuple[str, str],
            EvaluationDataset,
        ] = {}
        self._lock = RLock()

    def create(
        self,
        dataset: EvaluationDataset,
    ) -> EvaluationDataset:
        key = _identity_key(dataset.identity)

        with self._lock:
            if key in self._datasets:
                raise ValueError(
                    "evaluation dataset version already exists: "
                    f"{dataset.identity.dataset_id}/"
                    f"{dataset.identity.dataset_version}"
                )

            candidate = dict(self._datasets)
            candidate[key] = dataset
            self._datasets = candidate

        return dataset

    def get(
        self,
        identity: EvaluationDatasetIdentity,
    ) -> EvaluationDataset | None:
        with self._lock:
            return self._datasets.get(
                _identity_key(identity)
            )

    def list_datasets(
        self,
        *,
        dataset_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationDataset, ...]:
        _require_list_limit(limit)

        with self._lock:
            matches = (
                dataset
                for dataset in self._datasets.values()
                if (
                    dataset_id is None
                    or dataset.identity.dataset_id
                    == dataset_id
                )
            )

            ordered = sorted(
                matches,
                key=lambda dataset: (
                    dataset.identity.dataset_id,
                    dataset.identity.dataset_version,
                ),
            )

            return tuple(ordered[:limit])


class SQLiteEvaluationDatasetRepository:
    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def create(
        self,
        dataset: EvaluationDataset,
    ) -> EvaluationDataset:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            if _sqlite_dataset_exists(
                connection=connection,
                identity=dataset.identity,
            ):
                raise ValueError(
                    "evaluation dataset version already exists: "
                    f"{dataset.identity.dataset_id}/"
                    f"{dataset.identity.dataset_version}"
                )

            connection.execute(
                """
                INSERT INTO evaluation_datasets (
                    dataset_id,
                    dataset_version,
                    payload
                )
                VALUES (?, ?, ?)
                """,
                (
                    dataset.identity.dataset_id,
                    dataset.identity.dataset_version,
                    dataset.model_dump_json(),
                ),
            )

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return dataset

    def get(
        self,
        identity: EvaluationDatasetIdentity,
    ) -> EvaluationDataset | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM evaluation_datasets
                WHERE dataset_id = ?
                  AND dataset_version = ?
                """,
                (
                    identity.dataset_id,
                    identity.dataset_version,
                ),
            ).fetchone()

        if row is None:
            return None

        return EvaluationDataset.model_validate_json(
            row["payload"]
        )

    def list_datasets(
        self,
        *,
        dataset_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationDataset, ...]:
        _require_list_limit(limit)

        if dataset_id is None:
            query = """
                SELECT payload
                FROM evaluation_datasets
                ORDER BY
                    dataset_id ASC,
                    dataset_version ASC
                LIMIT ?
            """
            parameters: tuple[object, ...] = (
                limit,
            )
        else:
            query = """
                SELECT payload
                FROM evaluation_datasets
                WHERE dataset_id = ?
                ORDER BY
                    dataset_id ASC,
                    dataset_version ASC
                LIMIT ?
            """
            parameters = (
                dataset_id,
                limit,
            )

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return tuple(
            EvaluationDataset.model_validate_json(
                row["payload"]
            )
            for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    evaluation_datasets (
                        dataset_id TEXT NOT NULL,
                        dataset_version TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        PRIMARY KEY (
                            dataset_id,
                            dataset_version
                        )
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_evaluation_datasets_identity
                ON evaluation_datasets (
                    dataset_id ASC,
                    dataset_version ASC
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


def _identity_key(
    identity: EvaluationDatasetIdentity,
) -> tuple[str, str]:
    return (
        identity.dataset_id,
        identity.dataset_version,
    )


def _sqlite_dataset_exists(
    *,
    connection: sqlite3.Connection,
    identity: EvaluationDatasetIdentity,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM evaluation_datasets
        WHERE dataset_id = ?
          AND dataset_version = ?
        LIMIT 1
        """,
        (
            identity.dataset_id,
            identity.dataset_version,
        ),
    ).fetchone()

    return row is not None


def _require_list_limit(
    limit: int,
) -> None:
    if limit < 1 or limit > 10000:
        raise ValueError(
            "evaluation dataset list limit must be "
            "between 1 and 10000"
        )
