from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_evaluation_operations import (
    EnterpriseWorkspaceEvaluationOperationRepository,
    InMemoryEnterpriseWorkspaceEvaluationOperationRepository,
)
from app.v2.repositories.enterprise_evaluation_operations_sqlite import (
    SQLiteEnterpriseWorkspaceEvaluationOperationRepository,
)


class ExternalEnterpriseEvaluationOperationPersistenceUnavailableError(
    RuntimeError,
):
    pass


def build_enterprise_evaluation_operation_repository(
    settings: V2PersistenceSettings,
) -> EnterpriseWorkspaceEvaluationOperationRepository:
    settings.validate()

    if (
        settings.backend
        is PersistenceBackend.MEMORY
    ):
        return (
            InMemoryEnterpriseWorkspaceEvaluationOperationRepository()
        )

    if (
        settings.backend
        is PersistenceBackend.SQLITE
    ):
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite enterprise evaluation operation "
                "persistence requires a database path."
            )

        return (
            SQLiteEnterpriseWorkspaceEvaluationOperationRepository(
                database_path=settings.sqlite_path,
            )
        )

    if (
        settings.backend
        is PersistenceBackend.EXTERNAL
    ):
        raise (
            ExternalEnterpriseEvaluationOperationPersistenceUnavailableError(
                "External enterprise evaluation operation "
                "persistence is configured but no external "
                "evaluation operation adapter has been installed."
            )
        )

    raise RuntimeError(
        "Unsupported enterprise evaluation operation "
        "persistence backend."
    )
