from __future__ import annotations

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
from app.v2.services.candidate_control_enforcement import (
    CandidateClaimLockViolationError,
    ControlledCandidateGenerationExecution,
    ControlledCandidateRewriteOrchestrator,
)
from app.v2.services.candidate_generation_planner import (
    CandidateGenerationPlanner,
)
from app.v2.services.candidate_rewrite_orchestrator import (
    CandidateRewriteOrchestrator,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockCheckStatus,
    ClaimLockValidationDecision,
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


def _response(
    *,
    source_text: str,
    rewritten_text: str,
    trace_id: str,
    release_decision: ReleaseDecision,
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
            decision=release_decision,
            preserved_facts=[],
            missing_facts=[],
            unexpected_facts=[],
            warnings=[],
        ),
    )


class ControlledRecordingWorkflow:
    def __init__(
        self,
        *,
        outputs: tuple[
            tuple[
                str,
                ReleaseDecision,
            ],
            ...,
        ],
    ) -> None:
        self.requests: list[RewriteRequest] = []
        self._outputs = outputs

    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        del trace_id

        index = len(self.requests)

        if index >= len(self._outputs):
            raise AssertionError("workflow received more candidate executions than expected")

        self.requests.append(request)

        rewritten_text, release_decision = self._outputs[index]

        return _response(
            source_text=request.text,
            rewritten_text=rewritten_text,
            trace_id=f"trace-{index + 1}",
            release_decision=release_decision,
        )


def _explicit_atlas_term() -> tuple[
    ExplicitProtectedTerm,
    ...,
]:
    return (
        ExplicitProtectedTerm(
            text="Project Atlas",
            case_sensitive=True,
        ),
    )


def _execute(
    *,
    outputs: tuple[
        tuple[
            str,
            ReleaseDecision,
        ],
        ...,
    ],
    mode: ClaimLockEnforcementMode,
) -> ControlledCandidateGenerationExecution:
    request = _request()

    plan = CandidateGenerationPlanner().plan(
        request=request,
        candidate_count=len(outputs),
    )

    workflow = ControlledRecordingWorkflow(
        outputs=outputs,
    )

    candidate_orchestrator = CandidateRewriteOrchestrator(
        workflow=workflow,
    )

    controlled = ControlledCandidateRewriteOrchestrator(
        candidate_orchestrator=(candidate_orchestrator)
    )

    return controlled.execute(
        request=request,
        plan=plan,
        explicit_protected_terms=(_explicit_atlas_term()),
        claim_lock_enforcement_mode=mode,
    )


def test_each_candidate_receives_independent_v1_and_claim_lock_evidence() -> None:
    result = _execute(
        outputs=(
            (
                "Project Atlas completed the review. Revenue was 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
            (
                "Revenue was 42 million in 2025. Project Atlas finished the review.",
                ReleaseDecision.WARN,
            ),
        ),
        mode=ClaimLockEnforcementMode.STRICT,
    )

    assert len(result.controls) == 2

    assert tuple(control.v1_release_decision for control in result.controls) == (
        ReleaseDecision.PASS,
        ReleaseDecision.WARN,
    )

    assert all(
        (control.claim_lock_validation.decision is ClaimLockValidationDecision.PASS)
        for control in result.controls
    )


def test_strict_claim_lock_violation_fails_closed_for_v1_pass() -> None:
    with pytest.raises(
        CandidateClaimLockViolationError,
    ) as exc_info:
        _execute(
            outputs=(
                (
                    "Revenue was 42 million in 2025. The project completed the review.",
                    ReleaseDecision.PASS,
                ),
                (
                    "Project Atlas completed the review. Revenue was 42 million in 2025.",
                    ReleaseDecision.PASS,
                ),
            ),
            mode=ClaimLockEnforcementMode.STRICT,
        )

    error = exc_info.value

    assert len(error.violating_candidate_ids) == 1

    violating_controls = tuple(
        control
        for control in error.controls
        if control.candidate_id in error.violating_candidate_ids
    )

    assert len(violating_controls) == 1
    assert (
        violating_controls[0].claim_lock_validation.decision
        is ClaimLockValidationDecision.VIOLATION
    )


def test_strict_claim_lock_violation_fails_closed_for_v1_warn() -> None:
    with pytest.raises(
        CandidateClaimLockViolationError,
    ):
        _execute(
            outputs=(
                (
                    "Revenue was 42 million in 2025. The project completed the review.",
                    ReleaseDecision.WARN,
                ),
                (
                    "Project Atlas completed the review. Revenue was 42 million in 2025.",
                    ReleaseDecision.PASS,
                ),
            ),
            mode=ClaimLockEnforcementMode.STRICT,
        )


def test_v1_fail_remains_authoritative_over_strict_claim_lock_violation() -> None:
    result = _execute(
        outputs=(
            (
                "Revenue changed. The project completed the review.",
                ReleaseDecision.FAIL,
            ),
            (
                "Project Atlas completed the review. Revenue was 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
        ),
        mode=ClaimLockEnforcementMode.STRICT,
    )

    first = result.controls[0]

    assert first.v1_release_decision is ReleaseDecision.FAIL
    assert first.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION
    assert first.v1_failed is True
    assert first.claim_lock_violated is True


def test_audit_only_violation_is_observable_without_overriding_v1_pass() -> None:
    result = _execute(
        outputs=(
            (
                "Revenue was 42 million in 2025. The project completed the review.",
                ReleaseDecision.PASS,
            ),
            (
                "Project Atlas completed the review. Revenue was 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
        ),
        mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
    )

    first = result.controls[0]

    assert first.v1_release_decision is ReleaseDecision.PASS
    assert first.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION


def test_audit_only_violation_does_not_override_v1_warn() -> None:
    result = _execute(
        outputs=(
            (
                "Revenue was 42 million in 2025. The project completed the review.",
                ReleaseDecision.WARN,
            ),
            (
                "Project Atlas completed the review. Revenue was 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
        ),
        mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
    )

    first = result.controls[0]

    assert first.v1_release_decision is ReleaseDecision.WARN
    assert first.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION


def test_same_claim_lock_is_applied_to_every_candidate() -> None:
    result = _execute(
        outputs=(
            (
                "Project Atlas completed the review. Revenue was 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
            (
                "Revenue was 42 million in 2025. Project Atlas finished the review.",
                ReleaseDecision.PASS,
            ),
            (
                "Project Atlas finished its review. Revenue remained 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
        ),
        mode=ClaimLockEnforcementMode.STRICT,
    )

    lock = result.claim_lock_preparation.claim_lock

    assert lock is not None

    assert all(
        (control.claim_lock_validation.lock_id == lock.lock_id) for control in result.controls
    )


def test_protected_values_are_validated_per_candidate() -> None:
    with pytest.raises(
        CandidateClaimLockViolationError,
    ) as exc_info:
        _execute(
            outputs=(
                (
                    "Project Atlas completed the review. Revenue was 41 million in 2025.",
                    ReleaseDecision.PASS,
                ),
                (
                    "Project Atlas completed the review. Revenue was 42 million in 2025.",
                    ReleaseDecision.PASS,
                ),
            ),
            mode=ClaimLockEnforcementMode.STRICT,
        )

    violating_controls = tuple(
        control
        for control in exc_info.value.controls
        if control.candidate_id in exc_info.value.violating_candidate_ids
    )

    assert len(violating_controls) == 1

    missing_checks = tuple(
        check
        for check in (violating_controls[0].claim_lock_validation.checks)
        if (check.status is ClaimLockCheckStatus.MISSING)
    )

    assert any(check.expected_text == "42" for check in missing_checks)


def test_semantic_claims_remain_not_evaluated() -> None:
    result = _execute(
        outputs=(
            (
                "Project Atlas completed the review. Revenue was 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
            (
                "Revenue was 42 million in 2025. Project Atlas finished the review.",
                ReleaseDecision.PASS,
            ),
        ),
        mode=ClaimLockEnforcementMode.STRICT,
    )

    assert any(
        (check.status is ClaimLockCheckStatus.NOT_EVALUATED)
        for check in (result.controls[0].claim_lock_validation.checks)
        if check.item_type == "claim"
    )


def test_control_evidence_preserves_candidate_order() -> None:
    result = _execute(
        outputs=(
            (
                "Project Atlas completed the review. Revenue was 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
            (
                "Revenue was 42 million in 2025. Project Atlas finished the review.",
                ReleaseDecision.WARN,
            ),
            (
                "Project Atlas finished its review. Revenue remained 42 million in 2025.",
                ReleaseDecision.PASS,
            ),
        ),
        mode=ClaimLockEnforcementMode.STRICT,
    )

    assert tuple(control.candidate_id for control in result.controls) == tuple(
        candidate.candidate_id for candidate in result.generation.candidate_set.candidates
    )

    assert tuple(control.ordinal for control in result.controls) == (
        1,
        2,
        3,
    )
