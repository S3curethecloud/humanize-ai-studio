import json

import httpx
import pytest

from app.domain.models import RewriteRequest
from app.providers.cloudflare import CloudflareWorkersAIProvider
from app.providers.deterministic import DeterministicRewriteProvider
from app.providers.exceptions import RewriteProviderResponseError
from app.providers.fallback import FallbackRewriteProvider


def test_cloudflare_provider_returns_structured_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.url.path == (
            "/client/v4/accounts/test-account/ai/run/@cf/openai/gpt-oss-20b"
        )

        request_body = json.loads(request.content)

        assert request_body["messages"][0]["role"] == "system"
        assert "30 days" in request_body["messages"][1]["content"]

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "response": json.dumps(
                        {"rewritten_text": ("The team completed the migration in 30 days.")}
                    )
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = CloudflareWorkersAIProvider(
        account_id="test-account",
        api_token="test-token",
        client=client,
    )

    result = provider.rewrite(
        RewriteRequest(
            text=("Furthermore, the team completed the migration in 30 days."),
            document_type="professional_email",
            audience="executive stakeholder",
            tone="direct and professional",
        )
    )

    assert result.text == "The team completed the migration in 30 days."
    assert result.provider_name == "cloudflare-workers-ai"
    assert result.model_name == "@cf/openai/gpt-oss-20b"
    assert result.prompt_version == "cloudflare-humanize-v2"


def test_cloudflare_provider_rejects_non_json_model_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "response": "This is not JSON.",
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = CloudflareWorkersAIProvider(
        account_id="test-account",
        api_token="test-token",
        client=client,
    )

    with pytest.raises(
        RewriteProviderResponseError,
        match="not valid JSON",
    ):
        provider.rewrite(RewriteRequest(text="Rewrite this draft."))


def test_fallback_provider_uses_deterministic_provider_on_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request

        return httpx.Response(
            503,
            json={
                "success": False,
                "errors": [{"message": "Service unavailable"}],
                "messages": [],
                "result": None,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    cloudflare = CloudflareWorkersAIProvider(
        account_id="test-account",
        api_token="test-token",
        client=client,
    )

    provider = FallbackRewriteProvider(
        primary=cloudflare,
        fallback=DeterministicRewriteProvider(),
    )

    result = provider.rewrite(
        RewriteRequest(text=("Furthermore, the team completed the migration in 30 days."))
    )

    assert result.text == "The team completed the migration in 30 days."
    assert result.provider_name == "deterministic"
    assert result.model_name == "rules-v1"


def test_cloudflare_provider_parses_chat_completions_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "rewritten_text": (
                                            "The team completed the migration in 30 days."
                                        )
                                    }
                                ),
                            },
                        }
                    ],
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))

    provider = CloudflareWorkersAIProvider(
        account_id="test-account",
        api_token="test-token",
        client=client,
    )

    result = provider.rewrite(
        RewriteRequest(
            text=("Furthermore, the team completed the migration in 30 days."),
            document_type="professional_email",
            audience="executive stakeholder",
            tone="direct and professional",
        )
    )

    assert result.text == "The team completed the migration in 30 days."
    assert result.provider_name == "cloudflare-workers-ai"
    assert result.prompt_version == "cloudflare-humanize-v2"
