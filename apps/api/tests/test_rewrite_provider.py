from app.domain.models import RewriteRequest
from app.providers.base import RewriteProvider
from app.providers.deterministic import DeterministicRewriteProvider


def test_deterministic_provider_satisfies_provider_protocol() -> None:
    provider = DeterministicRewriteProvider()

    assert isinstance(provider, RewriteProvider)
    assert provider.provider_name == "deterministic"


def test_deterministic_provider_returns_auditable_metadata() -> None:
    provider = DeterministicRewriteProvider()

    result = provider.rewrite(
        RewriteRequest(
            text=(
                "Furthermore, it is important to note that "
                "the team completed the migration in 30 days."
            ),
            document_type="professional_email",
            audience="executive stakeholder",
            tone="direct and professional",
        )
    )

    assert result.text == "The team completed the migration in 30 days."
    assert result.provider_name == "deterministic"
    assert result.model_name == "rules-v1"
    assert result.prompt_version == "deterministic-rewrite-v1"
    assert len(result.changes) == 2


def test_deterministic_provider_receives_complete_request_context() -> None:
    provider = DeterministicRewriteProvider()

    request = RewriteRequest(
        text="The architecture is ready.",
        document_type="technical_document",
        audience="security architecture review board",
        tone="precise and technical",
        intensity="light_edit",
    )

    result = provider.rewrite(request)

    assert result.text == "The architecture is ready."
    assert result.provider_name == "deterministic"
