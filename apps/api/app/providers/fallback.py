from __future__ import annotations

from app.domain.models import RewriteRequest
from app.providers.base import RewriteProvider, RewriteProviderResult
from app.providers.exceptions import RewriteProviderError


class FallbackRewriteProvider:
    def __init__(
        self,
        *,
        primary: RewriteProvider,
        fallback: RewriteProvider,
    ) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def provider_name(self) -> str:
        return f"{self._primary.provider_name}-with-fallback"

    def rewrite(self, request: RewriteRequest) -> RewriteProviderResult:
        try:
            return self._primary.rewrite(request)
        except RewriteProviderError:
            return self._fallback.rewrite(request)
