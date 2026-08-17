from __future__ import annotations

from dataclasses import dataclass

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.routing_eval_evidence import (
    EvaluationEvidenceRepository,
    InMemoryEvaluationEvidenceRepository,
    InMemoryRoutingEvidenceRepository,
    RoutingEvidenceRepository,
    SQLiteEvaluationEvidenceRepository,
    SQLiteRoutingEvidenceRepository,
)


class ExternalRoutingEvalEvidencePersistenceUnavailableError(
    RuntimeError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class RoutingEvalEvidenceRepositoryBundle:
    routing: RoutingEvidenceRepository
    evaluation: EvaluationEvidenceRepository


def build_routing_eval_evidence_repositories(
    settings: V2PersistenceSettings,
) -> RoutingEvalEvidenceRepositoryBundle:
    settings.validate()

    if settings.backend is PersistenceBackend.MEMORY:
        return RoutingEvalEvidenceRepositoryBundle(
            routing=InMemoryRoutingEvidenceRepository(),
            evaluation=InMemoryEvaluationEvidenceRepository(),
        )

    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite routing/evaluation evidence "
                "persistence requires a database path."
            )

        return RoutingEvalEvidenceRepositoryBundle(
            routing=SQLiteRoutingEvidenceRepository(
                database_path=settings.sqlite_path,
            ),
            evaluation=SQLiteEvaluationEvidenceRepository(
                database_path=settings.sqlite_path,
            ),
        )

    if settings.backend is PersistenceBackend.EXTERNAL:
        raise (
            ExternalRoutingEvalEvidencePersistenceUnavailableError(
                "External routing/evaluation evidence "
                "persistence is configured but no external "
                "evidence adapter has been installed."
            )
        )

    raise RuntimeError(
        "Unsupported routing/evaluation evidence "
        "persistence backend."
    )
