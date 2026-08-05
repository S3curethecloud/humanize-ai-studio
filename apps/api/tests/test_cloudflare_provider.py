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
    assert result.prompt_version == "cloudflare-humanize-v5"


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
    assert result.prompt_version == "cloudflare-humanize-v5"


def test_cloudflare_provider_rejects_claim_inflation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "response": json.dumps(
                        {
                            "rewritten_text": (
                                "I have extensive experience and "
                                "developed expertise in generative AI."
                            )
                        }
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

    with pytest.raises(
        RewriteProviderResponseError,
        match="claim-integrity validation",
    ):
        provider.rewrite(
            RewriteRequest(
                text=("I have hands-on experience with generative AI."),
                document_type="professional_email",
                audience="technical hiring team",
                tone="natural and professional",
                intensity="deep_reconstruction",
            )
        )


def test_cloudflare_provider_accepts_claim_preserving_rewrite() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "response": json.dumps(
                        {
                            "rewritten_text": (
                                "I work with generative AI and have "
                                "hands-on experience across RAG and "
                                "agentic workflows."
                            )
                        }
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
            text=(
                "I have hands-on experience with generative AI across RAG and agentic workflows."
            ),
            document_type="professional_email",
            audience="technical hiring team",
            tone="natural and professional",
            intensity="deep_reconstruction",
        )
    )

    assert result.provider_name == "cloudflare-workers-ai"
    assert result.fallback_used is False
    assert "hands-on experience" in result.text


def test_cloudflare_provider_repairs_rejected_rewrite_once() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        body = json.loads(request.content)

        if request_count == 1:
            assert body["temperature"] == 0.4

            rewritten_text = (
                "I have developed expertise in generative AI across RAG and agentic workflows."
            )
        else:
            assert request_count == 2
            assert body["temperature"] == 0.0

            repair_prompt = body["messages"][1]["content"]

            assert "REJECTED VIOLATIONS" in repair_prompt
            assert "developed expertise" in repair_prompt
            assert "hands-on experience" in repair_prompt

            rewritten_text = (
                "Across RAG and agentic workflows, I have "
                "hands-on experience designing generative "
                "AI systems."
            )

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "response": json.dumps(
                        {
                            "rewritten_text": rewritten_text,
                        }
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
            text=(
                "I have hands-on experience designing "
                "generative AI systems across RAG and "
                "agentic workflows."
            ),
            document_type="professional_email",
            audience="technical hiring team",
            tone="natural and professional",
            intensity="deep_reconstruction",
        )
    )

    assert request_count == 2
    assert result.provider_name == "cloudflare-workers-ai"
    assert result.fallback_used is False
    assert result.text != (
        "I have hands-on experience designing "
        "generative AI systems across RAG and "
        "agentic workflows."
    )
    assert result.prompt_version == "cloudflare-humanize-v5"
    assert "hands-on experience" in result.text
    assert "developed expertise" not in result.text
    assert len(result.changes) == 1
    assert "policy-constrained repair" in result.changes[0].reason


def test_cloudflare_provider_raises_when_repair_also_fails() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        rewritten_text = "I have developed expertise and extensive experience in generative AI."

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "response": json.dumps(
                        {
                            "rewritten_text": rewritten_text,
                        }
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

    with pytest.raises(
        RewriteProviderResponseError,
        match="repair failed claim-integrity validation",
    ):
        provider.rewrite(
            RewriteRequest(
                text=("I have hands-on experience with generative AI."),
                document_type="professional_email",
                audience="technical hiring team",
                tone="natural and professional",
                intensity="deep_reconstruction",
            )
        )

    assert request_count == 2


def test_cloudflare_provider_does_not_repair_valid_output() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "response": json.dumps(
                        {
                            "rewritten_text": (
                                "I have hands-on experience designing generative AI systems."
                            )
                        }
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

    provider.rewrite(
        RewriteRequest(
            text=("I have hands-on experience designing generative AI systems."),
            document_type="professional_email",
            audience="technical hiring team",
            tone="natural and professional",
            intensity="deep_reconstruction",
        )
    )

    assert request_count == 1


def test_cloudflare_provider_rejects_no_op_deep_repair() -> None:
    request_count = 0
    source_text = (
        "I have hands-on experience designing generative AI "
        "systems across RAG and agentic workflows."
    )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count == 1:
            rewritten_text = (
                "I have developed expertise in generative AI across RAG and agentic workflows."
            )
        else:
            assert request_count == 2
            rewritten_text = source_text

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "response": json.dumps(
                        {
                            "rewritten_text": rewritten_text,
                        }
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

    with pytest.raises(
        RewriteProviderResponseError,
        match="useful-distance validation",
    ):
        provider.rewrite(
            RewriteRequest(
                text=source_text,
                document_type="professional_email",
                audience="technical hiring team",
                tone="natural and professional",
                intensity="deep_reconstruction",
            )
        )

    assert request_count == 2
