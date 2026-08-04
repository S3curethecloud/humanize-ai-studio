from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.domain.models import RewriteChange, RewriteRequest


@dataclass(frozen=True)
class RewriteProviderResult:
    text: str
    changes: list[RewriteChange]
    provider_name: str
    model_name: str
    prompt_version: str


@runtime_checkable
class RewriteProvider(Protocol):
    @property
    def provider_name(self) -> str:
        """Return the stable provider identifier."""

    def rewrite(self, request: RewriteRequest) -> RewriteProviderResult:
        """Produce a candidate rewrite for downstream verification."""
