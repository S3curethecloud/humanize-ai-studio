from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.domain.models import (
    DocumentType,
    RewriteIntensity,
    RewriteRequest,
)
from app.providers.base import (
    ProviderUsage,
    RewriteProvider,
    RewriteProviderResult,
)
from app.providers.exceptions import (
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.services.provider_execution_adapter import (
    BoundRewriteProviderExecutionAdapter,
    ProviderExecutionBindingError,
    ProviderExecutionIntegrityError,
)


def _target(
    *,
    target_id: str = "cloudflare-primary",
    provider_id: str = "cloudflare-workers-ai",
    model_id: str = "@cf/example/model",
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=target_id,
        provider=ProviderIdentity(
            provider_id=provider_id,
            display_name="Provider",
        ),
        model=ModelIdentity(
            provider_id=provider_id,
            model_id=model_id,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
    )


def _request() -> RewriteRequest:
    return RewriteRequest(
        text="The original text.",
        document_type=DocumentType.GENERAL,
        audience="general",
        tone="professional",
        intensity=RewriteIntensity.NATURAL_REWRITE,
    )


def _result(
    *,
    provider_name: str = "cloudflare-workers-ai",
    model_name: str = "@cf/example/model",
    primary_provider_name: str = "cloudflare-workers-ai",
    fallback_used: bool = False,
) -> RewriteProviderResult:
    return RewriteProviderResult(
        text="The rewritten text.",
        changes=[],
        provider_name=provider_name,
        model_name=model_name,
        prompt_version="prompt-v1",
        latency_ms=10.0,
        primary_provider_name=primary_provider_name,
        fallback_used=fallback_used,
        provider_error_category=None,
        usage=ProviderUsage(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        ),
    )


def _provider(
    *,
    provider_name: str = "cloudflare-workers-ai",
    result: RewriteProviderResult | None = None,
) -> MagicMock:
    provider = MagicMock(
        spec=RewriteProvider,
    )
    provider.provider_name = provider_name
    provider.rewrite.return_value = (
        result
        if result is not None
        else _result()
    )
    return provider


def test_executes_exact_bound_target() -> None:
    target = _target()
    provider = _provider()

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: provider,
        }
    )

    request = _request()

    result = adapter.execute(
        target=target,
        request=request,
    )

    assert result == _result()
    provider.rewrite.assert_called_once_with(
        request
    )


def test_missing_target_binding_fails_closed() -> None:
    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={}
    )

    with pytest.raises(
        ProviderExecutionBindingError,
        match="no rewrite provider is bound",
    ):
        adapter.execute(
            target=_target(),
            request=_request(),
        )


def test_binding_provider_identity_must_match_target() -> None:
    target = _target()

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: _provider(
                provider_name="other-provider",
            ),
        }
    )

    with pytest.raises(
        ProviderExecutionBindingError,
        match="identity does not match",
    ):
        adapter.execute(
            target=target,
            request=_request(),
        )


def test_binding_failure_occurs_before_provider_execution() -> None:
    target = _target()
    provider = _provider(
        provider_name="other-provider",
    )

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: provider,
        }
    )

    with pytest.raises(
        ProviderExecutionBindingError,
    ):
        adapter.execute(
            target=target,
            request=_request(),
        )

    provider.rewrite.assert_not_called()


def test_result_provider_identity_must_match_target() -> None:
    target = _target()

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: _provider(
                result=_result(
                    provider_name="other-provider",
                )
            ),
        }
    )

    with pytest.raises(
        ProviderExecutionIntegrityError,
        match="result provider identity",
    ):
        adapter.execute(
            target=target,
            request=_request(),
        )


def test_result_model_identity_must_match_target() -> None:
    target = _target()

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: _provider(
                result=_result(
                    model_name="other-model",
                )
            ),
        }
    )

    with pytest.raises(
        ProviderExecutionIntegrityError,
        match="result model identity",
    ):
        adapter.execute(
            target=target,
            request=_request(),
        )


def test_internal_provider_fallback_is_rejected() -> None:
    target = _target()

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: _provider(
                result=_result(
                    fallback_used=True,
                )
            ),
        }
    )

    with pytest.raises(
        ProviderExecutionIntegrityError,
        match="forbids internal provider fallback",
    ):
        adapter.execute(
            target=target,
            request=_request(),
        )


def test_primary_provider_identity_must_match_target() -> None:
    target = _target()

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: _provider(
                result=_result(
                    primary_provider_name="other-provider",
                )
            ),
        }
    )

    with pytest.raises(
        ProviderExecutionIntegrityError,
        match="primary provider identity",
    ):
        adapter.execute(
            target=target,
            request=_request(),
        )


def test_empty_primary_provider_identity_is_allowed() -> None:
    target = _target()

    result = _result(
        primary_provider_name="",
    )

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: _provider(
                result=result,
            ),
        }
    )

    assert adapter.execute(
        target=target,
        request=_request(),
    ) == result


def test_transport_error_propagates_unchanged() -> None:
    target = _target()
    provider = _provider()
    error = RewriteProviderTransportError(
        "transport failed"
    )
    provider.rewrite.side_effect = error

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: provider,
        }
    )

    with pytest.raises(
        RewriteProviderTransportError,
    ) as exc_info:
        adapter.execute(
            target=target,
            request=_request(),
        )

    assert exc_info.value is error


def test_response_error_propagates_unchanged() -> None:
    target = _target()
    provider = _provider()
    error = RewriteProviderResponseError(
        "response failed"
    )
    provider.rewrite.side_effect = error

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: provider,
        }
    )

    with pytest.raises(
        RewriteProviderResponseError,
    ) as exc_info:
        adapter.execute(
            target=target,
            request=_request(),
        )

    assert exc_info.value is error


def test_adapter_does_not_attempt_another_binding() -> None:
    target = _target(
        target_id="primary",
    )
    primary = _provider()
    primary.rewrite.side_effect = (
        RewriteProviderTransportError(
            "primary failed"
        )
    )
    fallback = _provider()

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            "primary": primary,
            "fallback": fallback,
        }
    )

    with pytest.raises(
        RewriteProviderTransportError,
    ):
        adapter.execute(
            target=target,
            request=_request(),
        )

    primary.rewrite.assert_called_once()
    fallback.rewrite.assert_not_called()


def test_target_id_selects_binding_not_provider_identity() -> None:
    first = _target(
        target_id="first",
    )
    second = _target(
        target_id="second",
        model_id="@cf/example/other-model",
    )

    first_provider = _provider()
    second_provider = _provider(
        result=_result(
            model_name="@cf/example/other-model",
        )
    )

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            first.target_id: first_provider,
            second.target_id: second_provider,
        }
    )

    adapter.execute(
        target=second,
        request=_request(),
    )

    first_provider.rewrite.assert_not_called()
    second_provider.rewrite.assert_called_once()


def test_unexpected_provider_exception_propagates() -> None:
    target = _target()
    provider = _provider()
    error = RuntimeError(
        "unexpected"
    )
    provider.rewrite.side_effect = error

    adapter = BoundRewriteProviderExecutionAdapter(
        bindings={
            target.target_id: provider,
        }
    )

    with pytest.raises(RuntimeError) as exc_info:
        adapter.execute(
            target=target,
            request=_request(),
        )

    assert exc_info.value is error
