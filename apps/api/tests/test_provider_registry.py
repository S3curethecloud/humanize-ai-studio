from app.core.settings import ProviderName, Settings
from app.providers.deterministic import DeterministicRewriteProvider
from app.providers.fallback import FallbackRewriteProvider
from app.providers.registry import build_rewrite_provider


def test_registry_builds_deterministic_provider() -> None:
    settings = Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/openai/gpt-oss-20b",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )

    provider = build_rewrite_provider(settings)

    assert isinstance(provider, DeterministicRewriteProvider)
    assert provider.provider_name == "deterministic"


def test_registry_wraps_cloudflare_with_fallback() -> None:
    settings = Settings(
        rewrite_provider=ProviderName.CLOUDFLARE,
        cloudflare_account_id="account-id",
        cloudflare_api_token="api-token",
        cloudflare_model="@cf/openai/gpt-oss-20b",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=True,
    )

    provider = build_rewrite_provider(settings)

    assert isinstance(provider, FallbackRewriteProvider)
    assert provider.provider_name == "cloudflare-workers-ai-with-fallback"
