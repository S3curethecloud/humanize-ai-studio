from __future__ import annotations

import httpx
import pytest

from app.domain.models import (
    RewriteIntensity,
    RewriteRequest,
)
from app.providers.exceptions import (
    RewriteProviderConfigurationError,
    RewriteProviderResponseError,
    RewriteProviderTransportError,
)
from app.providers.openai_responses import (
    OPENAI_PROVIDER_NAME,
    OPENAI_RESPONSES_URL,
    OpenAIResponsesProvider,
)


def _request() -> RewriteRequest:
    return RewriteRequest(
        text="Furthermore, this is the source.",
        audience="technical leaders",
        tone="direct",
        intensity=RewriteIntensity.NATURAL_REWRITE,
    )


def _response(
    *,
    status_code: int = 200,
    body: dict[str, object] | None = None,
) -> httpx.Response:
    resolved_body = (
        body
        if body is not None
        else {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "This is the source.",
                        }
                    ],
                }
            ],
            "usage": {
                "input_tokens": 12,
                "output_tokens": 5,
                "total_tokens": 17,
            },
        }
    )

    return httpx.Response(
        status_code,
        json=resolved_body,
        request=httpx.Request(
            "POST",
            OPENAI_RESPONSES_URL,
        ),
    )


def _client_with_response(
    response: httpx.Response,
) -> httpx.Client:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return response

    return httpx.Client(
        transport=httpx.MockTransport(handler)
    )


def test_provider_identity_is_stable() -> None:
    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
    )

    assert provider.provider_name == OPENAI_PROVIDER_NAME


@pytest.mark.parametrize(
    ("api_key", "model_name"),
    [
        ("", "model-a"),
        ("   ", "model-a"),
        ("secret", ""),
        ("secret", "   "),
    ],
)
def test_configuration_requires_api_key_and_model(
    api_key: str,
    model_name: str,
) -> None:
    with pytest.raises(
        RewriteProviderConfigurationError,
    ):
        OpenAIResponsesProvider(
            api_key=api_key,
            model_name=model_name,
        )


def test_configuration_requires_positive_timeout() -> None:
    with pytest.raises(
        RewriteProviderConfigurationError,
        match="greater than zero",
    ):
        OpenAIResponsesProvider(
            api_key="secret",
            model_name="model-a",
            timeout_seconds=0,
        )


def test_rewrite_returns_exact_provider_and_model_identity() -> None:
    client = _client_with_response(
        _response()
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    result = provider.rewrite(
        _request()
    )

    assert result.provider_name == "openai"
    assert result.model_name == "model-a"
    assert result.primary_provider_name == "openai"
    assert result.fallback_used is False
    assert result.provider_error_category is None


def test_rewrite_extracts_text_and_usage() -> None:
    client = _client_with_response(
        _response()
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    result = provider.rewrite(
        _request()
    )

    assert result.text == "This is the source."
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 5
    assert result.usage.total_tokens == 17


def test_changed_text_records_one_change() -> None:
    client = _client_with_response(
        _response()
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    result = provider.rewrite(
        _request()
    )

    assert len(result.changes) == 1
    assert result.changes[0].original == (
        "Furthermore, this is the source."
    )
    assert result.changes[0].replacement == (
        "This is the source."
    )


def test_unchanged_text_records_no_change() -> None:
    source = "Exact source."

    client = _client_with_response(
        _response(
            body={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": source,
                            }
                        ],
                    }
                ]
            }
        )
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    result = provider.rewrite(
        RewriteRequest(text=source)
    )

    assert result.text == source
    assert result.changes == []


def test_request_uses_responses_endpoint_and_exact_model() -> None:
    captured: list[
        httpx.Request
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        captured.append(request)
        return _response()

    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="catalog-model",
        timeout_seconds=19.0,
        client=client,
    )

    provider.rewrite(
        _request()
    )

    assert len(captured) == 1

    request = captured[0]

    assert str(request.url) == OPENAI_RESPONSES_URL
    assert (
        request.headers["authorization"]
        == "Bearer secret"
    )

    body = request.content.decode()

    assert '"model":"catalog-model"' in body
    assert '"store":false' in body


def test_request_contains_rewrite_controls_and_source() -> None:
    captured: list[
        httpx.Request
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        captured.append(request)
        return _response()

    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    provider.rewrite(
        _request()
    )

    body = captured[0].content.decode()

    assert "technical leaders" in body
    assert "direct" in body
    assert "natural_rewrite" in body
    assert "Furthermore" in body


def test_http_error_maps_to_provider_response_error() -> None:
    client = _client_with_response(
        _response(
            status_code=429,
            body={
                "error": {
                    "message": "rate limited"
                }
            },
        )
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    with pytest.raises(
        RewriteProviderResponseError,
        match="429.*rate limited",
    ):
        provider.rewrite(
            _request()
        )


def test_transport_error_maps_to_provider_transport_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "unavailable",
            request=request,
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    with pytest.raises(
        RewriteProviderTransportError,
    ):
        provider.rewrite(
            _request()
        )


def test_invalid_json_maps_to_provider_response_error() -> None:
    response = httpx.Response(
        200,
        content=b"not-json",
        request=httpx.Request(
            "POST",
            OPENAI_RESPONSES_URL,
        ),
    )

    client = _client_with_response(
        response
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    with pytest.raises(
        RewriteProviderResponseError,
        match="invalid JSON",
    ):
        provider.rewrite(
            _request()
        )


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"output": "not-a-list"},
        {"output": []},
        {
            "output": [
                {
                    "type": "message",
                    "content": [],
                }
            ]
        },
    ],
)
def test_missing_output_text_fails_closed(
    body: dict[str, object],
) -> None:
    client = _client_with_response(
        _response(
            body=body
        )
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    with pytest.raises(
        RewriteProviderResponseError,
    ):
        provider.rewrite(
            _request()
        )


def test_multiple_output_text_parts_are_combined() -> None:
    client = _client_with_response(
        _response(
            body={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "First ",
                            },
                            {
                                "type": "output_text",
                                "text": "second.",
                            },
                        ],
                    }
                ]
            }
        )
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    result = provider.rewrite(
        _request()
    )

    assert result.text == "First second."


def test_missing_or_invalid_usage_is_nonfatal() -> None:
    client = _client_with_response(
        _response(
            body={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Rewritten.",
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": -1,
                    "output_tokens": "five",
                    "total_tokens": True,
                },
            }
        )
    )

    provider = OpenAIResponsesProvider(
        api_key="secret",
        model_name="model-a",
        client=client,
    )

    result = provider.rewrite(
        _request()
    )

    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None
    assert result.usage.total_tokens is None
