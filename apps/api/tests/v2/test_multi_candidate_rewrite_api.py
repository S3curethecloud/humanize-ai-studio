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
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)

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
            trace_id=f"trace-api-{index}",
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
            provider_execution=(
                ProviderExecutionEvidence(
                    latency_ms=1.0,
                    primary_provider_name=("test-provider"),
                    actual_provider_name=("test-provider"),
                    fallback_used=False,
                    provider_error_category=None,
                    usage=ProviderUsageEvidence(
                        input_tokens=1,
                        output_tokens=1,
                        total_tokens=2,
                    ),
                )
            ),
            rewrite_necessity=(
                RewriteNecessityEvidence(
                    decision="full_rewrite",
                    score=80,
                    provider_required=True,
                    signals=[],
                    rationale="API candidate test.",
                )
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
            editorial_quality=(
                EditorialQualityResult(
                    decision=(EditorialQualityDecision.PASS),
                    naturalness_score=0.95,
                    source_flag_count=0,
                    remaining_flag_count=0,
                    removed_flag_count=0,
                    remaining_flagged_segments=[],
                    warnings=[],
                )
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
            "name": "Candidate Workspace",
        },
    )
    assert workspace_response.status_code == 201

    workspace_id = workspace_response.json()["workspace"]["workspace_id"]

    return user_id, workspace_id


def _rewrite_payload(
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


def test_single_result_request_remains_default_contract() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json=_rewrite_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert "rewrite" in body
    assert "history" in body
    assert "multi_candidate" not in body

    assert body["rewrite"]["trace_id"] == body["history"]["trace_id"]


def test_candidate_count_two_through_five_is_http_valid() -> None:
    user_id, workspace_id = _workspace()

    for candidate_count in (
        2,
        3,
        4,
        5,
    ):
        response = client.post(
            f"/api/v2/workspaces/{workspace_id}/rewrites",
            json={
                **_rewrite_payload(
                    user_id=user_id,
                ),
                "candidate_count": candidate_count,
            },
        )

        assert response.status_code == 200, {
            "candidate_count": candidate_count,
            "response": response.json(),
        }


def test_invalid_candidate_count_is_rejected() -> None:
    user_id, workspace_id = _workspace()

    for candidate_count in (
        1,
        6,
    ):
        response = client.post(
            f"/api/v2/workspaces/{workspace_id}/rewrites",
            json={
                **_rewrite_payload(
                    user_id=user_id,
                ),
                "candidate_count": candidate_count,
            },
        )

        assert response.status_code == 422


def test_multi_candidate_response_exposes_candidate_set_and_diffs() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_rewrite_payload(
                user_id=user_id,
            ),
            "candidate_count": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()
    evidence = body["multi_candidate"]

    assert len(evidence["candidate_set"]["candidates"]) == 3

    assert len(evidence["diffs"]["diffs"]) == 3

    assert evidence["candidate_set"]["candidate_set_id"] == evidence["diffs"]["candidate_set_id"]


def test_multi_candidate_response_exposes_controls_and_selection() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_rewrite_payload(
                user_id=user_id,
            ),
            "candidate_count": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()
    evidence = body["multi_candidate"]

    assert len(evidence["controls"]) == 3

    selected_candidate_id = evidence["selection"]["selected_candidate_id"]

    assert selected_candidate_id is not None

    assert selected_candidate_id == evidence["audit"]["selected_candidate_id"]


def test_selected_candidate_is_legacy_rewrite_and_history_result() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_rewrite_payload(
                user_id=user_id,
            ),
            "candidate_count": 3,
        },
    )

    assert response.status_code == 200

    body = response.json()
    evidence = body["multi_candidate"]

    selected_id = evidence["selection"]["selected_candidate_id"]

    candidates = {
        candidate["candidate_id"]: candidate
        for candidate in evidence["candidate_set"]["candidates"]
    }

    assert body["rewrite"]["rewritten_text"] == candidates[selected_id]["rewritten_text"]

    assert body["history"]["rewritten_text"] == body["rewrite"]["rewritten_text"]

    assert body["history"]["selected_candidate_id"] == selected_id


def test_candidate_audit_linkage_is_persisted_in_history() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_rewrite_payload(
                user_id=user_id,
            ),
            "candidate_count": 2,
        },
    )

    assert response.status_code == 200

    body = response.json()
    evidence = body["multi_candidate"]
    history = body["history"]

    assert history["candidate_set_id"] == evidence["candidate_set"]["candidate_set_id"]

    assert history["candidate_audit_snapshot"] == evidence["audit"]

    history_response = client.get(
        f"/api/v2/workspaces/{workspace_id}/history",
        params={
            "user_id": user_id,
        },
    )

    assert history_response.status_code == 200

    persisted = history_response.json()["records"][0]

    assert persisted["candidate_audit_snapshot"] == evidence["audit"]


def test_multi_candidate_claim_lock_evidence_remains_visible() -> None:
    user_id, workspace_id = _workspace()

    response = client.post(
        f"/api/v2/workspaces/{workspace_id}/rewrites",
        json={
            **_rewrite_payload(
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

    assert response.status_code == 200

    body = response.json()

    assert body["claim_lock"]["validation"]["decision"] == "pass"

    controls = body["multi_candidate"]["controls"]

    assert all(control["claim_lock_validation"]["decision"] == "pass" for control in controls)
