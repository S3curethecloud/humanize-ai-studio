import pytest

from app.core.settings import ProviderName, Settings


def test_settings_default_to_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HUMANIZE_REWRITE_PROVIDER", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)

    settings = Settings.from_environment()

    assert settings.rewrite_provider is ProviderName.DETERMINISTIC
    assert settings.cloudflare_model == "@cf/openai/gpt-oss-20b"
    assert settings.cloudflare_fallback_enabled is True


def test_cloudflare_configuration_requires_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HUMANIZE_REWRITE_PROVIDER", "cloudflare")
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)

    with pytest.raises(
        ValueError,
        match="CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN",
    ):
        Settings.from_environment()


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUMANIZE_REWRITE_PROVIDER", "unknown-provider")

    with pytest.raises(ValueError, match="Unsupported rewrite provider"):
        Settings.from_environment()
