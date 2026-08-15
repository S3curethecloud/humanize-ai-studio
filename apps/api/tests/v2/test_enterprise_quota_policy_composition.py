from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.repositories.enterprise_quota_limits import (
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
)
from app.v2.repositories.enterprise_workspace import (
    InMemoryEnterpriseMembershipRepository,
    InMemoryEnterpriseOrganizationRepository,
    InMemoryEnterpriseWorkspaceRepository,
)
from app.v2.services.enterprise_authorization_resolver import (
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_runtime import (
    EnterpriseAuthorizationRuntime,
)
from app.v2.services.enterprise_quota_runtime_factory import (
    build_enterprise_quota_limit_repository,
    build_enterprise_quota_runtime,
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


def _authorization_runtime() -> EnterpriseAuthorizationRuntime:
    return EnterpriseAuthorizationRuntime(
        organizations=(
            InMemoryEnterpriseOrganizationRepository()
        ),
        workspaces=InMemoryEnterpriseWorkspaceRepository(),
        memberships=InMemoryEnterpriseMembershipRepository(),
        authorization_resolver=MagicMock(
            spec=EnterpriseAuthorizationResolver,
        ),
    )


def _quota_limit() -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id="limit_requests",
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        window=EnterpriseQuotaWindow(
            window_start=datetime(
                2026,
                8,
                1,
                tzinfo=UTC,
            ),
            window_end=datetime(
                2026,
                9,
                1,
                tzinfo=UTC,
            ),
        ),
        limit=100,
    )


def test_policy_factory_builds_memory_limit_authority() -> None:
    limits = build_enterprise_quota_limit_repository(
        _memory_settings()
    )

    assert isinstance(
        limits,
        InMemoryEnterpriseQuotaLimitRepository,
    )


def test_policy_factory_builds_sqlite_limit_authority(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    limits = build_enterprise_quota_limit_repository(
        _sqlite_settings(database_path)
    )

    assert isinstance(
        limits,
        SQLiteEnterpriseQuotaLimitRepository,
    )
    assert limits._database_path == database_path


def test_v2_services_compose_quota_admin_without_runtime() -> None:
    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
        enterprise_authorization_runtime=(
            _authorization_runtime()
        ),
        quota_runtime=None,
    )

    assert isinstance(
        services.quota_admin._limits,
        InMemoryEnterpriseQuotaLimitRepository,
    )


def test_quota_admin_uses_shared_authorization_resolver() -> None:
    authorization_runtime = _authorization_runtime()

    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
        enterprise_authorization_runtime=(
            authorization_runtime
        ),
        quota_runtime=None,
    )

    assert (
        services.quota_admin._authorization_resolver
        is authorization_runtime.authorization_resolver
    )


def test_active_quota_admin_uses_exact_runtime_limit_authority() -> None:
    settings = _memory_settings()

    quota_runtime = build_enterprise_quota_runtime(
        settings
    )

    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=settings,
        enterprise_authorization_runtime=(
            _authorization_runtime()
        ),
        quota_runtime=quota_runtime,
    )

    assert services.quota_admin._limits is quota_runtime.limits


def test_inactive_sqlite_policy_authority_persists(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"
    settings = _sqlite_settings(database_path)

    first = V2Services(
        workflow=MagicMock(),
        persistence_settings=settings,
        enterprise_authorization_runtime=(
            _authorization_runtime()
        ),
        quota_runtime=None,
    )

    first.quota_admin._limits.create(
        _quota_limit()
    )

    second = V2Services(
        workflow=MagicMock(),
        persistence_settings=settings,
        enterprise_authorization_runtime=(
            _authorization_runtime()
        ),
        quota_runtime=None,
    )

    assert (
        second.quota_admin._limits.get(
            "limit_requests"
        )
        == _quota_limit()
    )


def test_policy_provisioned_before_activation_is_visible_to_runtime(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"
    settings = _sqlite_settings(database_path)

    limits = build_enterprise_quota_limit_repository(
        settings
    )
    limits.create(
        _quota_limit()
    )

    runtime = build_enterprise_quota_runtime(
        settings
    )

    assert (
        runtime.limits.get(
            "limit_requests"
        )
        == _quota_limit()
    )
