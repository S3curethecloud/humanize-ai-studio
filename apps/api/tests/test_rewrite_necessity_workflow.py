from app.domain.models import RewriteRequest
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.workflows.rewrite_workflow import RewriteWorkflow


class RecordingProvider:
    def __init__(self) -> None:
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return "recording-provider"

    def rewrite(
        self,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        self.call_count += 1

        return RewriteProviderResult(
            text=(
                "The platform provides governance controls, "
                "trace evidence, policy enforcement, and "
                "human escalation."
            ),
            changes=[],
            provider_name=self.provider_name,
            model_name="recording-model",
            prompt_version="recording-v1",
            primary_provider_name=self.provider_name,
            usage=ProviderUsage(
                input_tokens=10,
                output_tokens=12,
                total_tokens=22,
            ),
        )


def test_no_change_skips_provider_and_records_zero_tokens() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    source = "The policy engine evaluates every proposed tool call before execution."

    result = workflow.execute(RewriteRequest(text=source))

    assert provider.call_count == 0
    assert result.rewritten_text == source
    assert result.provider_name == "rewrite-necessity-analyzer"
    assert result.model_name == "deterministic-no-change"
    assert result.prompt_version == "rewrite-necessity-v1"
    assert result.provider_execution.fallback_used is False
    assert result.provider_execution.usage.input_tokens == 0
    assert result.provider_execution.usage.output_tokens == 0
    assert result.provider_execution.usage.total_tokens == 0
    assert result.changes == []
    assert result.verification.decision.value == "pass"
    assert result.editorial_quality.decision.value == "pass"


def test_minimal_edit_skips_provider_and_records_change() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(text=("Furthermore, the migration completed in 30 days."))
    )

    assert provider.call_count == 0
    assert result.rewritten_text == ("The migration completed in 30 days.")
    assert result.provider_name == "rewrite-necessity-analyzer"
    assert result.model_name == "deterministic-minimal-edit"
    assert result.provider_execution.usage.total_tokens == 0
    assert len(result.changes) == 1
    assert result.changes[0].change_type == "minimal_edit"
    assert result.verification.decision.value == "pass"


def test_full_rewrite_invokes_configured_provider() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(
            text=(
                "The platform provides governance controls. "
                "The platform provides trace evidence. "
                "The platform provides policy enforcement. "
                "The platform provides human escalation."
            )
        )
    )

    assert provider.call_count == 1
    assert result.provider_name == "recording-provider"
    assert result.model_name == "recording-model"
    assert result.provider_execution.usage.input_tokens == 10
    assert result.provider_execution.usage.output_tokens == 12
    assert result.provider_execution.usage.total_tokens == 22


def test_deep_reconstruction_forces_provider() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(
            text="The policy engine evaluates tool calls.",
            intensity="deep_reconstruction",
        )
    )

    assert provider.call_count == 1
    assert result.provider_name == "recording-provider"


def test_bypass_output_still_runs_fact_verification() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(
            text=("Additionally, the service processed 12,000 requests with 99.9% availability.")
        )
    )

    assert provider.call_count == 0
    assert "12,000" in result.rewritten_text
    assert "99.9%" in result.rewritten_text
    assert result.verification.decision.value == "pass"
    assert result.verification.missing_facts == []
