from app.domain.models import RewriteRequest
from app.providers.base import ProviderUsage, RewriteProviderResult
from app.workflows.rewrite_workflow import RewriteWorkflow


class ResidualGenericLanguageProvider:
    @property
    def provider_name(self) -> str:
        return "quality-test-provider"

    def rewrite(
        self,
        request: RewriteRequest,
    ) -> RewriteProviderResult:
        del request

        return RewriteProviderResult(
            text=(
                "In today’s rapidly evolving technological landscape, "
                "the migration completed in 30 days."
            ),
            changes=[],
            provider_name=self.provider_name,
            model_name="quality-test-model",
            prompt_version="quality-test-v1",
            latency_ms=1.0,
            primary_provider_name=self.provider_name,
            fallback_used=False,
            provider_error_category=None,
            usage=ProviderUsage(
                input_tokens=10,
                output_tokens=10,
                total_tokens=20,
            ),
        )


def test_factual_pass_with_weak_editorial_quality_requires_review() -> None:
    workflow = RewriteWorkflow(provider=ResidualGenericLanguageProvider())

    result = workflow.execute(
        RewriteRequest(
            text=(
                "In today's rapidly evolving technological landscape, "
                "it is important to note that the migration completed "
                "in 30 days."
            )
        )
    )

    assert result.verification.decision == "pass"
    assert result.editorial_quality.decision == "review"
    assert result.editorial_quality.remaining_flag_count == 1
    assert result.workflow_states[-1] == "requires_review"
