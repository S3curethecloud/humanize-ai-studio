from __future__ import annotations

from dataclasses import dataclass

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.eval_dataset import (
    EvaluationDatasetRepository,
    InMemoryEvaluationDatasetRepository,
    SQLiteEvaluationDatasetRepository,
)
from app.v2.repositories.eval_run import (
    EvaluationRunRepository,
    InMemoryEvaluationRunRepository,
    SQLiteEvaluationRunRepository,
)


class ExternalEvaluationOpsPersistenceUnavailableError(
    RuntimeError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class EvaluationOpsRepositoryBundle:
    datasets: EvaluationDatasetRepository
    runs: EvaluationRunRepository


def build_evaluation_ops_repositories(
    settings: V2PersistenceSettings,
) -> EvaluationOpsRepositoryBundle:
    settings.validate()

    if settings.backend is PersistenceBackend.MEMORY:
        return EvaluationOpsRepositoryBundle(
            datasets=InMemoryEvaluationDatasetRepository(),
            runs=InMemoryEvaluationRunRepository(),
        )

    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite EvalOps persistence requires "
                "a database path."
            )

        return EvaluationOpsRepositoryBundle(
            datasets=SQLiteEvaluationDatasetRepository(
                database_path=settings.sqlite_path,
            ),
            runs=SQLiteEvaluationRunRepository(
                database_path=settings.sqlite_path,
            ),
        )

    if settings.backend is PersistenceBackend.EXTERNAL:
        raise ExternalEvaluationOpsPersistenceUnavailableError(
            "External EvalOps persistence is configured "
            "but no external EvalOps adapter has been installed."
        )

    raise RuntimeError(
        "Unsupported EvalOps persistence backend."
    )
