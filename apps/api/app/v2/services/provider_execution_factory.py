from __future__ import annotations

from app.core.settings import Settings
from app.providers.base import RewriteProvider
from app.providers.cloudflare import (
    CloudflareWorkersAIProvider,
)
from app.providers.deterministic import (
    DeterministicRewriteProvider,
)
from app.providers.openai_responses import (
    OpenAIResponsesProvider,
)
from app.v2.domain.provider_routing import (
    ProviderModelTarget,
)
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)
from app.v2.services.provider_execution_adapter import (
    BoundRewriteProviderExecutionAdapter,
)

DETERMINISTIC_PROVIDER_ID = "deterministic"
DETERMINISTIC_MODEL_ID = "rules-v1"
CLOUDFLARE_PROVIDER_ID = "cloudflare-workers-ai"
OPENAI_PROVIDER_ID = "openai"


class ProviderExecutionCompositionError(RuntimeError):
    pass


class UnsupportedProviderTargetError(
    ProviderExecutionCompositionError
):
    pass


class ProviderTargetConfigurationError(
    ProviderExecutionCompositionError
):
    pass


def build_provider_execution_adapter(
    *,
    settings: Settings,
    catalog: ProviderCatalogRepository,
) -> BoundRewriteProviderExecutionAdapter:
    return BoundRewriteProviderExecutionAdapter(
        bindings=build_provider_execution_bindings(
            settings=settings,
            catalog=catalog,
        )
    )


def build_provider_execution_bindings(
    *,
    settings: Settings,
    catalog: ProviderCatalogRepository,
) -> dict[str, RewriteProvider]:
    try:
        targets = catalog.list_targets(
            enabled_only=False,
            limit=10_000,
        )
    except Exception as exc:
        raise ProviderExecutionCompositionError(
            "provider execution catalog listing failed"
        ) from exc

    return {
        target.target_id: _build_target_provider(
            settings=settings,
            target=target,
        )
        for target in targets
    }


def _build_target_provider(
    *,
    settings: Settings,
    target: ProviderModelTarget,
) -> RewriteProvider:
    provider_id = target.provider.provider_id

    if provider_id == DETERMINISTIC_PROVIDER_ID:
        return _build_deterministic_provider(
            target
        )

    if provider_id == CLOUDFLARE_PROVIDER_ID:
        return _build_cloudflare_provider(
            settings=settings,
            target=target,
        )

    if provider_id == OPENAI_PROVIDER_ID:
        return _build_openai_provider(
            settings=settings,
            target=target,
        )

    raise UnsupportedProviderTargetError(
        "unsupported provider catalog target provider: "
        f"{provider_id}"
    )


def _build_deterministic_provider(
    target: ProviderModelTarget,
) -> RewriteProvider:
    if target.model.model_id != DETERMINISTIC_MODEL_ID:
        raise ProviderTargetConfigurationError(
            "deterministic provider target requires model "
            f"{DETERMINISTIC_MODEL_ID!r}: "
            f"{target.target_id}"
        )

    return DeterministicRewriteProvider()


def _build_cloudflare_provider(
    *,
    settings: Settings,
    target: ProviderModelTarget,
) -> RewriteProvider:
    if settings.cloudflare_account_id is None:
        raise ProviderTargetConfigurationError(
            "Cloudflare provider target requires "
            "CLOUDFLARE_ACCOUNT_ID"
        )

    if settings.cloudflare_api_token is None:
        raise ProviderTargetConfigurationError(
            "Cloudflare provider target requires "
            "CLOUDFLARE_API_TOKEN"
        )

    if not target.model.model_id.strip():
        raise ProviderTargetConfigurationError(
            "Cloudflare provider target requires "
            "a non-empty model identity"
        )

    return CloudflareWorkersAIProvider(
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_api_token,
        model_name=target.model.model_id,
        timeout_seconds=(
            settings.cloudflare_timeout_seconds
        ),
    )

def _build_openai_provider(
    *,
    settings: Settings,
    target: ProviderModelTarget,
) -> RewriteProvider:
    if settings.openai_api_key is None:
        raise ProviderTargetConfigurationError(
            "OpenAI provider target requires OPENAI_API_KEY"
        )

    if not target.model.model_id.strip():
        raise ProviderTargetConfigurationError(
            "OpenAI provider target requires "
            "a non-empty model identity"
        )

    return OpenAIResponsesProvider(
        api_key=settings.openai_api_key,
        model_name=target.model.model_id,
        timeout_seconds=settings.openai_timeout_seconds,
    )
