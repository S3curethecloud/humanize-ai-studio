import httpx

from app.domain.models import RewriteRequest
from app.providers.cloudflare import CloudflareWorkersAIProvider
from app.providers.deterministic import DeterministicRewriteProvider
from app.providers.fallback import FallbackRewriteProvider
from app.workflows.rewrite_workflow import RewriteWorkflow


def test_workflow_returns_trace_and_deterministic_execution_evidence() -> None:
    workflow = RewriteWorkflow(provider=DeterministicRewriteProvider())

    result = workflow.execute(
        RewriteRequest(text="Furthermore, the migration completed in 30 days."),
        trace_id="trace-test-001",
    )

    assert result.trace_id == "trace-test-001"
    assert result.provider_execution.primary_provider_name == "deterministic"
    assert result.provider_execution.actual_provider_name == "deterministic"
    assert result.provider_execution.fallback_used is False
    assert result.provider_execution.provider_error_category is None
    assert result.provider_execution.latency_ms >= 0
    assert result.provider_execution.usage.input_tokens == 0
    assert result.provider_execution.usage.output_tokens == 0
    assert result.provider_execution.usage.total_tokens == 0


def test_cloudflare_provider_extracts_chat_completion_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request

        return httpx.Response(
            200,
            json={
                "success": True,
                "errors": [],
                "messages": [],
                "result": {
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": (
                                    '{"rewritten_text":"The migration completed in 30 days."}'
                                ),
                            },
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 18,
                        "total_tokens": 138,
                    },
                },
            },
        )

    provider = CloudflareWorkersAIProvider(
        account_id="test-account",
        api_token="test-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.rewrite(
        RewriteRequest(text="Furthermore, the migration completed in 30 days.")
    )

    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 18
    assert result.usage.total_tokens == 138
    assert result.fallback_used is False
    assert result.primary_provider_name == "cloudflare-workers-ai"
    assert result.latency_ms >= 0


def test_fallback_records_primary_failure_and_actual_provider() -> None:
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

    cloudflare = CloudflareWorkersAIProvider(
        account_id="test-account",
        api_token="test-token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    provider = FallbackRewriteProvider(
        primary=cloudflare,
        fallback=DeterministicRewriteProvider(),
    )

    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(text="Furthermore, the migration completed in 30 days.")
    )

    assert result.provider_name == "deterministic"
    assert result.provider_execution.primary_provider_name == ("cloudflare-workers-ai")
    assert result.provider_execution.actual_provider_name == "deterministic"
    assert result.provider_execution.fallback_used is True
    assert result.provider_execution.provider_error_category == "response"
    assert result.provider_execution.latency_ms >= 0
