from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.eval_dataset import (
    EvaluationDatasetRepository,
    InMemoryEvaluationDatasetRepository,
    SQLiteEvaluationDatasetRepository,
)


class ExternalEvaluationDatasetPersistenceUnavailableError(
    RuntimeError
):
    pass


def build_evaluation_dataset_repository(
    settings: V2PersistenceSettings,
) -> EvaluationDatasetRepository:
    settings.validate()

    if settings.backend is PersistenceBackend.MEMORY:
        return InMemoryEvaluationDatasetRepository()

    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite evaluation dataset persistence "
                "requires a database path."
            )

        return SQLiteEvaluationDatasetRepository(
            database_path=settings.sqlite_path,
        )

    if settings.backend is PersistenceBackend.EXTERNAL:
        raise (
            ExternalEvaluationDatasetPersistenceUnavailableError(
                "External evaluation dataset persistence is "
                "configured but no external evaluation "
                "dataset adapter has been installed."
            )
        )

    raise RuntimeError(
        "Unsupported evaluation dataset persistence backend."
    )
