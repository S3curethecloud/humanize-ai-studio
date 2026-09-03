from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_provider_routing_policies import (
    EnterpriseWorkspaceProviderRoutingPolicyRepository,
    InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository,
)
from app.v2.repositories.enterprise_provider_routing_policies_sqlite import (
    SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository,
)


class ExternalEnterpriseProviderRoutingPolicyPersistenceUnavailableError(
    RuntimeError,
):
    pass


def build_enterprise_provider_routing_policy_repository(
    settings: V2PersistenceSettings,
) -> EnterpriseWorkspaceProviderRoutingPolicyRepository:
    settings.validate()

    if (
        settings.backend
        is PersistenceBackend.MEMORY
    ):
        return (
            InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository()
        )

    if (
        settings.backend
        is PersistenceBackend.SQLITE
    ):
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite enterprise provider routing "
                "policy persistence requires a database path."
            )

        return (
            SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository(
                database_path=settings.sqlite_path,
            )
        )

    if (
        settings.backend
        is PersistenceBackend.EXTERNAL
    ):
        raise (
            ExternalEnterpriseProviderRoutingPolicyPersistenceUnavailableError(
                "External enterprise provider routing policy "
                "persistence is configured but no external "
                "routing policy adapter has been installed."
            )
        )

    raise RuntimeError(
        "Unsupported enterprise provider routing "
        "policy persistence backend."
    )
