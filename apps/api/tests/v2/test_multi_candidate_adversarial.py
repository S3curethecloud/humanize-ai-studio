from __future__ import annotations

from dataclasses import dataclass

import pytest

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
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.services.candidate_control_enforcement import (
    CandidateClaimLockViolationError,
)
from app.v2.services.candidate_rewrite_orchestrator import (
    CandidateGenerationError,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateWorkspaceRewriteService,
    NoEligibleCandidateError,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)


@dataclass(frozen=True)
class Scenario:
    rewritten_text: str
    verification_decision: ReleaseDecision = ReleaseDecision.PASS
    source_text_override: str | None = None
    naturalness_score: float = 0.95


class ScenarioWorkflow:
    def __init__(
        self,
        scenarios: tuple[
            Scenario,
            ...,
        ],
    ) -> None:
        self._scenarios = scenarios
        self.requests: list[RewriteRequest] = []

    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        del trace_id

        index = len(self.requests)

        if index >= len(self._scenarios):
            raise AssertionError(
                "ScenarioWorkflow received more candidate calls than configured scenarios."
            )

        scenario = self._scenarios[index]
        self.requests.append(request)

        return RewriteResponse(
            trace_id=f"trace-adversarial-{index + 1}",
            workflow_states=[
                "received",
                "ready_for_review",
            ],
            source_text=(
                scenario.source_text_override
                if scenario.source_text_override is not None
                else request.text
            ),
            rewritten_text=scenario.rewritten_text,
            provider_name="test-provider",
            model_name="test-model",
            prompt_version="test-v1",
            provider_execution=(
                ProviderExecutionEvidence(
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
                )
            ),
            rewrite_necessity=(
                RewriteNecessityEvidence(
                    decision="full_rewrite",
                    score=80,
                    provider_required=True,
                    signals=[],
                    rationale="Adversarial multi-candidate test.",
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
                    decision=EditorialQualityDecision.PASS,
                    naturalness_score=(scenario.naturalness_score),
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
                decision=(scenario.verification_decision),
                preserved_facts=[],
                missing_facts=[],
                unexpected_facts=[],
                warnings=[],
            ),
        )


@dataclass(frozen=True)
class Harness:
    workspace_service: WorkspaceService
    history_service: RewriteHistoryService
    history_repository: InMemoryRewriteHistoryRepository
    workflow: ScenarioWorkflow
    service: MultiCandidateWorkspaceRewriteService
    user_id: str
    workspace_id: str


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


def _harness(
    scenarios: tuple[
        Scenario,
        ...,
    ],
) -> Harness:
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
        workspace_service=workspace_service,
        history=history,
    )

    workflow = ScenarioWorkflow(
        scenarios,
    )

    service = MultiCandidateWorkspaceRewriteService(
        workspace_service=workspace_service,
        history_service=history_service,
        workflow=workflow,
    )

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Adversarial Workspace",
    )

    return Harness(
        workspace_service=workspace_service,
        history_service=history_service,
        history_repository=history,
        workflow=workflow,
        service=service,
        user_id=user.user_id,
        workspace_id=workspace.workspace_id,
    )


def _history(
    harness: Harness,
) -> tuple[RewriteHistoryRecord, ...]:
    return harness.history_repository.list_for_workspace(
        workspace_id=harness.workspace_id,
    )


def test_duplicate_candidate_outputs_fail_closed_without_history() -> None:
    duplicate = "Project Atlas completed the review in 2025 with revenue of 42 million."

    harness = _harness(
        (
            Scenario(
                rewritten_text=duplicate,
            ),
            Scenario(
                rewritten_text=duplicate,
            ),
        )
    )

    with pytest.raises(
        CandidateGenerationError,
        match=("candidate generation produced duplicate rewritten outputs"),
    ):
        harness.service.execute(
            workspace_id=harness.workspace_id,
            user_id=harness.user_id,
            request=_request(),
            candidate_count=2,
        )

    assert _history(harness) == ()


def test_candidate_source_mismatch_fails_closed_without_history() -> None:
    harness = _harness(
        (
            Scenario(
                rewritten_text=(
                    "Project Atlas completed the review in 2025 with revenue of 42 million."
                ),
                source_text_override=("tampered source text"),
            ),
            Scenario(
                rewritten_text=(
                    "The 2025 review for Project Atlas finished with revenue of 42 million."
                ),
            ),
        )
    )

    with pytest.raises(
        CandidateGenerationError,
        match=("candidate workflow response source text does not match the original request"),
    ):
        harness.service.execute(
            workspace_id=harness.workspace_id,
            user_id=harness.user_id,
            request=_request(),
            candidate_count=2,
        )

    assert _history(harness) == ()


def test_strict_claim_lock_violation_aborts_entire_set_without_history() -> None:
    harness = _harness(
        (
            Scenario(
                rewritten_text=("The review completed in 2025 with revenue of 42 million."),
            ),
            Scenario(
                rewritten_text=(
                    "Project Atlas completed the review in 2025 with revenue of 42 million."
                ),
            ),
        )
    )

    with pytest.raises(
        CandidateClaimLockViolationError,
    ):
        harness.service.execute(
            workspace_id=harness.workspace_id,
            user_id=harness.user_id,
            request=_request(),
            candidate_count=2,
            explicit_protected_terms=(
                ExplicitProtectedTerm(
                    text="Project Atlas",
                    case_sensitive=True,
                ),
            ),
            claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
        )

    assert _history(harness) == ()


def test_v1_failed_claim_lock_violation_does_not_override_v1_precedence() -> None:
    harness = _harness(
        (
            Scenario(
                rewritten_text=("The review completed in 2025 with revenue of 42 million."),
                verification_decision=(ReleaseDecision.FAIL),
            ),
            Scenario(
                rewritten_text=(
                    "Project Atlas completed the review in 2025 with revenue of 42 million."
                ),
                verification_decision=(ReleaseDecision.PASS),
            ),
        )
    )

    result = harness.service.execute(
        workspace_id=harness.workspace_id,
        user_id=harness.user_id,
        request=_request(),
        candidate_count=2,
        explicit_protected_terms=(
            ExplicitProtectedTerm(
                text="Project Atlas",
                case_sensitive=True,
            ),
        ),
        claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
    )

    first_control = result.controls[0]

    assert first_control.v1_release_decision is ReleaseDecision.FAIL
    assert first_control.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION

    assert result.selection.selected_candidate_id == result.candidate_set.candidates[1].candidate_id

    assert len(_history(harness)) == 1


def test_audit_only_violation_remains_eligible_but_clean_candidate_wins() -> None:
    harness = _harness(
        (
            Scenario(
                rewritten_text=("The review completed in 2025 with revenue of 42 million."),
                naturalness_score=0.99,
            ),
            Scenario(
                rewritten_text=(
                    "Project Atlas completed the review in 2025 with revenue of 42 million."
                ),
                naturalness_score=0.90,
            ),
        )
    )

    result = harness.service.execute(
        workspace_id=harness.workspace_id,
        user_id=harness.user_id,
        request=_request(),
        candidate_count=2,
        explicit_protected_terms=(
            ExplicitProtectedTerm(
                text="Project Atlas",
                case_sensitive=True,
            ),
        ),
        claim_lock_enforcement_mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
    )

    first_control = result.controls[0]
    second_control = result.controls[1]

    assert first_control.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION
    assert second_control.claim_lock_validation.decision is ClaimLockValidationDecision.PASS

    assert result.selection.selected_candidate_id == result.candidate_set.candidates[1].candidate_id

    assert (
        result.audit_snapshot.controls[0].claim_lock.decision
        is ClaimLockValidationDecision.VIOLATION
    )

    assert len(_history(harness)) == 1


def test_all_v1_failed_candidates_produce_no_selected_result_or_history() -> None:
    harness = _harness(
        (
            Scenario(
                rewritten_text=(
                    "Project Atlas completed the review "
                    "in 2025 with revenue of 42 million. "
                    "Candidate one."
                ),
                verification_decision=(ReleaseDecision.FAIL),
            ),
            Scenario(
                rewritten_text=(
                    "Project Atlas finished the review "
                    "in 2025 with revenue of 42 million. "
                    "Candidate two."
                ),
                verification_decision=(ReleaseDecision.FAIL),
            ),
        )
    )

    with pytest.raises(
        NoEligibleCandidateError,
        match=("multi-candidate rewrite produced no eligible candidate"),
    ):
        harness.service.execute(
            workspace_id=harness.workspace_id,
            user_id=harness.user_id,
            request=_request(),
            candidate_count=2,
        )

    assert _history(harness) == ()


def test_candidate_directives_do_not_mutate_original_request_contract() -> None:
    harness = _harness(
        (
            Scenario(
                rewritten_text=(
                    "Project Atlas completed the review "
                    "in 2025 with revenue of 42 million. "
                    "Candidate one."
                ),
            ),
            Scenario(
                rewritten_text=(
                    "In 2025, Project Atlas completed "
                    "the review with revenue of 42 million. "
                    "Candidate two."
                ),
            ),
        )
    )

    request = _request()
    original_dump = request.model_dump()

    harness.service.execute(
        workspace_id=harness.workspace_id,
        user_id=harness.user_id,
        request=request,
        candidate_count=2,
    )

    assert request.model_dump() == original_dump
    assert len(harness.workflow.requests) == 2

    for candidate_request in harness.workflow.requests:
        assert candidate_request.text == request.text
        assert candidate_request.document_type == request.document_type
        assert candidate_request.audience == request.audience
        assert candidate_request.intensity == request.intensity
        assert candidate_request.preserve_numbers is request.preserve_numbers
        assert candidate_request.preserve_dates is request.preserve_dates
        assert candidate_request.tone != request.tone


def test_failed_adversarial_execution_does_not_create_partial_candidate_audit() -> None:
    duplicate = "Project Atlas completed the review in 2025 with revenue of 42 million."

    harness = _harness(
        (
            Scenario(
                rewritten_text=duplicate,
            ),
            Scenario(
                rewritten_text=duplicate,
            ),
        )
    )

    with pytest.raises(
        CandidateGenerationError,
    ):
        harness.service.execute(
            workspace_id=harness.workspace_id,
            user_id=harness.user_id,
            request=_request(),
            candidate_count=2,
        )

    records = _history(harness)

    assert records == ()
