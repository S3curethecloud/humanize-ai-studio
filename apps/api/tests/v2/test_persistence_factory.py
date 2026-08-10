from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.factory import (
    ExternalPersistenceUnavailableError,
    build_unit_of_work,
)
from app.v2.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)


def test_sqlite_factory_builds_unit_of_work(
    tmp_path: Path,
) -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=tmp_path / "v2.db",
        database_url=None,
    )

    unit_of_work = build_unit_of_work(settings)

    assert isinstance(
        unit_of_work,
        SQLiteUnitOfWork,
    )


def test_external_factory_fails_closed() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url=("postgresql://example.invalid/db"),
    )

    with pytest.raises(
        ExternalPersistenceUnavailableError,
        match="no production database adapter",
    ):
        build_unit_of_work(settings)


def test_memory_factory_is_not_production_uow() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )

    with pytest.raises(
        ExternalPersistenceUnavailableError,
        match="does not provide",
    ):
        build_unit_of_work(settings)
