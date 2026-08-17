from __future__ import annotations

import pytest

from app.core.settings import (
    ProviderName,
    Settings,
)
from app.providers.openai_responses import (
    OpenAIResponsesProvider,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
)
from app.v2.services.provider_execution_factory import (
    OPENAI_PROVIDER_ID,
    ProviderTargetConfigurationError,
    build_provider_execution_bindings,
)


def _settings(
    *,
    openai_api_key: str | None = "openai-secret",
    openai_timeout_seconds: float = 23.0,
) -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
        openai_api_key=openai_api_key,
        openai_timeout_seconds=openai_timeout_seconds,
    )


def _openai_target(
    *,
    model_id: str = "catalog-openai-model",
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id="openai-primary",
        provider=ProviderIdentity(
            provider_id=OPENAI_PROVIDER_ID,
            display_name="OpenAI",
        ),
        model=ModelIdentity(
            provider_id=OPENAI_PROVIDER_ID,
            model_id=model_id,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
        enabled=True,
    )


def _catalog(
    target: ProviderModelTarget,
) -> InMemoryProviderCatalogRepository:
    catalog = InMemoryProviderCatalogRepository()
    catalog.create(target)
    return catalog


def test_settings_defaults_preserve_existing_constructor_compatibility() -> None:
    settings = Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )

    assert settings.openai_api_key is None
    assert settings.openai_timeout_seconds == 30.0


def test_settings_reads_openai_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_REWRITE_PROVIDER",
        "deterministic",
    )
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "  environment-secret  ",
    )
    monkeypatch.setenv(
        "OPENAI_TIMEOUT_SECONDS",
        "41.5",
    )

    settings = Settings.from_environment()

    assert settings.openai_api_key == "environment-secret"
    assert settings.openai_timeout_seconds == 41.5


def test_settings_openai_timeout_defaults_to_30_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_REWRITE_PROVIDER",
        "deterministic",
    )
    monkeypatch.delenv(
        "OPENAI_TIMEOUT_SECONDS",
        raising=False,
    )

    settings = Settings.from_environment()

    assert settings.openai_timeout_seconds == 30.0


@pytest.mark.parametrize(
    "raw_timeout",
    [
        "0",
        "-1",
        "not-a-number",
    ],
)
def test_invalid_openai_timeout_fails_configuration(
    monkeypatch: pytest.MonkeyPatch,
    raw_timeout: str,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_REWRITE_PROVIDER",
        "deterministic",
    )
    monkeypatch.setenv(
        "OPENAI_TIMEOUT_SECONDS",
        raw_timeout,
    )

    with pytest.raises(
        ValueError,
        match="OPENAI_TIMEOUT_SECONDS",
    ):
        Settings.from_environment()


def test_openai_catalog_target_builds_openai_provider() -> None:
    target = _openai_target()

    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(target),
    )

    provider = bindings[target.target_id]

    assert isinstance(
        provider,
        OpenAIResponsesProvider,
    )
    assert provider.provider_name == OPENAI_PROVIDER_ID


def test_openai_binding_uses_catalog_model_identity() -> None:
    target = _openai_target(
        model_id="catalog-model-exact"
    )

    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(target),
    )

    provider = bindings[target.target_id]

    assert isinstance(
        provider,
        OpenAIResponsesProvider,
    )
    assert provider._model_name == "catalog-model-exact"


def test_openai_binding_uses_openai_timeout_setting() -> None:
    target = _openai_target()

    bindings = build_provider_execution_bindings(
        settings=_settings(
            openai_timeout_seconds=12.5
        ),
        catalog=_catalog(target),
    )

    provider = bindings[target.target_id]

    assert isinstance(
        provider,
        OpenAIResponsesProvider,
    )
    assert provider._timeout_seconds == 12.5


def test_openai_target_requires_api_key() -> None:
    target = _openai_target()

    with pytest.raises(
        ProviderTargetConfigurationError,
        match="OPENAI_API_KEY",
    ):
        build_provider_execution_bindings(
            settings=_settings(
                openai_api_key=None
            ),
            catalog=_catalog(target),
        )


def test_openai_configuration_does_not_change_legacy_provider_selection() -> None:
    settings = _settings()

    assert settings.rewrite_provider is ProviderName.DETERMINISTIC
    assert "openai" not in {
        provider.value
        for provider in ProviderName
    }


def test_openai_target_is_not_wrapped_with_legacy_fallback() -> None:
    target = _openai_target()

    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(target),
    )

    provider = bindings[target.target_id]

    assert type(provider) is OpenAIResponsesProvider
