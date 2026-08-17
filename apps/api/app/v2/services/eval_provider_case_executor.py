from __future__ import annotations

from app.domain.models import RewriteRequest
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderError,
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)
from app.v2.domain.eval_dataset import (
    EvaluationDatasetCase,
)
from app.v2.domain.eval_execution import (
    EvaluationCaseExecutionResult,
)
from app.v2.domain.eval_metrics import (
    EvaluationCaseExecutionEvidence,
)
from app.v2.domain.provider_routing import (
    ProviderModelTarget,
    RoutingFailureCategory,
)
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)
from app.v2.services.provider_execution_adapter import (
    ProviderTargetExecutionAdapter,
)


class EvaluationCaseTargetResolutionError(
    RuntimeError
):
    pass


class EvaluationProviderCaseExecutor:
    def __init__(
        self,
        *,
        catalog: ProviderCatalogRepository,
        executor: ProviderTargetExecutionAdapter,
    ) -> None:
        self._catalog = catalog
        self._executor = executor

    def execute(
        self,
        *,
        case: EvaluationDatasetCase,
        target_id: str,
    ) -> EvaluationCaseExecutionResult:
        target = self._resolve_target(
            target_id=target_id
        )

        request = _build_rewrite_request(
            case=case
        )

        try:
            provider_result = self._executor.execute(
                target=target,
                request=request,
            )
        except RewriteProviderError as exc:
            return EvaluationCaseExecutionResult(
                target_id=target_id,
                evidence=EvaluationCaseExecutionEvidence(
                    case_id=case.case_id,
                    provider_error=True,
                    provider_error_category=(
                        _provider_error_category(
                            exc
                        ).value
                    ),
                ),
            )

        return EvaluationCaseExecutionResult(
            target_id=target_id,
            evidence=EvaluationCaseExecutionEvidence(
                case_id=case.case_id,
                output_text=provider_result.text,
                latency_ms=provider_result.latency_ms,
                provider_error=False,
                naturalness_score=None,
            ),
        )

    def _resolve_target(
        self,
        *,
        target_id: str,
    ) -> ProviderModelTarget:
        try:
            target = self._catalog.get(
                target_id
            )
        except Exception as exc:
            raise EvaluationCaseTargetResolutionError(
                "evaluation provider target lookup failed"
            ) from exc

        if target is None:
            raise EvaluationCaseTargetResolutionError(
                "evaluation provider target does not exist: "
                f"{target_id}"
            )

        if target.target_id != target_id:
            raise EvaluationCaseTargetResolutionError(
                "provider catalog returned a different "
                "evaluation target identity"
            )

        return target


def _build_rewrite_request(
    *,
    case: EvaluationDatasetCase,
) -> RewriteRequest:
    source = case.input

    return RewriteRequest(
        text=source.text,
        document_type=source.document_type,
        audience=source.audience,
        tone=source.tone,
        intensity=source.intensity,
        preserve_numbers=source.preserve_numbers,
        preserve_dates=source.preserve_dates,
    )


def _provider_error_category(
    error: RewriteProviderError,
) -> RoutingFailureCategory:
    if isinstance(
        error,
        RewriteProviderConfigurationError,
    ):
        return RoutingFailureCategory.CONFIGURATION

    if isinstance(
        error,
        RewriteProviderTransportError,
    ):
        return RoutingFailureCategory.TRANSPORT

    if isinstance(
        error,
        RewriteProviderResponseError,
    ):
        return RoutingFailureCategory.RESPONSE

    return RoutingFailureCategory.PROVIDER
