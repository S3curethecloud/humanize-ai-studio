from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.domain.models import (
    EditorialQualityDecision,
    EditorialQualityResult,
    ProviderExecutionEvidence,
    ProviderUsageEvidence,
    ReleaseDecision,
    RewriteNecessityEvidence,
    RewriteRequest,
    RewriteResponse,
    VerificationResult,
)
from app.main import app
from app.v2.api.dependencies import V2Services
from app.v2.services.candidate_control_enforcement import (
    CandidateClaimLockViolationError,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateVoiceUnavailableError,
    MultiCandidateWorkspaceRewriteService,
    NoEligibleCandidateError,
)
from app.workflows.rewrite_workflow import RewriteWorkflow

client = TestClient(app)


class DistinctWorkflow:
    def __init__(self) -> None:
        self.requests: list[RewriteRequest] = []

    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        del trace_id

        index = len(self.requests) + 1
        self.requests.append(request)

        return RewriteResponse(
            trace_id=f"trace-g3-{index}",
            workflow_states=[
                "received",
                "ready_for_review",
            ],
            source_text=request.text,
            rewritten_text=(
                "Project Atlas completed the review "
                "in 2025 with revenue of 42 million. "
                f"Candidate {index}."
            ),
            provider_name="test-provider",
            model_name="test-model",
            prompt_version="test-v1",
            provider_execution=ProviderExecutionEvidence(
                latency_ms=1.0,
                primary_provider_name="test-provider",
                actual_provider_name="test-provider",
                fallback_used=False,
                provider_error_category=None,
                usage=ProviderUsageEvidence(
                    input_tokens=1,
                    output_tokens=1,
                    total_tokens=2,
                ),
            ),
            rewrite_necessity=RewriteNecessityEvidence(
                decision="full_rewrite",
                score=80,
                provider_required=True,
                signals=[],
                rationale="G3 API test.",
            ),
            analysis={
                "scores": {
                    "generic_language": 0.0,
                    "repetition": 0.0,
                    "sentence_uniformity": 0.0,
                    "transition_overuse": 0.0,
                },
                "flagged_segments": [],
            },
            editorial_quality=EditorialQualityResult(
                decision=EditorialQualityDecision.PASS,
                naturalness_score=0.95,
                source_flag_count=0,
                remaining_flag_count=0,
                removed_flag_count=0,
                remaining_flagged_segments=[],
                warnings=[],
            ),
            protected_facts=[],
            changes=[],
            verification=VerificationResult(
                decision=ReleaseDecision.PASS,
                preserved_facts=[],
                missing_facts=[],
                unexpected_facts=[],
                warnings=[],
            ),
        )


class RaisingMultiCandidateService:
    def __init__(
        self,
        error: Exception,
    ) -> None:
        self._error = error

    def execute(
        self,
        **kwargs: object,
    ) -> object:
        del kwargs
        raise self._error


def setup_function() -> None:
    v2_routes.services = V2Services(
        workflow=cast(
            RewriteWorkflow,
            DistinctWorkflow(),
        ),
    )


def _workspace() -> tuple[str, str]:
    user_response = client.post(
        "/api/v2/users",
        json={
            "email": "owner@example.com",
            "display_name": "Owner",
        },
    )
    assert user_response.status_code == 201

    user_id = user_response.json()["user"]["user_id"]

    workspace_response = client.post(
        "/api/v2/workspaces",
        json={
            "user_id": user_id,
            "name": "G3 Workspace",
        },
    )
    assert workspace_response.status_code == 201

    workspace_id = workspace_response.json()["workspace"]["workspace_id"]

    return user_id, workspace_id


def _payload(
    *,
    user_id: str,
) -> dict[str, object]:
    return {
        "user_id": user_id,
        "rewrite": {
            "text": ("Revenue was 42 million in 2025. Project Atlas completed the review."),
            "document_type": "general",
            "audience": "engineering leadership",
            "tone": "natural and clear",
            "intensity": "deep_reconstruction",
            "preserve_numbers": True,
            "preserve_dates": True,
        },
    }


def test_omitted_candidate_count_preserves_legacy_response_shape() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert "multi_candidate" not in body
    assert "candidate_set_id" not in body["history"]
    assert "candidate_audit_snapshot" not in body["history"]
    assert "selected_candidate_id" not in body["history"]

    assert body["rewrite"]["trace_id"] == body["history"]["trace_id"]


def test_explicit_null_candidate_count_preserves_legacy_path() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=user_id,
            ),
            "candidate_count": None,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "multi_candidate" not in body
    assert "candidate_set_id" not in body["history"]
    assert "candidate_audit_snapshot" not in body["history"]
    assert "selected_candidate_id" not in body["history"]


def test_strict_candidate_claim_lock_violation_maps_to_409() -> None:
    user_id, workspace_id = _workspace()

    v2_routes.services.multi_candidate = cast(
        MultiCandidateWorkspaceRewriteService,
        RaisingMultiCandidateService(
            CandidateClaimLockViolationError(
                controls=(),
            )
        ),
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=user_id,
            ),
            "candidate_count": 2,
            "protected_terms": [
                {
                    "text": "Project Atlas",
                    "case_sensitive": True,
                }
            ],
            "claim_lock_enforcement_mode": "strict",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "candidate claim lock strict enforcement failed"


def test_no_eligible_candidate_maps_to_409() -> None:
    user_id, workspace_id = _workspace()

    v2_routes.services.multi_candidate = cast(
        MultiCandidateWorkspaceRewriteService,
        RaisingMultiCandidateService(
            NoEligibleCandidateError("multi-candidate rewrite produced no eligible candidate")
        ),
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=user_id,
            ),
            "candidate_count": 2,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "multi-candidate rewrite produced no eligible candidate"


def test_unavailable_multi_candidate_voice_maps_to_503() -> None:
    user_id, workspace_id = _workspace()

    v2_routes.services.multi_candidate = cast(
        MultiCandidateWorkspaceRewriteService,
        RaisingMultiCandidateService(
            MultiCandidateVoiceUnavailableError(
                "voice-aware multi-candidate rewrite orchestration is unavailable"
            )
        ),
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=user_id,
            ),
            "candidate_count": 2,
            "voice_profile_id": "voice-profile-test",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "voice-aware multi-candidate rewrite orchestration is unavailable"
    )


def test_multi_candidate_membership_failure_maps_to_403() -> None:
    user_id, workspace_id = _workspace()

    v2_routes.services.multi_candidate = cast(
        MultiCandidateWorkspaceRewriteService,
        RaisingMultiCandidateService(PermissionError("user is not a member of this workspace")),
    )

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=user_id,
            ),
            "candidate_count": 2,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "user is not a member of this workspace"
