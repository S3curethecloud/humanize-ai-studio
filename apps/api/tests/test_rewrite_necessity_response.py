from fastapi.testclient import TestClient

from app.domain.models import RewriteRequest
from app.main import app
from app.providers.base import (
    ProviderUsage,
    RewriteProviderResult,
)
from app.workflows.rewrite_workflow import RewriteWorkflow

client = TestClient(app)


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


def test_light_edit_no_change_exposes_auditable_decision() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(
            text=(
                "The policy engine evaluates every proposed tool call before execution."
            ),
            intensity="light_edit",
        )
    )

    evidence = result.rewrite_necessity

    assert provider.call_count == 0
    assert evidence.decision == "no_change"
    assert evidence.score == 0
    assert evidence.provider_required is False
    assert evidence.rationale
    assert len(evidence.signals) == 1
    assert evidence.signals[0].signal_type == "already_clear"


def test_light_edit_exposes_formulaic_signal() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(
            text="Furthermore, the migration completed in 30 days.",
            intensity="light_edit",
        )
    )

    evidence = result.rewrite_necessity

    assert provider.call_count == 0
    assert evidence.decision == "minimal_edit"
    assert evidence.score == 10
    assert evidence.provider_required is False
    assert evidence.signals[0].signal_type == ("formulaic_language")
    assert evidence.signals[0].evidence == ["furthermore"]


def test_natural_rewrite_invokes_provider_for_clear_text() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(
            text=(
                "The policy engine evaluates every "
                "proposed tool call before execution."
            ),
            intensity="natural_rewrite",
        )
    )

    evidence = result.rewrite_necessity

    assert provider.call_count == 1
    assert evidence.decision == "full_rewrite"
    assert evidence.provider_required is True
    assert any(
        signal.signal_type == "intensity_request"
        for signal in evidence.signals
    )


def test_full_rewrite_exposes_structural_signal() -> None:
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

    evidence = result.rewrite_necessity

    assert provider.call_count == 1
    assert evidence.decision == "full_rewrite"
    assert evidence.provider_required is True
    assert any(signal.signal_type == "repetition" for signal in evidence.signals)


def test_deep_reconstruction_exposes_intensity_signal() -> None:
    provider = RecordingProvider()
    workflow = RewriteWorkflow(provider=provider)

    result = workflow.execute(
        RewriteRequest(
            text="The policy engine evaluates tool calls.",
            intensity="deep_reconstruction",
        )
    )

    evidence = result.rewrite_necessity

    assert provider.call_count == 1
    assert evidence.decision == "full_rewrite"
    assert evidence.provider_required is True
    assert any(signal.signal_type == "intensity_request" for signal in evidence.signals)


def test_api_serializes_rewrite_necessity_contract() -> None:
    response = client.post(
        "/api/v1/rewrites",
        json={
            "text": (
                "Additionally, the service processed 12,000 requests."
            ),
            "intensity": "light_edit",
        },
    )

    assert response.status_code == 200

    body = response.json()
    evidence = body["rewrite_necessity"]

    assert evidence["decision"] == "minimal_edit"
    assert evidence["provider_required"] is False
    assert evidence["score"] == 10
    assert evidence["rationale"]
    assert evidence["signals"] == [
        {
            "signal_type": "formulaic_language",
            "description": (
                "Localized formulaic language can be removed without reconstructing the document."
            ),
            "score": 10,
            "evidence": ["additionally"],
        }
    ]
