from __future__ import annotations

import logging
from dataclasses import replace
from time import perf_counter

from app.domain.models import RewriteRequest
from app.providers.base import RewriteProvider, RewriteProviderResult
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderError,
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)

logger = logging.getLogger(__name__)


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
        started_at = perf_counter()

        try:
            return self._primary.rewrite(request)
        except RewriteProviderError as exc:
            logger.warning(
                "rewrite_provider_fallback",
                extra={
                    "primary_provider": self._primary.provider_name,
                    "fallback_provider": self._fallback.provider_name,
                    "provider_error_category": _classify_provider_error(exc),
                    "provider_error_detail": str(exc),
                },
            )

            fallback_result = self._fallback.rewrite(request)

            return replace(
                fallback_result,
                latency_ms=round((perf_counter() - started_at) * 1000, 3),
                primary_provider_name=self._primary.provider_name,
                fallback_used=True,
                provider_error_category=_classify_provider_error(exc),
            )


def _classify_provider_error(error: RewriteProviderError) -> str:
    if isinstance(error, RewriteProviderConfigurationError):
        return "configuration"

    if isinstance(error, RewriteProviderTransportError):
        return "transport"

    if isinstance(error, RewriteProviderResponseError):
        return "response"

    return "provider"
