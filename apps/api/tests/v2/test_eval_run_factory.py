from __future__ import annotations

from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.eval_run import (
    InMemoryEvaluationRunRepository,
    SQLiteEvaluationRunRepository,
)
from app.v2.services.eval_run_factory import (
    ExternalEvaluationRunPersistenceUnavailableError,
    build_evaluation_run_repository,
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
    repository = build_evaluation_run_repository(
        _settings(
            backend=PersistenceBackend.MEMORY
        )
    )

    assert isinstance(
        repository,
        InMemoryEvaluationRunRepository,
    )


def test_sqlite_builds_sqlite_repository(
    tmp_path: Path,
) -> None:
    repository = build_evaluation_run_repository(
        _settings(
            backend=PersistenceBackend.SQLITE,
            sqlite_path=(
                tmp_path
                / "evaluation-runs.sqlite3"
            ),
        )
    )

    assert isinstance(
        repository,
        SQLiteEvaluationRunRepository,
    )


def test_sqlite_without_path_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="SQLITE_PATH",
    ):
        build_evaluation_run_repository(
            _settings(
                backend=PersistenceBackend.SQLITE,
            )
        )


def test_external_without_url_fails_shared_validation() -> None:
    with pytest.raises(
        ValueError,
        match="DATABASE_URL",
    ):
        build_evaluation_run_repository(
            _settings(
                backend=PersistenceBackend.EXTERNAL,
            )
        )


def test_external_with_url_fails_without_adapter() -> None:
    with pytest.raises(
        ExternalEvaluationRunPersistenceUnavailableError,
        match="no external evaluation run adapter",
    ):
        build_evaluation_run_repository(
            _settings(
                backend=PersistenceBackend.EXTERNAL,
                database_url=(
                    "postgresql://example/eval"
                ),
            )
        )
