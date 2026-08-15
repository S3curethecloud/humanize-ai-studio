from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.v2.api import dependencies as v2_dependencies
from app.v2.config.enterprise_quota import (
    EnterpriseQuotaActivationSettings,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.services.enterprise_quota_runtime import (
    EnterpriseQuotaRuntime,
)


def _memory_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def test_activation_defaults_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_V2_ENTERPRISE_QUOTA_ENABLED",
        raising=False,
    )

    settings = (
        EnterpriseQuotaActivationSettings.from_environment()
    )

    assert settings.enabled is False


@pytest.mark.parametrize(
    "value",
    (
        "1",
        "true",
        "TRUE",
        "yes",
        "on",
    ),
)
def test_activation_accepts_true_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_V2_ENTERPRISE_QUOTA_ENABLED",
        value,
    )

    settings = (
        EnterpriseQuotaActivationSettings.from_environment()
    )

    assert settings.enabled is True


@pytest.mark.parametrize(
    "value",
    (
        "0",
        "false",
        "FALSE",
        "no",
        "off",
    ),
)
def test_activation_accepts_false_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_V2_ENTERPRISE_QUOTA_ENABLED",
        value,
    )

    settings = (
        EnterpriseQuotaActivationSettings.from_environment()
    )

    assert settings.enabled is False


def test_invalid_activation_value_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_V2_ENTERPRISE_QUOTA_ENABLED",
        "sometimes",
    )

    with pytest.raises(
        ValueError,
        match=(
            "HUMANIZE_V2_ENTERPRISE_QUOTA_ENABLED "
            "must be a boolean value"
        ),
    ):
        EnterpriseQuotaActivationSettings.from_environment()


def test_disabled_activation_does_not_build_quota_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence = _memory_settings()

    persistence_loader = MagicMock(
        return_value=persistence,
    )
    activation_loader = MagicMock(
        return_value=EnterpriseQuotaActivationSettings(
            enabled=False,
        )
    )
    runtime_factory = MagicMock()

    monkeypatch.setattr(
        v2_dependencies.V2PersistenceSettings,
        "from_environment",
        persistence_loader,
    )
    monkeypatch.setattr(
        v2_dependencies.EnterpriseQuotaActivationSettings,
        "from_environment",
        activation_loader,
    )
    monkeypatch.setattr(
        v2_dependencies,
        "build_enterprise_quota_runtime",
        runtime_factory,
    )

    services = (
        v2_dependencies.build_v2_services_from_environment()
    )

    runtime_factory.assert_not_called()

    assert services.rewrite._quota_admission is None
    assert (
        services.multi_candidate
        ._multi_candidate_quota_admission
        is None
    )
    assert (
        services.long_document
        ._long_document_quota_admission
        is None
    )


def test_enabled_activation_builds_runtime_from_same_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence = _memory_settings()

    runtime = EnterpriseQuotaRuntime(
        runtime_context=MagicMock(),
        enforcement=MagicMock(),
    )

    monkeypatch.setattr(
        v2_dependencies.V2PersistenceSettings,
        "from_environment",
        MagicMock(return_value=persistence),
    )
    monkeypatch.setattr(
        v2_dependencies.EnterpriseQuotaActivationSettings,
        "from_environment",
        MagicMock(
            return_value=EnterpriseQuotaActivationSettings(
                enabled=True,
            )
        ),
    )

    runtime_factory = MagicMock(
        return_value=runtime,
    )

    monkeypatch.setattr(
        v2_dependencies,
        "build_enterprise_quota_runtime",
        runtime_factory,
    )

    services = (
        v2_dependencies.build_v2_services_from_environment()
    )

    runtime_factory.assert_called_once_with(
        persistence,
    )

    assert services.rewrite._quota_admission is not None
    assert (
        services.multi_candidate
        ._multi_candidate_quota_admission
        is not None
    )
    assert (
        services.long_document
        ._long_document_quota_admission
        is not None
    )


def test_enabled_runtime_factory_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence = _memory_settings()

    monkeypatch.setattr(
        v2_dependencies.V2PersistenceSettings,
        "from_environment",
        MagicMock(return_value=persistence),
    )
    monkeypatch.setattr(
        v2_dependencies.EnterpriseQuotaActivationSettings,
        "from_environment",
        MagicMock(
            return_value=EnterpriseQuotaActivationSettings(
                enabled=True,
            )
        ),
    )
    monkeypatch.setattr(
        v2_dependencies,
        "build_enterprise_quota_runtime",
        MagicMock(
            side_effect=RuntimeError(
                "quota runtime construction failed"
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="quota runtime construction failed",
    ):
        v2_dependencies.build_v2_services_from_environment()


def test_persistence_backend_does_not_implicitly_activate_quota(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    persistence = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=tmp_path / "v2.db",
        database_url=None,
    )

    monkeypatch.setattr(
        v2_dependencies.V2PersistenceSettings,
        "from_environment",
        MagicMock(return_value=persistence),
    )
    monkeypatch.setattr(
        v2_dependencies.EnterpriseQuotaActivationSettings,
        "from_environment",
        MagicMock(
            return_value=EnterpriseQuotaActivationSettings(
                enabled=False,
            )
        ),
    )

    runtime_factory = MagicMock()

    monkeypatch.setattr(
        v2_dependencies,
        "build_enterprise_quota_runtime",
        runtime_factory,
    )

    services = (
        v2_dependencies.build_v2_services_from_environment()
    )

    runtime_factory.assert_not_called()
    assert services.rewrite._quota_admission is None
