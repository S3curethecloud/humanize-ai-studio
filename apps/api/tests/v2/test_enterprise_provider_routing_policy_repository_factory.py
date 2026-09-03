from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_provider_routing_policies import (
    InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository,
)
from app.v2.repositories.enterprise_provider_routing_policies_sqlite import (
    SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository,
)
from app.v2.services.enterprise_provider_routing_policy_repository_factory import (
    ExternalEnterpriseProviderRoutingPolicyPersistenceUnavailableError,
    build_enterprise_provider_routing_policy_repository,
)


def test_factory_builds_memory_repository() -> None:
    repository = (
        build_enterprise_provider_routing_policy_repository(
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
        InMemoryEnterpriseWorkspaceProviderRoutingPolicyRepository,
    )


def test_factory_builds_sqlite_repository(
    tmp_path,
) -> None:
    repository = (
        build_enterprise_provider_routing_policy_repository(
            V2PersistenceSettings(
                backend=(
                    PersistenceBackend.SQLITE
                ),
                sqlite_path=(
                    tmp_path
                    / "routing-policy.sqlite3"
                ),
                database_url=None,
            )
        )
    )

    assert isinstance(
        repository,
        SQLiteEnterpriseWorkspaceProviderRoutingPolicyRepository,
    )


def test_factory_external_backend_fails_closed() -> None:
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
        build_enterprise_provider_routing_policy_repository(
            settings
        )
    except (
        ExternalEnterpriseProviderRoutingPolicyPersistenceUnavailableError
    ):
        pass
    else:
        raise AssertionError(
            "external routing policy persistence "
            "must fail closed without an adapter"
        )
