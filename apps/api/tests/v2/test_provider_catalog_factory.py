from __future__ import annotations

from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
    SQLiteProviderCatalogRepository,
)
from app.v2.services.provider_catalog_factory import (
    ExternalProviderCatalogPersistenceUnavailableError,
    build_provider_catalog_repository,
)


def _memory_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _sqlite_settings(
    path: Path,
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=str(path),
        database_url=None,
    )


def _external_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url="postgresql://example.invalid/db",
    )


def test_memory_factory_builds_memory_repository() -> None:
    repository = build_provider_catalog_repository(
        _memory_settings()
    )

    assert isinstance(
        repository,
        InMemoryProviderCatalogRepository,
    )


def test_sqlite_factory_builds_sqlite_repository(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.db"

    repository = build_provider_catalog_repository(
        _sqlite_settings(database_path)
    )

    assert isinstance(
        repository,
        SQLiteProviderCatalogRepository,
    )
    assert repository._database_path == database_path


def test_external_factory_fails_explicitly() -> None:
    with pytest.raises(
        ExternalProviderCatalogPersistenceUnavailableError,
        match="no external provider catalog adapter",
    ):
        build_provider_catalog_repository(
            _external_settings()
        )
