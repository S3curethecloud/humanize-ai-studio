from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_workspace import (
    InMemoryEnterpriseMembershipRepository,
    InMemoryEnterpriseOrganizationRepository,
    InMemoryEnterpriseWorkspaceRepository,
    SQLiteEnterpriseMembershipRepository,
    SQLiteEnterpriseOrganizationRepository,
    SQLiteEnterpriseWorkspaceRepository,
)
from app.v2.services.enterprise_authorization_resolver import (
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_runtime import (
    EnterpriseAuthorizationRuntime,
)


def _memory_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _sqlite_settings(
    database_path: Path,
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )


def _explicit_runtime() -> EnterpriseAuthorizationRuntime:
    return EnterpriseAuthorizationRuntime(
        organizations=InMemoryEnterpriseOrganizationRepository(),
        workspaces=InMemoryEnterpriseWorkspaceRepository(),
        memberships=InMemoryEnterpriseMembershipRepository(),
        authorization_resolver=MagicMock(
            spec=EnterpriseAuthorizationResolver,
        ),
    )


def test_v2_services_exposes_explicit_authorization_runtime() -> None:
    runtime = _explicit_runtime()

    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
        enterprise_authorization_runtime=runtime,
    )

    assert services.enterprise_authorization is runtime


def test_v2_services_builds_memory_authorization_runtime() -> None:
    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
    )

    runtime = services.enterprise_authorization

    assert isinstance(
        runtime.organizations,
        InMemoryEnterpriseOrganizationRepository,
    )
    assert isinstance(
        runtime.workspaces,
        InMemoryEnterpriseWorkspaceRepository,
    )
    assert isinstance(
        runtime.memberships,
        InMemoryEnterpriseMembershipRepository,
    )


def test_memory_runtime_resolver_uses_exposed_authorities() -> None:
    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
    )

    runtime = services.enterprise_authorization

    assert (
        runtime.authorization_resolver._workspaces
        is runtime.workspaces
    )
    assert (
        runtime.authorization_resolver._memberships
        is runtime.memberships
    )


def test_v2_services_builds_sqlite_authorization_runtime(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_sqlite_settings(database_path),
    )

    runtime = services.enterprise_authorization

    assert isinstance(
        runtime.organizations,
        SQLiteEnterpriseOrganizationRepository,
    )
    assert isinstance(
        runtime.workspaces,
        SQLiteEnterpriseWorkspaceRepository,
    )
    assert isinstance(
        runtime.memberships,
        SQLiteEnterpriseMembershipRepository,
    )


def test_sqlite_authorization_runtime_uses_same_database_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_sqlite_settings(database_path),
    )

    runtime = services.enterprise_authorization

    assert runtime.organizations._database_path == database_path
    assert runtime.workspaces._database_path == database_path
    assert runtime.memberships._database_path == database_path


def test_sqlite_runtime_resolver_uses_exposed_authorities(
    tmp_path: Path,
) -> None:
    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_sqlite_settings(
            tmp_path / "v2.db",
        ),
    )

    runtime = services.enterprise_authorization

    assert (
        runtime.authorization_resolver._workspaces
        is runtime.workspaces
    )
    assert (
        runtime.authorization_resolver._memberships
        is runtime.memberships
    )


def test_explicit_runtime_prevents_secondary_authority_graph() -> None:
    runtime = _explicit_runtime()

    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
        enterprise_authorization_runtime=runtime,
    )

    assert services.enterprise_authorization.organizations is (
        runtime.organizations
    )
    assert services.enterprise_authorization.workspaces is (
        runtime.workspaces
    )
    assert services.enterprise_authorization.memberships is (
        runtime.memberships
    )
    assert services.enterprise_authorization.authorization_resolver is (
        runtime.authorization_resolver
    )
