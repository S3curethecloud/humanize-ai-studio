from __future__ import annotations

from pathlib import Path

import pytest

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
from app.v2.services.enterprise_authorization_runtime import (
    EnterpriseAuthorizationRuntime,
)
from app.v2.services.enterprise_authorization_runtime_factory import (
    ExternalEnterpriseAuthorizationPersistenceUnavailableError,
    build_enterprise_authorization_runtime,
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


def test_memory_factory_returns_runtime() -> None:
    runtime = build_enterprise_authorization_runtime(
        _memory_settings()
    )

    assert isinstance(
        runtime,
        EnterpriseAuthorizationRuntime,
    )


def test_memory_factory_builds_organization_authority() -> None:
    runtime = build_enterprise_authorization_runtime(
        _memory_settings()
    )

    assert isinstance(
        runtime.organizations,
        InMemoryEnterpriseOrganizationRepository,
    )


def test_memory_factory_builds_workspace_authority() -> None:
    runtime = build_enterprise_authorization_runtime(
        _memory_settings()
    )

    assert isinstance(
        runtime.workspaces,
        InMemoryEnterpriseWorkspaceRepository,
    )


def test_memory_factory_builds_membership_authority() -> None:
    runtime = build_enterprise_authorization_runtime(
        _memory_settings()
    )

    assert isinstance(
        runtime.memberships,
        InMemoryEnterpriseMembershipRepository,
    )


def test_resolver_uses_exact_exposed_workspace_authority() -> None:
    runtime = build_enterprise_authorization_runtime(
        _memory_settings()
    )

    assert (
        runtime.authorization_resolver._workspaces
        is runtime.workspaces
    )


def test_resolver_uses_exact_exposed_membership_authority() -> None:
    runtime = build_enterprise_authorization_runtime(
        _memory_settings()
    )

    assert (
        runtime.authorization_resolver._memberships
        is runtime.memberships
    )


def test_sqlite_factory_builds_all_authorities(
    tmp_path: Path,
) -> None:
    runtime = build_enterprise_authorization_runtime(
        _sqlite_settings(
            tmp_path / "enterprise.db",
        )
    )

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


def test_sqlite_authorities_share_configured_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "enterprise.db"

    runtime = build_enterprise_authorization_runtime(
        _sqlite_settings(database_path)
    )

    assert runtime.organizations._database_path == database_path
    assert runtime.workspaces._database_path == database_path
    assert runtime.memberships._database_path == database_path


def test_sqlite_resolver_uses_exact_exposed_authorities(
    tmp_path: Path,
) -> None:
    runtime = build_enterprise_authorization_runtime(
        _sqlite_settings(
            tmp_path / "enterprise.db",
        )
    )

    assert (
        runtime.authorization_resolver._workspaces
        is runtime.workspaces
    )
    assert (
        runtime.authorization_resolver._memberships
        is runtime.memberships
    )


def test_external_backend_fails_explicitly() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url="postgresql://example.invalid/db",
    )

    with pytest.raises(
        ExternalEnterpriseAuthorizationPersistenceUnavailableError
    ):
        build_enterprise_authorization_runtime(
            settings
        )
