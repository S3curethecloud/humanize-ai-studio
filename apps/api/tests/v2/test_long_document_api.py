from __future__ import annotations

from datetime import UTC, datetime
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
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)

client = TestClient(app)

SOURCE = (
    "# Overview\n"
    "Project Atlas completed the review.\n"
    "\n"
    "## Financials\n"
    "Revenue was 42 million in 2025.\n"
)


def _response(
    *,
    source_text: str,
    rewritten_text: str,
    trace_id: str,
    decision: ReleaseDecision = ReleaseDecision.PASS,
) -> RewriteResponse:
    return RewriteResponse(
        trace_id=trace_id,
        workflow_states=[
            "received",
            "ready_for_review",
        ],
        source_text=source_text,
        rewritten_text=rewritten_text,
        provider_name="test-provider",
        model_name="test-model",
        prompt_version="test-v1",
        provider_execution=(
            ProviderExecutionEvidence(
                latency_ms=0.0,
                primary_provider_name=("test-provider"),
                actual_provider_name=("test-provider"),
                fallback_used=False,
                provider_error_category=None,
                usage=ProviderUsageEvidence(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                ),
            )
        ),
        rewrite_necessity=(
            RewriteNecessityEvidence(
                decision="full_rewrite",
                score=80,
                provider_required=True,
                signals=[],
                rationale=("Long-document API test."),
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
                naturalness_score=1.0,
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
            decision=decision,
            preserved_facts=[],
            missing_facts=[],
            unexpected_facts=[],
            warnings=[],
        ),
    )


class RecordingWorkflow:
    def __init__(
        self,
        *,
        replace_atlas: bool = False,
        decision: ReleaseDecision = (ReleaseDecision.PASS),
    ) -> None:
        self.requests: list[RewriteRequest] = []
        self._replace_atlas = replace_atlas
        self._decision = decision

    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        del trace_id

        self.requests.append(request)

        rewritten = request.text

        if self._replace_atlas:
            rewritten = rewritten.replace(
                "Project Atlas",
                "The project",
            )

        return _response(
            source_text=request.text,
            rewritten_text=rewritten,
            trace_id=(f"trace_{len(self.requests)}"),
            decision=self._decision,
        )


def _install_services(
    workflow: RecordingWorkflow,
) -> None:
    v2_routes.services = V2Services(
        workflow=cast(
            RewriteWorkflow,
            workflow,
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
            "name": "Long Document Workspace",
        },
    )

    assert workspace_response.status_code == 201

    workspace_id = workspace_response.json()["workspace"]["workspace_id"]

    return workspace_id, user_id


def _payload(
    *,
    user_id: str,
    text: str = SOURCE,
    protected_terms: list[dict[str, object]] | None = None,
    enforcement_mode: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_id": user_id,
        "rewrite": {
            "text": text,
            "document_type": "general",
            "audience": ("engineering leadership"),
            "tone": "natural and clear",
            "intensity": ("deep_reconstruction"),
            "preserve_numbers": True,
            "preserve_dates": True,
        },
    }

    if protected_terms is not None:
        payload["protected_terms"] = protected_terms

    if enforcement_mode is not None:
        payload["claim_lock_enforcement_mode"] = enforcement_mode

    return payload


def test_long_document_endpoint_runs_a_to_g_flow() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["reconstruction"]["reconstructed_text"] == SOURCE

    assert body["audit"]["structure"] == body["reconstruction"]["structure"]

    assert body["audit"]["reconstruction"] == body["reconstruction"]

    assert len(workflow.requests) == 2


def test_long_document_endpoint_persists_audit() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200

    audit_id = response.json()["audit"]["audit_id"]

    stored = v2_routes.services.long_document_audit.get(
        workspace_id=workspace_id,
        user_id=user_id,
        audit_id=audit_id,
    )

    assert stored is not None
    assert stored.audit_id == audit_id


def test_long_document_endpoint_requires_membership_before_rewrite() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, _ = _workspace()

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id="user_outsider",
        ),
    )

    assert response.status_code == 403
    assert workflow.requests == []


def test_long_document_v1_failure_is_conflict() -> None:
    workflow = RecordingWorkflow(
        decision=ReleaseDecision.FAIL,
    )
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 409

    records = v2_routes.services.long_document_audit.list_workspace(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert records == ()


def test_long_document_strict_claim_lock_violation_is_conflict() -> None:
    workflow = RecordingWorkflow(
        replace_atlas=True,
    )
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id=user_id,
            protected_terms=[
                {
                    "text": "Project Atlas",
                    "case_sensitive": True,
                }
            ],
            enforcement_mode="strict",
        ),
    )

    assert response.status_code == 409

    records = v2_routes.services.long_document_audit.list_workspace(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    assert records == ()


def test_long_document_audit_only_violation_completes_with_evidence() -> None:
    workflow = RecordingWorkflow(
        replace_atlas=True,
    )
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id=user_id,
            protected_terms=[
                {
                    "text": "Project Atlas",
                    "case_sensitive": True,
                }
            ],
            enforcement_mode="audit_only",
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["claim_lock"]["validation"]["decision"] == "violation"

    assert body["audit"]["claim_lock_validation"]["decision"] == "violation"


def test_long_document_claim_lock_evidence_is_opt_in() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200
    assert "claim_lock" not in response.json()


def test_long_document_payload_can_exceed_v1_request_limit() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    text = "# Large Section\n" + ("A" * 20_001)

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id=user_id,
            text=text,
        ),
    )

    assert response.status_code == 200

    assert response.json()["reconstruction"]["reconstructed_text"] == text


def test_long_document_payload_rejects_more_than_domain_limit() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    text = "A" * 1_000_001

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=_payload(
            user_id=user_id,
            text=text,
        ),
    )

    assert response.status_code == 422
    assert workflow.requests == []


def test_long_document_endpoint_rejects_candidate_fields() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    payload = _payload(
        user_id=user_id,
    )
    payload["candidate_count"] = 2

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=payload,
    )

    assert response.status_code == 422
    assert workflow.requests == []


def test_long_document_endpoint_rejects_voice_profile_field() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    payload = _payload(
        user_id=user_id,
    )
    payload["voice_profile_id"] = "voice_test"

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/long-document-rewrites"),
        json=payload,
    )

    assert response.status_code == 422
    assert workflow.requests == []


def test_regular_v2_rewrite_route_remains_available() -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/rewrites"),
        json={
            "user_id": user_id,
            "rewrite": {
                "text": "Simple source.",
                "document_type": "general",
                "audience": "general audience",
                "tone": "natural and clear",
                "intensity": "natural_rewrite",
                "preserve_numbers": True,
                "preserve_dates": True,
            },
        },
    )

    assert response.status_code == 200

def test_long_document_active_workspace_policy_exposes_existing_audit_evidence(
) -> None:
    workflow = RecordingWorkflow()
    _install_services(workflow)

    workspace_id, user_id = _workspace()

    policy_id = f"policy_{workspace_id}"
    now = datetime(
        2026,
        8,
        26,
        12,
        0,
        tzinfo=UTC,
    )

    policy = EnterpriseWorkspaceClaimLockPolicy(
        policy_id=policy_id,
        workspace_id=workspace_id,
        status=EnterpriseClaimLockPolicyStatus.ACTIVE,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(
            ProtectedTerm(
                term_id="workspace_term_long_api",
                text="Project Atlas",
                case_sensitive=True,
                provenance=ClaimLockProvenance(
                    origin=ClaimLockOrigin.WORKSPACE,
                    source_reference=(
                        "workspace-claim-lock-policy:"
                        f"{policy_id}:revision:1"
                    ),
                ),
            ),
        ),
        created_by_user_id=user_id,
        created_at=now,
        updated_by_user_id=user_id,
        updated_at=now,
        revision=1,
    )

    v2_routes.services.enterprise_claim_lock_policies.create(
        policy
    )

    response = client.post(
        (
            f"/api/v2/workspaces/{workspace_id}/"
            "long-document-rewrites"
        ),
        json=_payload(
            user_id=user_id,
        ),
    )

    assert response.status_code == 200

    body = response.json()

    workspace_policy = (
        body["claim_lock"]["workspace_policy"]
    )

    assert workspace_policy["policy_id"] == policy_id
    assert workspace_policy["policy_revision"] == 1
    assert workspace_policy["applicable_term_ids"] == [
        "workspace_term_long_api"
    ]

    assert (
        body["audit"]["claim_lock_workspace_policy"]
        == workspace_policy
    )

    assert body["audit"]["audit_version"] == (
        "long-document-audit-v2"
    )
