from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.settings import ProviderName, Settings
from app.domain.models import RewriteRequest
from app.providers.base import RewriteProviderResult
from app.providers.cloudflare import (
    CloudflareWorkersAIProvider,
)
from app.providers.deterministic import (
    DeterministicRewriteProvider,
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
    ProviderCatalogRepository,
)
from app.v2.services.provider_execution_adapter import (
    BoundRewriteProviderExecutionAdapter,
)
from app.v2.services.provider_execution_factory import (
    CLOUDFLARE_PROVIDER_ID,
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
    ProviderExecutionCompositionError,
    ProviderTargetConfigurationError,
    UnsupportedProviderTargetError,
    build_provider_execution_adapter,
    build_provider_execution_bindings,
)


def _settings(
    *,
    rewrite_provider: ProviderName = (
        ProviderName.DETERMINISTIC
    ),
    cloudflare_account_id: str | None = "account",
    cloudflare_api_token: str | None = "token",
    cloudflare_fallback_enabled: bool = True,
) -> Settings:
    return Settings(
        rewrite_provider=rewrite_provider,
        cloudflare_account_id=cloudflare_account_id,
        cloudflare_api_token=cloudflare_api_token,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=17.0,
        cloudflare_fallback_enabled=(
            cloudflare_fallback_enabled
        ),
    )


def _target(
    *,
    target_id: str,
    provider_id: str,
    model_id: str,
    enabled: bool = True,
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=provider_id,
            display_name=provider_id,
        ),
        model=ModelIdentity(
            provider_id=provider_id,
            model_id=model_id,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
        enabled=enabled,
    )


def _catalog(
    *targets: ProviderModelTarget,
) -> InMemoryProviderCatalogRepository:
    catalog = InMemoryProviderCatalogRepository()

    for target in targets:
        catalog.create(target)

    return catalog


def test_empty_catalog_builds_empty_bindings() -> None:
    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(),
    )

    assert bindings == {}


def test_deterministic_target_builds_exact_provider() -> None:
    target = _target(
        target_id="deterministic-primary",
        provider_id=DETERMINISTIC_PROVIDER_ID,
        model_id=DETERMINISTIC_MODEL_ID,
    )

    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(target),
    )

    provider = bindings[target.target_id]

    assert isinstance(
        provider,
        DeterministicRewriteProvider,
    )
    assert (
        provider.provider_name
        == DETERMINISTIC_PROVIDER_ID
    )


def test_deterministic_target_rejects_wrong_model() -> None:
    target = _target(
        target_id="deterministic-primary",
        provider_id=DETERMINISTIC_PROVIDER_ID,
        model_id="rules-v2",
    )

    with pytest.raises(
        ProviderTargetConfigurationError,
        match="rules-v1",
    ):
        build_provider_execution_bindings(
            settings=_settings(),
            catalog=_catalog(target),
        )


def test_cloudflare_target_uses_catalog_model() -> None:
    target = _target(
        target_id="cloudflare-primary",
        provider_id=CLOUDFLARE_PROVIDER_ID,
        model_id="@cf/catalog/model",
    )

    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(target),
    )

    provider = bindings[target.target_id]

    assert isinstance(
        provider,
        CloudflareWorkersAIProvider,
    )
    assert provider.provider_name == (
        CLOUDFLARE_PROVIDER_ID
    )
    assert provider._model_name == "@cf/catalog/model"
    assert provider._timeout_seconds == 17.0


def test_cloudflare_target_does_not_use_legacy_model_setting() -> None:
    target = _target(
        target_id="cloudflare-primary",
        provider_id=CLOUDFLARE_PROVIDER_ID,
        model_id="@cf/catalog/model",
    )

    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(target),
    )

    provider = bindings[target.target_id]

    assert isinstance(
        provider,
        CloudflareWorkersAIProvider,
    )
    assert provider._model_name != "@cf/legacy/model"


def test_cloudflare_target_requires_account_id() -> None:
    target = _target(
        target_id="cloudflare-primary",
        provider_id=CLOUDFLARE_PROVIDER_ID,
        model_id="@cf/catalog/model",
    )

    with pytest.raises(
        ProviderTargetConfigurationError,
        match="CLOUDFLARE_ACCOUNT_ID",
    ):
        build_provider_execution_bindings(
            settings=_settings(
                cloudflare_account_id=None,
            ),
            catalog=_catalog(target),
        )


def test_cloudflare_target_requires_api_token() -> None:
    target = _target(
        target_id="cloudflare-primary",
        provider_id=CLOUDFLARE_PROVIDER_ID,
        model_id="@cf/catalog/model",
    )

    with pytest.raises(
        ProviderTargetConfigurationError,
        match="CLOUDFLARE_API_TOKEN",
    ):
        build_provider_execution_bindings(
            settings=_settings(
                cloudflare_api_token=None,
            ),
            catalog=_catalog(target),
        )


def test_multiple_provider_targets_are_composed_together() -> None:
    deterministic = _target(
        target_id="deterministic",
        provider_id=DETERMINISTIC_PROVIDER_ID,
        model_id=DETERMINISTIC_MODEL_ID,
    )
    cloudflare = _target(
        target_id="cloudflare",
        provider_id=CLOUDFLARE_PROVIDER_ID,
        model_id="@cf/catalog/model",
    )

    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(
            deterministic,
            cloudflare,
        ),
    )

    assert set(bindings) == {
        "deterministic",
        "cloudflare",
    }
    assert isinstance(
        bindings["deterministic"],
        DeterministicRewriteProvider,
    )
    assert isinstance(
        bindings["cloudflare"],
        CloudflareWorkersAIProvider,
    )


def test_legacy_rewrite_provider_does_not_choose_v2_bindings() -> None:
    deterministic = _target(
        target_id="deterministic",
        provider_id=DETERMINISTIC_PROVIDER_ID,
        model_id=DETERMINISTIC_MODEL_ID,
    )
    cloudflare = _target(
        target_id="cloudflare",
        provider_id=CLOUDFLARE_PROVIDER_ID,
        model_id="@cf/catalog/model",
    )

    bindings = build_provider_execution_bindings(
        settings=_settings(
            rewrite_provider=ProviderName.DETERMINISTIC,
        ),
        catalog=_catalog(
            deterministic,
            cloudflare,
        ),
    )

    assert set(bindings) == {
        "deterministic",
        "cloudflare",
    }


def test_legacy_fallback_setting_does_not_wrap_v2_provider() -> None:
    target = _target(
        target_id="cloudflare",
        provider_id=CLOUDFLARE_PROVIDER_ID,
        model_id="@cf/catalog/model",
    )

    bindings = build_provider_execution_bindings(
        settings=_settings(
            cloudflare_fallback_enabled=True,
        ),
        catalog=_catalog(target),
    )

    provider = bindings[target.target_id]

    assert isinstance(
        provider,
        CloudflareWorkersAIProvider,
    )


def test_disabled_target_is_still_composed() -> None:
    target = _target(
        target_id="disabled",
        provider_id=DETERMINISTIC_PROVIDER_ID,
        model_id=DETERMINISTIC_MODEL_ID,
        enabled=False,
    )

    bindings = build_provider_execution_bindings(
        settings=_settings(),
        catalog=_catalog(target),
    )

    assert target.target_id in bindings


def test_unsupported_provider_fails_explicitly() -> None:
    target = _target(
        target_id="unsupported",
        provider_id="unsupported-provider",
        model_id="model",
    )

    with pytest.raises(
        UnsupportedProviderTargetError,
        match="unsupported-provider",
    ):
        build_provider_execution_bindings(
            settings=_settings(),
            catalog=_catalog(target),
        )


def test_catalog_listing_failure_is_wrapped() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.list_targets.side_effect = RuntimeError(
        "database unavailable"
    )

    with pytest.raises(
        ProviderExecutionCompositionError,
        match="catalog listing failed",
    ) as exc_info:
        build_provider_execution_bindings(
            settings=_settings(),
            catalog=catalog,
        )

    assert isinstance(
        exc_info.value.__cause__,
        RuntimeError,
    )


def test_factory_requests_full_catalog_without_enabled_filter() -> None:
    catalog = MagicMock(
        spec=ProviderCatalogRepository,
    )
    catalog.list_targets.return_value = ()

    build_provider_execution_bindings(
        settings=_settings(),
        catalog=catalog,
    )

    catalog.list_targets.assert_called_once_with(
        enabled_only=False,
        limit=10_000,
    )


def test_adapter_factory_returns_governed_adapter() -> None:
    adapter = build_provider_execution_adapter(
        settings=_settings(),
        catalog=_catalog(),
    )

    assert isinstance(
        adapter,
        BoundRewriteProviderExecutionAdapter,
    )


def test_deterministic_binding_executes_with_exact_identity() -> None:
    target = _target(
        target_id="deterministic",
        provider_id=DETERMINISTIC_PROVIDER_ID,
        model_id=DETERMINISTIC_MODEL_ID,
    )

    adapter = build_provider_execution_adapter(
        settings=_settings(),
        catalog=_catalog(target),
    )

    result = adapter.execute(
        target=target,
        request=RewriteRequest(
            text="Furthermore, this is direct.",
        ),
    )

    assert isinstance(
        result,
        RewriteProviderResult,
    )
    assert (
        result.provider_name
        == DETERMINISTIC_PROVIDER_ID
    )
    assert result.model_name == DETERMINISTIC_MODEL_ID
    assert result.fallback_used is False
