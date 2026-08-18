from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
    ProviderCatalogRepository,
    SQLiteProviderCatalogRepository,
)


class ExternalProviderCatalogPersistenceUnavailableError(
    RuntimeError,
):
    pass


def build_provider_catalog_repository(
    settings: V2PersistenceSettings,
) -> ProviderCatalogRepository:
    settings.validate()

    if settings.backend is PersistenceBackend.MEMORY:
        return InMemoryProviderCatalogRepository()

    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite provider catalog persistence "
                "requires a database path."
            )

        return SQLiteProviderCatalogRepository(
            database_path=settings.sqlite_path,
        )

    if settings.backend is PersistenceBackend.EXTERNAL:
        raise (
            ExternalProviderCatalogPersistenceUnavailableError(
                "External provider catalog persistence is "
                "configured but no external provider catalog "
                "adapter has been installed."
            )
        )

    raise RuntimeError(
        "Unsupported provider catalog persistence backend."
    )
