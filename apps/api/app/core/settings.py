from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


class ProviderName(StrEnum):
    DETERMINISTIC = "deterministic"
    CLOUDFLARE = "cloudflare"


@dataclass(frozen=True)
class Settings:
    rewrite_provider: ProviderName
    cloudflare_account_id: str | None
    cloudflare_api_token: str | None
    cloudflare_model: str
    cloudflare_timeout_seconds: float
    cloudflare_fallback_enabled: bool
    openai_api_key: str | None = None
    openai_timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls) -> Settings:
        raw_provider = os.getenv(
            "HUMANIZE_REWRITE_PROVIDER",
            ProviderName.DETERMINISTIC.value,
        ).strip()

        try:
            rewrite_provider = ProviderName(raw_provider)
        except ValueError as exc:
            supported = ", ".join(provider.value for provider in ProviderName)
            raise ValueError(
                f"Unsupported rewrite provider '{raw_provider}'. Supported providers: {supported}."
            ) from exc

        settings = cls(
            rewrite_provider=rewrite_provider,
            cloudflare_account_id=_optional_environment_value("CLOUDFLARE_ACCOUNT_ID"),
            cloudflare_api_token=_optional_environment_value("CLOUDFLARE_API_TOKEN"),
            cloudflare_model=os.getenv(
                "CLOUDFLARE_AI_MODEL",
                "@cf/openai/gpt-oss-20b",
            ).strip(),
            cloudflare_timeout_seconds=_positive_float_environment_value(
                "CLOUDFLARE_AI_TIMEOUT_SECONDS",
                default=30.0,
            ),
            cloudflare_fallback_enabled=_boolean_environment_value(
                "CLOUDFLARE_AI_FALLBACK_ENABLED",
                default=True,
            ),
            openai_api_key=_optional_environment_value(
                "OPENAI_API_KEY"
            ),
            openai_timeout_seconds=_positive_float_environment_value(
                "OPENAI_TIMEOUT_SECONDS",
                default=30.0,
            ),
        )

        settings.validate()
        return settings

    def validate(self) -> None:
        if self.rewrite_provider is not ProviderName.CLOUDFLARE:
            return

        missing: list[str] = []

        if not self.cloudflare_account_id:
            missing.append("CLOUDFLARE_ACCOUNT_ID")

        if not self.cloudflare_api_token:
            missing.append("CLOUDFLARE_API_TOKEN")

        if not self.cloudflare_model:
            missing.append("CLOUDFLARE_AI_MODEL")

        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Cloudflare provider configuration is incomplete. Missing: {joined}.")


def _optional_environment_value(name: str) -> str | None:
    value = os.getenv(name)

    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def _positive_float_environment_value(name: str, *, default: float) -> float:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return value


def _boolean_environment_value(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"{name} must be one of: true, false, 1, 0, yes, no, on, off.")
