from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_provider_routing_operations import (
    InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.repositories.enterprise_provider_routing_operations_sqlite import (
    SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository,
)
from app.v2.services.enterprise_provider_routing_operation_repository_factory import (
    ExternalEnterpriseProviderRoutingOperationPersistenceUnavailableError,
    build_enterprise_provider_routing_operation_repository,
)


def test_operation_factory_builds_memory_repository() -> None:
    repository = (
        build_enterprise_provider_routing_operation_repository(
            V2PersistenceSettings(
                backend=(
                    PersistenceBackend.MEMORY
                ),
                sqlite_path=None,
                database_url=None,
            )
        )
    )

    assert isinstance(
        repository,
        InMemoryEnterpriseWorkspaceProviderRoutingOperationRepository,
    )


def test_operation_factory_builds_sqlite_repository(
    tmp_path,
) -> None:
    repository = (
        build_enterprise_provider_routing_operation_repository(
            V2PersistenceSettings(
                backend=(
                    PersistenceBackend.SQLITE
                ),
                sqlite_path=(
                    tmp_path
                    / "routing-operation.sqlite3"
                ),
                database_url=None,
            )
        )
    )

    assert isinstance(
        repository,
        SQLiteEnterpriseWorkspaceProviderRoutingOperationRepository,
    )


def test_operation_factory_external_backend_fails_closed() -> None:
    settings = V2PersistenceSettings(
        backend=(
            PersistenceBackend.EXTERNAL
        ),
        sqlite_path=None,
        database_url=(
            "postgresql://example.invalid/humanize"
        ),
    )

    try:
        build_enterprise_provider_routing_operation_repository(
            settings
        )
    except (
        ExternalEnterpriseProviderRoutingOperationPersistenceUnavailableError
    ):
        pass
    else:
        raise AssertionError(
            "external routing operation persistence "
            "must fail closed without an adapter"
        )
