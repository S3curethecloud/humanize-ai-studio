from __future__ import annotations

from app.core.settings import ProviderName, Settings
from app.providers.base import RewriteProvider
from app.providers.cloudflare import CloudflareWorkersAIProvider
from app.providers.deterministic import DeterministicRewriteProvider
from app.providers.fallback import FallbackRewriteProvider


def build_rewrite_provider(settings: Settings) -> RewriteProvider:
    deterministic = DeterministicRewriteProvider()

    if settings.rewrite_provider is ProviderName.DETERMINISTIC:
        return deterministic

    if settings.rewrite_provider is ProviderName.CLOUDFLARE:
        if settings.cloudflare_account_id is None:
            raise ValueError("CLOUDFLARE_ACCOUNT_ID is required.")

        if settings.cloudflare_api_token is None:
            raise ValueError("CLOUDFLARE_API_TOKEN is required.")

        cloudflare = CloudflareWorkersAIProvider(
            account_id=settings.cloudflare_account_id,
            api_token=settings.cloudflare_api_token,
            model_name=settings.cloudflare_model,
            timeout_seconds=settings.cloudflare_timeout_seconds,
        )

        if settings.cloudflare_fallback_enabled:
            return FallbackRewriteProvider(
                primary=cloudflare,
                fallback=deterministic,
            )

        return cloudflare

    raise ValueError(f"Provider registry does not support {settings.rewrite_provider!r}.")
