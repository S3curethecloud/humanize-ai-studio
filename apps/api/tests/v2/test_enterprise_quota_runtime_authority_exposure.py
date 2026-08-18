from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_quota_limits import (
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_quota_runtime_factory import (
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


def test_memory_runtime_exposes_authoritative_limit_repository() -> None:
    runtime = build_enterprise_quota_runtime(
        _memory_settings()
    )

    assert isinstance(
        runtime.limits,
        InMemoryEnterpriseQuotaLimitRepository,
    )


def test_memory_runtime_limit_authority_is_exact_shared_instance() -> None:
    runtime = build_enterprise_quota_runtime(
        _memory_settings()
    )

    assert runtime.limits is runtime.runtime_context._limits
    assert runtime.limits is runtime.enforcement._limits


def test_sqlite_runtime_exposes_authoritative_limit_repository(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "quota.db"

    runtime = build_enterprise_quota_runtime(
        _sqlite_settings(database_path)
    )

    assert isinstance(
        runtime.limits,
        SQLiteEnterpriseQuotaLimitRepository,
    )


def test_sqlite_runtime_limit_authority_is_exact_shared_instance(
    tmp_path: Path,
) -> None:
    runtime = build_enterprise_quota_runtime(
        _sqlite_settings(
            tmp_path / "quota.db",
        )
    )

    assert runtime.limits is runtime.runtime_context._limits
    assert runtime.limits is runtime.enforcement._limits


def test_runtime_limit_authority_is_frozen() -> None:
    runtime = build_enterprise_quota_runtime(
        _memory_settings()
    )

    with pytest.raises(FrozenInstanceError):
        runtime.limits = (  # type: ignore[misc]
            InMemoryEnterpriseQuotaLimitRepository()
        )
