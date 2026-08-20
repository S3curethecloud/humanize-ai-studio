from __future__ import annotations

from tests.v2.test_support_authorization_gate import allow_all_workspace_authorization_gate
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
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateWorkspaceRewriteService,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)


class RecordingWorkflow:
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

        rewritten_text = (
            f"Project Atlas completed the review in "
            f"2025 with revenue of 42 million. "
            f"Candidate {index}."
        )

        return RewriteResponse(
            trace_id=f"trace-{index}",
            workflow_states=[
                "received",
                "ready_for_review",
            ],
            source_text=request.text,
            rewritten_text=rewritten_text,
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
                    rationale="Candidate test.",
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
                    naturalness_score=(0.90 + (index * 0.01)),
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


def _services() -> tuple[
    WorkspaceService,
    RewriteHistoryService,
    RecordingWorkflow,
]:
    users = InMemoryUserRepository()
    workspaces = InMemoryWorkspaceRepository()
    memberships = InMemoryMembershipRepository()
    history = InMemoryRewriteHistoryRepository()

    workspace_service = WorkspaceService(
        users=users,
        workspaces=workspaces,
        memberships=memberships,
    )

    history_service = RewriteHistoryService(
        history=history,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    return (
        workspace_service,
        history_service,
        RecordingWorkflow(),
    )


def _request() -> RewriteRequest:
    return RewriteRequest(
        text=("Revenue was 42 million in 2025. Project Atlas completed the review."),
        document_type="general",
        audience="engineering leadership",
        tone="natural and clear",
        intensity="deep_reconstruction",
        preserve_numbers=True,
        preserve_dates=True,
    )


def test_multi_candidate_service_generates_requested_count() -> None:
    workspace_service, history_service, workflow = _services()

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )
    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Workspace",
    )

    service = MultiCandidateWorkspaceRewriteService(
        history_service=history_service,
        workflow=workflow,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    result = service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=_request(),
        candidate_count=3,
        explicit_protected_terms=(
            ExplicitProtectedTerm(
                text="Project Atlas",
                case_sensitive=True,
            ),
        ),
        claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
    )

    assert len(result.candidate_set.candidates) == 3
    assert len(result.controls) == 3
    assert len(result.diff_set.diffs) == 3


def test_selected_candidate_matches_rank_one() -> None:
    workspace_service, history_service, workflow = _services()

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )
    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Workspace",
    )

    service = MultiCandidateWorkspaceRewriteService(
        history_service=history_service,
        workflow=workflow,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    result = service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=_request(),
        candidate_count=3,
    )

    assert result.selection.selected_candidate_id == result.audit_snapshot.selected_candidate_id

    assert result.history.selected_candidate_id == result.selection.selected_candidate_id


def test_selected_response_is_persisted_as_legacy_history_result() -> None:
    workspace_service, history_service, workflow = _services()

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )
    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Workspace",
    )

    service = MultiCandidateWorkspaceRewriteService(
        history_service=history_service,
        workflow=workflow,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    result = service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=_request(),
        candidate_count=2,
    )

    assert result.history.rewritten_text == result.selected_response.rewritten_text
    assert result.history.trace_id == result.selected_response.trace_id


def test_candidate_audit_is_persisted_with_history() -> None:
    workspace_service, history_service, workflow = _services()

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )
    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Workspace",
    )

    service = MultiCandidateWorkspaceRewriteService(
        history_service=history_service,
        workflow=workflow,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    result = service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=_request(),
        candidate_count=2,
    )

    assert result.history.candidate_set_id == result.candidate_set.candidate_set_id
    assert result.history.candidate_audit_snapshot == result.audit_snapshot


def test_selected_claim_lock_validation_matches_selected_control() -> None:
    workspace_service, history_service, workflow = _services()

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )
    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Workspace",
    )

    service = MultiCandidateWorkspaceRewriteService(
        history_service=history_service,
        workflow=workflow,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    result = service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=_request(),
        candidate_count=2,
        explicit_protected_terms=(
            ExplicitProtectedTerm(
                text="Project Atlas",
                case_sensitive=True,
            ),
        ),
    )

    selected_id = result.selection.selected_candidate_id

    selected_control = next(
        control for control in result.controls if control.candidate_id == selected_id
    )

    assert result.selected_claim_lock_validation == selected_control.claim_lock_validation


def test_multi_candidate_service_keeps_original_request_tone_for_history() -> None:
    workspace_service, history_service, workflow = _services()

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )
    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Workspace",
    )

    request = _request()

    service = MultiCandidateWorkspaceRewriteService(
        history_service=history_service,
        workflow=workflow,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    result = service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=request,
        candidate_count=2,
    )

    assert result.history.tone == request.tone

    assert all(candidate_request.tone != request.tone for candidate_request in workflow.requests)
