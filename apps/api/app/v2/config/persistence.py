from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class PersistenceBackend(StrEnum):
    MEMORY = "memory"
    SQLITE = "sqlite"
    EXTERNAL = "external"


@dataclass(frozen=True)
class V2PersistenceSettings:
    backend: PersistenceBackend
    sqlite_path: Path | None
    database_url: str | None

    @classmethod
    def from_environment(
        cls,
    ) -> V2PersistenceSettings:
        raw_backend = os.getenv(
            "HUMANIZE_V2_PERSISTENCE_BACKEND",
            PersistenceBackend.MEMORY.value,
        ).strip()

        try:
            backend = PersistenceBackend(raw_backend)
        except ValueError as exc:
            supported = ", ".join(item.value for item in PersistenceBackend)
            raise ValueError(
                "Unsupported V2 persistence "
                f"backend '{raw_backend}'. "
                f"Supported backends: {supported}."
            ) from exc

        sqlite_path_raw = _optional_value("HUMANIZE_V2_SQLITE_PATH")
        database_url = _optional_value("HUMANIZE_V2_DATABASE_URL")

        settings = cls(
            backend=backend,
            sqlite_path=(Path(sqlite_path_raw) if sqlite_path_raw else None),
            database_url=database_url,
        )

        settings.validate()
        return settings

    def validate(self) -> None:
        if self.backend is PersistenceBackend.SQLITE and self.sqlite_path is None:
            raise ValueError(
                "HUMANIZE_V2_SQLITE_PATH is required when the V2 persistence backend is sqlite."
            )

        if self.backend is PersistenceBackend.EXTERNAL and not self.database_url:
            raise ValueError(
                "HUMANIZE_V2_DATABASE_URL is required when the V2 persistence backend is external."
            )


def _optional_value(
    name: str,
) -> str | None:
    value = os.getenv(name)

    if value is None:
        return None

    stripped = value.strip()
    return stripped or None
