from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)


def test_memory_is_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_V2_PERSISTENCE_BACKEND",
        raising=False,
    )
    monkeypatch.delenv(
        "HUMANIZE_V2_SQLITE_PATH",
        raising=False,
    )
    monkeypatch.delenv(
        "HUMANIZE_V2_DATABASE_URL",
        raising=False,
    )

    settings = V2PersistenceSettings.from_environment()

    assert settings.backend is PersistenceBackend.MEMORY
    assert settings.sqlite_path is None
    assert settings.database_url is None


def test_sqlite_requires_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_V2_PERSISTENCE_BACKEND",
        "sqlite",
    )
    monkeypatch.delenv(
        "HUMANIZE_V2_SQLITE_PATH",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_SQLITE_PATH",
    ):
        V2PersistenceSettings.from_environment()


def test_sqlite_configuration_is_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_V2_PERSISTENCE_BACKEND",
        "sqlite",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_SQLITE_PATH",
        "/tmp/humanize-v2.db",
    )

    settings = V2PersistenceSettings.from_environment()

    assert settings.backend is PersistenceBackend.SQLITE
    assert settings.sqlite_path == Path("/tmp/humanize-v2.db")


def test_external_requires_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_V2_PERSISTENCE_BACKEND",
        "external",
    )
    monkeypatch.delenv(
        "HUMANIZE_V2_DATABASE_URL",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_DATABASE_URL",
    ):
        V2PersistenceSettings.from_environment()


def test_external_configuration_is_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_V2_PERSISTENCE_BACKEND",
        "external",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_DATABASE_URL",
        "postgresql://example.invalid/db",
    )

    settings = V2PersistenceSettings.from_environment()

    assert settings.backend is PersistenceBackend.EXTERNAL
    assert settings.database_url == ("postgresql://example.invalid/db")


def test_unknown_backend_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_V2_PERSISTENCE_BACKEND",
        "unknown",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported V2 persistence backend",
    ):
        V2PersistenceSettings.from_environment()
