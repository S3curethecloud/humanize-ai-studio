from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.eval_run import (
    EvaluationRunRepository,
    InMemoryEvaluationRunRepository,
    SQLiteEvaluationRunRepository,
)


class ExternalEvaluationRunPersistenceUnavailableError(
    RuntimeError
):
    pass


def build_evaluation_run_repository(
    settings: V2PersistenceSettings,
) -> EvaluationRunRepository:
    settings.validate()

    if settings.backend is PersistenceBackend.MEMORY:
        return InMemoryEvaluationRunRepository()

    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite evaluation run persistence "
                "requires a database path."
            )

        return SQLiteEvaluationRunRepository(
            database_path=settings.sqlite_path,
        )

    if settings.backend is PersistenceBackend.EXTERNAL:
        raise ExternalEvaluationRunPersistenceUnavailableError(
            "External evaluation run persistence is configured "
            "but no external evaluation run adapter has been "
            "installed."
        )

    raise RuntimeError(
        "Unsupported evaluation run persistence backend."
    )
