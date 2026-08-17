from __future__ import annotations

from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.eval_dataset import (
    InMemoryEvaluationDatasetRepository,
    SQLiteEvaluationDatasetRepository,
)
from app.v2.services.eval_dataset_factory import (
    ExternalEvaluationDatasetPersistenceUnavailableError,
    build_evaluation_dataset_repository,
)


def _settings(
    *,
    backend: PersistenceBackend,
    sqlite_path: Path | None = None,
    database_url: str | None = None,
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=backend,
        sqlite_path=sqlite_path,
        database_url=database_url,
    )


def test_memory_builds_memory_repository() -> None:
    repository = build_evaluation_dataset_repository(
        _settings(
            backend=PersistenceBackend.MEMORY
        )
    )

    assert isinstance(
        repository,
        InMemoryEvaluationDatasetRepository,
    )


def test_sqlite_builds_sqlite_repository(
    tmp_path: Path,
) -> None:
    repository = build_evaluation_dataset_repository(
        _settings(
            backend=PersistenceBackend.SQLITE,
            sqlite_path=(
                tmp_path
                / "evaluation.sqlite3"
            ),
        )
    )

    assert isinstance(
        repository,
        SQLiteEvaluationDatasetRepository,
    )


def test_sqlite_without_path_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="SQLITE_PATH",
    ):
        build_evaluation_dataset_repository(
            _settings(
                backend=PersistenceBackend.SQLITE,
            )
        )


def test_external_without_url_fails_shared_validation() -> None:
    with pytest.raises(
        ValueError,
        match="DATABASE_URL",
    ):
        build_evaluation_dataset_repository(
            _settings(
                backend=PersistenceBackend.EXTERNAL,
            )
        )


def test_external_with_url_fails_without_adapter() -> None:
    with pytest.raises(
        ExternalEvaluationDatasetPersistenceUnavailableError,
        match="no external evaluation dataset adapter",
    ):
        build_evaluation_dataset_repository(
            _settings(
                backend=PersistenceBackend.EXTERNAL,
                database_url=(
                    "postgresql://example/eval"
                ),
            )
        )
