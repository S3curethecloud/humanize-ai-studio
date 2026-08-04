from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rewrite_removes_formulaic_language_and_preserves_number() -> None:
    response = client.post(
        "/api/v1/rewrites",
        json={
            "text": (
                "Furthermore, it is important to note that "
                "the team completed the project in 30 days."
            ),
            "document_type": "professional_email",
            "audience": "executive stakeholder",
            "tone": "direct and professional",
            "intensity": "natural_rewrite",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["rewritten_text"] == "The team completed the project in 30 days."
    assert body["provider_name"] == "deterministic"
    assert body["model_name"] == "rules-v1"
    assert body["prompt_version"] == "deterministic-rewrite-v1"
    assert body["verification"]["decision"] == "pass"
    assert body["verification"]["missing_facts"] == []
    assert body["workflow_states"][-1] == "ready_for_review"
    assert any(fact["value"] == "30" for fact in body["protected_facts"])


def test_empty_text_is_rejected() -> None:
    response = client.post(
        "/api/v1/rewrites",
        json={
            "text": "",
        },
    )

    assert response.status_code == 422


def test_date_is_preserved() -> None:
    response = client.post(
        "/api/v1/rewrites",
        json={
            "text": ("In conclusion, the architecture review is scheduled for August 4, 2026."),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "August 4, 2026" in body["rewritten_text"]
    assert body["verification"]["decision"] == "pass"


def test_workflow_blocks_when_provider_removes_protected_fact() -> None:
    from app.domain.models import RewriteRequest
    from app.providers.base import RewriteProviderResult
    from app.workflows.rewrite_workflow import RewriteWorkflow

    class UnsafeProvider:
        @property
        def provider_name(self) -> str:
            return "unsafe-test-provider"

        def rewrite(self, request: RewriteRequest) -> RewriteProviderResult:
            del request
            return RewriteProviderResult(
                text="The team completed the migration.",
                changes=[],
                provider_name=self.provider_name,
                model_name="unsafe-test-model",
                prompt_version="unsafe-test-v1",
            )

    workflow = RewriteWorkflow(provider=UnsafeProvider())

    result = workflow.execute(
        RewriteRequest(
            text="The team completed the migration in 30 days.",
            document_type="general",
        )
    )

    assert result.verification.decision == "fail"
    assert result.workflow_states[-1] == "blocked"
    assert result.verification.missing_facts == ["number-1"]
    assert result.provider_name == "unsafe-test-provider"


def test_workflow_requires_review_when_provider_adds_number() -> None:
    from app.domain.models import RewriteRequest
    from app.providers.base import RewriteProviderResult
    from app.workflows.rewrite_workflow import RewriteWorkflow

    class UnsafeProvider:
        @property
        def provider_name(self) -> str:
            return "unsafe-test-provider"

        def rewrite(self, request: RewriteRequest) -> RewriteProviderResult:
            del request
            return RewriteProviderResult(
                text="The team completed the migration in 14 days.",
                changes=[],
                provider_name=self.provider_name,
                model_name="unsafe-test-model",
                prompt_version="unsafe-test-v1",
            )

    workflow = RewriteWorkflow(provider=UnsafeProvider())

    result = workflow.execute(
        RewriteRequest(
            text="The team completed the migration.",
            document_type="general",
        )
    )

    assert result.verification.decision == "warn"
    assert result.workflow_states[-1] == "requires_review"
    assert result.verification.unexpected_facts == ["14"]
    assert result.provider_name == "unsafe-test-provider"
