from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from app.domain.models import RewriteChange, RewriteRequest


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class RewriteProviderResult:
    text: str
    changes: list[RewriteChange]
    provider_name: str
    model_name: str
    prompt_version: str
    latency_ms: float = 0.0
    primary_provider_name: str = ""
    fallback_used: bool = False
    provider_error_category: str | None = None
    usage: ProviderUsage = field(default_factory=ProviderUsage)


@runtime_checkable
class RewriteProvider(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the stable provider identifier."""

    def rewrite(self, request: RewriteRequest) -> RewriteProviderResult:
        """Produce a candidate rewrite for downstream verification."""
