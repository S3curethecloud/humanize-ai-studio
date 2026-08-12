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
from app.v2.services.candidate_rewrite_orchestrator import (
    CandidateGenerationError,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateWorkspaceRewriteService,
)
from app.workflows.rewrite_workflow import RewriteWorkflow

client = TestClient(app)
non_raising_client = TestClient(
    app,
    raise_server_exceptions=False,
)


class StableWorkflow:
    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        del trace_id

        return RewriteResponse(
            trace_id="trace-h2",
            workflow_states=[
                "received",
                "ready_for_review",
            ],
            source_text=request.text,
            rewritten_text=(
                "Project Atlas completed the review in 2025 with revenue of 42 million."
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
                rationale="H2 compatibility test.",
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


class RaisingCandidateService:
    def __init__(
        self,
        message: str,
    ) -> None:
        self._message = message

    def execute(
        self,
        **kwargs: object,
    ) -> object:
        del kwargs
        raise CandidateGenerationError(self._message)


def setup_function() -> None:
    v2_routes.services = V2Services(
        workflow=cast(
            RewriteWorkflow,
            StableWorkflow(),
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
            "name": "H2 Workspace",
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


def test_malformed_candidate_count_boundaries_return_422() -> None:
    user_id, workspace_id = _workspace()

    invalid_values: tuple[object, ...] = (
        -1,
        0,
        1,
        6,
        2.5,
        "not-a-number",
        [],
        {},
    )

    for candidate_count in invalid_values:
        response = client.post(
            f"/api/v2/workspaces/{workspace_id}/rewrites",
            json={
                **_payload(
                    user_id=user_id,
                ),
                "candidate_count": candidate_count,
            },
        )

        assert response.status_code == 422, {
            "candidate_count": candidate_count,
            "response": response.json(),
        }


def test_omitted_candidate_count_preserves_single_result_shape() -> None:
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


def test_explicit_null_candidate_count_with_claim_lock_stays_single_result() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=user_id,
            ),
            "candidate_count": None,
            "protected_terms": [
                {
                    "text": "Project Atlas",
                    "case_sensitive": True,
                }
            ],
            "claim_lock_enforcement_mode": "strict",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "multi_candidate" not in body
    assert body["claim_lock"]["validation"]["decision"] == "pass"

    assert "candidate_set_id" not in body["history"]
    assert "candidate_audit_snapshot" not in body["history"]
    assert "selected_candidate_id" not in body["history"]


def test_real_multi_candidate_membership_failure_returns_403() -> None:
    owner_id, workspace_id = _workspace()

    outsider_response = client.post(
        "/api/v2/users",
        json={
            "email": "outsider@example.com",
            "display_name": "Outsider",
        },
    )
    assert outsider_response.status_code == 201

    outsider_id = outsider_response.json()["user"]["user_id"]

    assert outsider_id != owner_id

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=outsider_id,
            ),
            "candidate_count": 2,
        },
    )

    assert response.status_code == 403


def test_duplicate_candidate_generation_failure_is_controlled_http_conflict() -> None:
    user_id, workspace_id = _workspace()

    v2_routes.services.multi_candidate = cast(
        MultiCandidateWorkspaceRewriteService,
        RaisingCandidateService("candidate generation produced duplicate rewritten outputs"),
    )

    response = non_raising_client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=user_id,
            ),
            "candidate_count": 2,
        },
    )

    assert response.status_code == 409

    assert response.json()["detail"] == (
        "candidate generation produced duplicate rewritten outputs"
    )


def test_source_mismatch_generation_failure_is_controlled_http_conflict() -> None:
    user_id, workspace_id = _workspace()

    v2_routes.services.multi_candidate = cast(
        MultiCandidateWorkspaceRewriteService,
        RaisingCandidateService(
            "candidate workflow response source text does not match the original request"
        ),
    )

    response = non_raising_client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_payload(
                user_id=user_id,
            ),
            "candidate_count": 2,
        },
    )

    assert response.status_code == 409

    assert response.json()["detail"] == (
        "candidate workflow response source text does not match the original request"
    )
