from __future__ import annotations

from pathlib import Path

import pytest

from app.v2.api import dependencies as v2_dependencies
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_quota import (
    InMemoryEnterpriseQuotaAccountingRepository,
    SQLiteEnterpriseQuotaAccountingRepository,
)
from app.v2.repositories.enterprise_quota_limits import (
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_quota_decision_service import (
    EnterpriseQuotaDecisionService,
)
from app.v2.services.enterprise_quota_runtime import (
    EnterpriseQuotaRuntime,
)
from app.v2.services.enterprise_quota_runtime_factory import (
    ExternalEnterpriseQuotaPersistenceUnavailableError,
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


def test_memory_factory_returns_enterprise_quota_runtime() -> None:
    runtime = build_enterprise_quota_runtime(
        _memory_settings(),
    )

    assert isinstance(
        runtime,
        EnterpriseQuotaRuntime,
    )


def test_memory_factory_uses_in_memory_accounting_repository() -> None:
    runtime = build_enterprise_quota_runtime(
        _memory_settings(),
    )

    assert isinstance(
        runtime.enforcement._accounting,
        InMemoryEnterpriseQuotaAccountingRepository,
    )


def test_memory_factory_uses_in_memory_limit_repository() -> None:
    runtime = build_enterprise_quota_runtime(
        _memory_settings(),
    )

    assert isinstance(
        runtime.enforcement._limits,
        InMemoryEnterpriseQuotaLimitRepository,
    )


def test_memory_factory_shares_exact_limit_repository() -> None:
    runtime = build_enterprise_quota_runtime(
        _memory_settings(),
    )

    assert (
        runtime.runtime_context._limits
        is runtime.enforcement._limits
    )


def test_memory_factory_builds_decision_service() -> None:
    runtime = build_enterprise_quota_runtime(
        _memory_settings(),
    )

    assert isinstance(
        runtime.enforcement._decision_service,
        EnterpriseQuotaDecisionService,
    )


def test_sqlite_factory_uses_sqlite_accounting_repository(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota-runtime.db"

    runtime = build_enterprise_quota_runtime(
        _sqlite_settings(database_path),
    )

    accounting = runtime.enforcement._accounting

    assert isinstance(
        accounting,
        SQLiteEnterpriseQuotaAccountingRepository,
    )
    assert accounting._database_path == database_path


def test_sqlite_factory_uses_sqlite_limit_repository(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota-runtime.db"

    runtime = build_enterprise_quota_runtime(
        _sqlite_settings(database_path),
    )

    limits = runtime.enforcement._limits

    assert isinstance(
        limits,
        SQLiteEnterpriseQuotaLimitRepository,
    )
    assert limits._database_path == database_path


def test_sqlite_factory_shares_exact_limit_repository(
    tmp_path: Path,
) -> None:
    runtime = build_enterprise_quota_runtime(
        _sqlite_settings(
            tmp_path / "quota-runtime.db",
        ),
    )

    assert (
        runtime.runtime_context._limits
        is runtime.enforcement._limits
    )


def test_sqlite_factory_uses_same_configured_database_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota-runtime.db"

    runtime = build_enterprise_quota_runtime(
        _sqlite_settings(database_path),
    )

    accounting = runtime.enforcement._accounting
    limits = runtime.enforcement._limits

    assert isinstance(
        accounting,
        SQLiteEnterpriseQuotaAccountingRepository,
    )
    assert isinstance(
        limits,
        SQLiteEnterpriseQuotaLimitRepository,
    )

    assert accounting._database_path == database_path
    assert limits._database_path == database_path


def test_invalid_sqlite_settings_fail_before_runtime_construction() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=None,
        database_url=None,
    )

    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_SQLITE_PATH is required",
    ):
        build_enterprise_quota_runtime(settings)


def test_external_backend_fails_explicitly() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url="postgresql://quota.example/test",
    )

    with pytest.raises(
        ExternalEnterpriseQuotaPersistenceUnavailableError,
        match="no external quota persistence adapter",
    ):
        build_enterprise_quota_runtime(settings)


def test_factory_construction_does_not_activate_global_v2services() -> None:
    build_enterprise_quota_runtime(
        _memory_settings(),
    )

    assert v2_dependencies.services.rewrite._quota_admission is None
    assert (
        v2_dependencies.services.multi_candidate
        ._multi_candidate_quota_admission
        is None
    )
    assert (
        v2_dependencies.services.long_document
        ._long_document_quota_admission
        is None
    )
