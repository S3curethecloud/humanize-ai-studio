from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from app.domain.models import RewriteRequest
from app.providers.base import (
    RewriteProvider,
    RewriteProviderResult,
)
from app.v2.domain.provider_routing import (
    ProviderModelTarget,
)


class ProviderExecutionBindingError(RuntimeError):
    pass


class ProviderExecutionIntegrityError(RuntimeError):
    pass


class ProviderTargetExecutionAdapter(Protocol):
    def execute(
        self,
        *,
        target: ProviderModelTarget,
        request: RewriteRequest,
    ) -> RewriteProviderResult: ...


class BoundRewriteProviderExecutionAdapter:
    def __init__(
        self,
        *,
        bindings: Mapping[
            str,
            RewriteProvider,
        ],
    ) -> None:
        self._bindings = dict(bindings)

    def execute(
        self,
        *,
        target: ProviderModelTarget,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        provider = self._resolve_binding(target)

        result = provider.rewrite(request)

        self._require_result_integrity(
            target=target,
            result=result,
        )

        return result

    def _resolve_binding(
        self,
        target: ProviderModelTarget,
    ) -> RewriteProvider:
        provider = self._bindings.get(
            target.target_id
        )

        if provider is None:
            raise ProviderExecutionBindingError(
                "no rewrite provider is bound to routing target: "
                f"{target.target_id}"
            )

        if (
            provider.provider_name
            != target.provider.provider_id
        ):
            raise ProviderExecutionBindingError(
                "bound rewrite provider identity does not match "
                "routing target provider identity"
            )

        return provider

    @staticmethod
    def _require_result_integrity(
        *,
        target: ProviderModelTarget,
        result: RewriteProviderResult,
    ) -> None:
        if result.provider_name != target.provider.provider_id:
            raise ProviderExecutionIntegrityError(
                "provider execution result provider identity "
                "does not match routing target"
            )

        if result.model_name != target.model.model_id:
            raise ProviderExecutionIntegrityError(
                "provider execution result model identity "
                "does not match routing target"
            )

        if result.fallback_used:
            raise ProviderExecutionIntegrityError(
                "provider execution adapter forbids internal "
                "provider fallback"
            )

        if (
            result.primary_provider_name
            and result.primary_provider_name
            != target.provider.provider_id
        ):
            raise ProviderExecutionIntegrityError(
                "provider execution result primary provider "
                "identity does not match routing target"
            )
