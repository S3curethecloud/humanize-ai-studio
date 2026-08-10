from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)
from app.v2.repositories.uow_interfaces import (
    UnitOfWork,
)


class ExternalPersistenceUnavailableError(RuntimeError):
    pass


def build_unit_of_work(
    settings: V2PersistenceSettings,
) -> UnitOfWork:
    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError("SQLite persistence requires a database path.")

        return SQLiteUnitOfWork(settings.sqlite_path)

    if settings.backend is PersistenceBackend.EXTERNAL:
        raise ExternalPersistenceUnavailableError(
            "External V2 persistence is configured "
            "but no production database adapter "
            "has been installed."
        )

    raise ExternalPersistenceUnavailableError(
        "The in-memory persistence backend does "
        "not provide a transactional production "
        "unit of work."
    )
