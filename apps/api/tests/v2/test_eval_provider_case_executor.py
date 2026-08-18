from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.domain.models import (
    DocumentType,
    RewriteIntensity,
    RewriteRequest,
)
from app.providers.base import (
    RewriteProviderResult,
)
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderError,
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)
from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationDatasetCase,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
)
from app.v2.services.eval_provider_case_executor import (
    EvaluationCaseTargetResolutionError,
    EvaluationProviderCaseExecutor,
)


def _target(
    *,
    target_id: str = "target-1",
    enabled: bool = True,
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id="provider-1",
            display_name="Provider 1",
        ),
        model=ModelIdentity(
            provider_id="provider-1",
            model_id="model-1",
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
        enabled=enabled,
    )


def _case() -> EvaluationDatasetCase:
    return EvaluationDatasetCase(
        case_id="case-1",
        input=EvaluationCaseInput(
            text="Original text 123 on May 3.",
            document_type=(
                DocumentType.TECHNICAL_DOCUMENT
            ),
            audience="security architects",
            tone="direct",
            intensity=(
                RewriteIntensity.LIGHT_EDIT
            ),
            preserve_numbers=False,
            preserve_dates=False,
        ),
    )


@dataclass
class CapturingExecutor:
    result: RewriteProviderResult | None = None
    error: Exception | None = None
    target: ProviderModelTarget | None = None
    request: RewriteRequest | None = None
    calls: int = 0

    def execute(
        self,
        *,
        target: ProviderModelTarget,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        self.calls += 1
        self.target = target
        self.request = request

        if self.error is not None:
            raise self.error

        if self.result is None:
            raise RuntimeError(
                "test executor has no result"
            )

        return self.result


def _provider_result() -> RewriteProviderResult:
    return RewriteProviderResult(
        text="Rewritten text 123 on May 3.",
        changes=[],
        provider_name="provider-1",
        model_name="model-1",
        prompt_version="test-v1",
        latency_ms=42.5,
    )


def _service(
    *,
    executor: CapturingExecutor,
    target: ProviderModelTarget | None = None,
) -> EvaluationProviderCaseExecutor:
    catalog = InMemoryProviderCatalogRepository()

    if target is not None:
        catalog.create(target)

    return EvaluationProviderCaseExecutor(
        catalog=catalog,
        executor=executor,
    )


def test_executes_exact_catalog_target() -> None:
    target = _target()
    executor = CapturingExecutor(
        result=_provider_result()
    )
    service = _service(
        executor=executor,
        target=target,
    )

    result = service.execute(
        case=_case(),
        target_id="target-1",
    )

    assert executor.calls == 1
    assert executor.target == target
    assert result.target_id == "target-1"


def test_maps_case_input_exactly_to_rewrite_request() -> None:
    executor = CapturingExecutor(
        result=_provider_result()
    )
    service = _service(
        executor=executor,
        target=_target(),
    )

    service.execute(
        case=_case(),
        target_id="target-1",
    )

    request = executor.request

    assert request is not None
    assert request.text == "Original text 123 on May 3."
    assert (
        request.document_type
        is DocumentType.TECHNICAL_DOCUMENT
    )
    assert request.audience == "security architects"
    assert request.tone == "direct"
    assert (
        request.intensity
        is RewriteIntensity.LIGHT_EDIT
    )
    assert request.preserve_numbers is False
    assert request.preserve_dates is False


def test_success_returns_output_and_latency_evidence() -> None:
    executor = CapturingExecutor(
        result=_provider_result()
    )
    service = _service(
        executor=executor,
        target=_target(),
    )

    result = service.execute(
        case=_case(),
        target_id="target-1",
    )

    evidence = result.evidence

    assert evidence.case_id == "case-1"
    assert (
        evidence.output_text
        == "Rewritten text 123 on May 3."
    )
    assert evidence.latency_ms == 42.5
    assert evidence.provider_error is False
    assert evidence.provider_error_category is None


def test_success_does_not_invent_naturalness_score() -> None:
    executor = CapturingExecutor(
        result=_provider_result()
    )
    service = _service(
        executor=executor,
        target=_target(),
    )

    result = service.execute(
        case=_case(),
        target_id="target-1",
    )

    assert (
        result.evidence.naturalness_score
        is None
    )


@pytest.mark.parametrize(
    (
        "error",
        "category",
    ),
    [
        (
            RewriteProviderConfigurationError(
                "configuration"
            ),
            "configuration",
        ),
        (
            RewriteProviderTransportError(
                "transport"
            ),
            "transport",
        ),
        (
            RewriteProviderResponseError(
                "response"
            ),
            "response",
        ),
        (
            RewriteProviderError(
                "provider"
            ),
            "provider",
        ),
    ],
)
def test_provider_errors_become_case_evidence(
    error: RewriteProviderError,
    category: str,
) -> None:
    executor = CapturingExecutor(
        error=error
    )
    service = _service(
        executor=executor,
        target=_target(),
    )

    result = service.execute(
        case=_case(),
        target_id="target-1",
    )

    evidence = result.evidence

    assert evidence.case_id == "case-1"
    assert evidence.provider_error is True
    assert (
        evidence.provider_error_category
        == category
    )
    assert evidence.output_text is None
    assert evidence.latency_ms is None


def test_missing_target_fails_before_execution() -> None:
    executor = CapturingExecutor(
        result=_provider_result()
    )
    service = _service(
        executor=executor,
    )

    with pytest.raises(
        EvaluationCaseTargetResolutionError,
        match="does not exist",
    ):
        service.execute(
            case=_case(),
            target_id="missing-target",
        )

    assert executor.calls == 0


class BrokenCatalog:
    def create(
        self,
        target: ProviderModelTarget,
    ) -> ProviderModelTarget:
        return target

    def get(
        self,
        target_id: str,
    ) -> ProviderModelTarget | None:
        raise RuntimeError(
            "storage unavailable"
        )

    def list_targets(
        self,
        *,
        enabled_only: bool = False,
        limit: int = 1000,
    ) -> tuple[
        ProviderModelTarget,
        ...,
    ]:
        return ()


def test_catalog_failure_fails_closed() -> None:
    executor = CapturingExecutor(
        result=_provider_result()
    )

    service = EvaluationProviderCaseExecutor(
        catalog=BrokenCatalog(),
        executor=executor,
    )

    with pytest.raises(
        EvaluationCaseTargetResolutionError,
        match="lookup failed",
    ):
        service.execute(
            case=_case(),
            target_id="target-1",
        )

    assert executor.calls == 0


class WrongIdentityCatalog:
    def __init__(
        self,
        target: ProviderModelTarget,
    ) -> None:
        self._target = target

    def create(
        self,
        target: ProviderModelTarget,
    ) -> ProviderModelTarget:
        return target

    def get(
        self,
        target_id: str,
    ) -> ProviderModelTarget | None:
        return self._target

    def list_targets(
        self,
        *,
        enabled_only: bool = False,
        limit: int = 1000,
    ) -> tuple[
        ProviderModelTarget,
        ...,
    ]:
        return (self._target,)


def test_catalog_identity_mismatch_fails_closed() -> None:
    executor = CapturingExecutor(
        result=_provider_result()
    )

    service = EvaluationProviderCaseExecutor(
        catalog=WrongIdentityCatalog(
            _target(
                target_id="different-target"
            )
        ),
        executor=executor,
    )

    with pytest.raises(
        EvaluationCaseTargetResolutionError,
        match="different evaluation target identity",
    ):
        service.execute(
            case=_case(),
            target_id="requested-target",
        )

    assert executor.calls == 0


def test_non_provider_execution_failure_propagates() -> None:
    executor = CapturingExecutor(
        error=RuntimeError(
            "binding or integrity failure"
        )
    )
    service = _service(
        executor=executor,
        target=_target(),
    )

    with pytest.raises(
        RuntimeError,
        match="binding or integrity failure",
    ):
        service.execute(
            case=_case(),
            target_id="target-1",
        )


def test_disabled_target_may_be_evaluated_exactly() -> None:
    target = _target(
        enabled=False
    )
    executor = CapturingExecutor(
        result=_provider_result()
    )
    service = _service(
        executor=executor,
        target=target,
    )

    result = service.execute(
        case=_case(),
        target_id=target.target_id,
    )

    assert result.target_id == target.target_id
    assert executor.target == target
