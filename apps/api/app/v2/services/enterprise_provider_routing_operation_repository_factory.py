from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    EnterpriseWorkspaceProviderRoutingOperationRepository,
    InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.repositories.enterprise_provider_routing_operations_sqlite import (
    SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository,
)


class ExternalEnterpriseProviderRoutingOperationPersistenceUnavailableError(
    RuntimeError,
):
    pass


def build_enterprise_provider_routing_operation_repository(
    settings: V2PersistenceSettings,
) -> EnterpriseWorkspaceProviderRoutingOperationRepository:
    settings.validate()

    if (
        settings.backend
        is PersistenceBackend.MEMORY
    ):
        return (
            InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository()
        )

    if (
        settings.backend
        is PersistenceBackend.SQLITE
    ):
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite enterprise provider routing "
                "operation persistence requires a database path."
            )

        return (
            SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository(
                database_path=settings.sqlite_path,
            )
        )

    if (
        settings.backend
        is PersistenceBackend.EXTERNAL
    ):
        raise (
            ExternalEnterpriseProviderRoutingOperationPersistenceUnavailableError(
                "External enterprise provider routing operation "
                "persistence is configured but no external "
                "routing operation adapter has been installed."
            )
        )

    raise RuntimeError(
        "Unsupported enterprise provider routing "
        "operation persistence backend."
    )
