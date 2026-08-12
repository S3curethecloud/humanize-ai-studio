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
from app.v2.domain.candidate_generation import (
    CandidateGenerationStrategy,
)
from app.v2.services.candidate_generation_planner import (
    CANDIDATE_GENERATION_PLAN_VERSION,
    CandidateGenerationPlanner,
)
from app.v2.services.candidate_rewrite_orchestrator import (
    CandidateGenerationError,
    CandidateRewriteOrchestrator,
    RewriteWorkflowExecutor,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def _request() -> RewriteRequest:
    return RewriteRequest(
        text=("Revenue was 42 million in 2025. The team completed the review."),
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
        provider_execution=ProviderExecutionEvidence(
            latency_ms=0.0,
            primary_provider_name="test-provider",
            actual_provider_name="test-provider",
            fallback_used=False,
            provider_error_category=None,
            usage=ProviderUsageEvidence(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            ),
        ),
        rewrite_necessity=RewriteNecessityEvidence(
            decision="full_rewrite",
            score=80,
            provider_required=True,
            signals=[],
            rationale="Candidate test.",
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
            naturalness_score=1.0,
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


class RecordingWorkflow:
    def __init__(
        self,
        *,
        outputs: tuple[str, ...],
    ) -> None:
        self.requests: list[RewriteRequest] = []
        self._outputs = outputs

    def execute(
        self,
        request: RewriteRequest,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        del trace_id

        index = len(self.requests)

        if index >= len(self._outputs):
            raise AssertionError("workflow received more candidate executions than expected")

        self.requests.append(request)

        return _response(
            source_text=request.text,
            rewritten_text=self._outputs[index],
            trace_id=f"trace-{index + 1}",
        )


class MismatchedSourceWorkflow(RecordingWorkflow):
    def execute(
        self,
        request: RewriteRequest,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        response = super().execute(
            request,
            trace_id,
        )

        return response.model_copy(update={"source_text": ("Unexpected source text.")})


def test_planner_is_deterministic() -> None:
    planner = CandidateGenerationPlanner()
    request = _request()

    first = planner.plan(
        request=request,
        candidate_count=3,
    )
    second = planner.plan(
        request=request,
        candidate_count=3,
    )

    assert first == second
    assert first.plan_version == CANDIDATE_GENERATION_PLAN_VERSION


@pytest.mark.parametrize(
    "candidate_count",
    (
        1,
        6,
    ),
)
def test_planner_rejects_unsupported_candidate_count(
    candidate_count: int,
) -> None:
    planner = CandidateGenerationPlanner()

    with pytest.raises(
        ValueError,
        match="between 2 and 5",
    ):
        planner.plan(
            request=_request(),
            candidate_count=candidate_count,
        )


def test_plan_has_stable_ordered_unique_variants() -> None:
    plan = CandidateGenerationPlanner().plan(
        request=_request(),
        candidate_count=5,
    )

    assert plan.candidate_count == 5
    assert tuple(variant.ordinal for variant in plan.variants) == (
        1,
        2,
        3,
        4,
        5,
    )

    assert tuple(variant.strategy for variant in plan.variants) == (
        CandidateGenerationStrategy.BALANCED,
        CandidateGenerationStrategy.CONCISE,
        CandidateGenerationStrategy.STRUCTURAL,
        CandidateGenerationStrategy.FLOW,
        CandidateGenerationStrategy.DIRECT,
    )

    assert len({variant.candidate_id for variant in plan.variants}) == 5


def test_candidate_count_changes_plan_identity() -> None:
    planner = CandidateGenerationPlanner()
    request = _request()

    two = planner.plan(
        request=request,
        candidate_count=2,
    )
    three = planner.plan(
        request=request,
        candidate_count=3,
    )

    assert two.candidate_set_id != three.candidate_set_id


def test_orchestrator_executes_one_workflow_per_variant() -> None:
    workflow = RecordingWorkflow(
        outputs=(
            "Candidate one.",
            "Candidate two.",
            "Candidate three.",
        )
    )
    request = _request()
    plan = CandidateGenerationPlanner().plan(
        request=request,
        candidate_count=3,
    )

    result = CandidateRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=request,
        plan=plan,
    )

    assert len(workflow.requests) == 3
    assert len(result.responses) == 3
    assert len(result.candidate_set.candidates) == 3


def test_orchestrator_preserves_request_constraints() -> None:
    workflow = RecordingWorkflow(
        outputs=(
            "Candidate one.",
            "Candidate two.",
        )
    )
    request = _request()
    plan = CandidateGenerationPlanner().plan(
        request=request,
        candidate_count=2,
    )

    CandidateRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=request,
        plan=plan,
    )

    assert request.tone == "natural and clear"

    for generated_request in workflow.requests:
        assert generated_request.text == request.text
        assert generated_request.document_type == request.document_type
        assert generated_request.audience == request.audience
        assert generated_request.intensity == request.intensity
        assert generated_request.preserve_numbers is request.preserve_numbers
        assert generated_request.preserve_dates is request.preserve_dates

        assert "CANDIDATE GENERATION DIRECTIVE" in generated_request.tone
        assert generated_request.tone.startswith(request.tone)


def test_orchestrator_preserves_candidate_order_and_ids() -> None:
    outputs = (
        "Candidate one.",
        "Candidate two.",
        "Candidate three.",
    )
    workflow = RecordingWorkflow(outputs=outputs)
    request = _request()
    plan = CandidateGenerationPlanner().plan(
        request=request,
        candidate_count=3,
    )

    result = CandidateRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=request,
        plan=plan,
    )

    assert result.candidate_set.candidate_set_id == plan.candidate_set_id

    assert tuple(candidate.candidate_id for candidate in result.candidate_set.candidates) == tuple(
        variant.candidate_id for variant in plan.variants
    )

    assert (
        tuple(candidate.rewritten_text for candidate in result.candidate_set.candidates) == outputs
    )


def test_orchestrator_rejects_duplicate_outputs() -> None:
    workflow = RecordingWorkflow(
        outputs=(
            "Same candidate.",
            "Same candidate.",
        )
    )
    request = _request()
    plan = CandidateGenerationPlanner().plan(
        request=request,
        candidate_count=2,
    )

    with pytest.raises(
        CandidateGenerationError,
        match="duplicate rewritten outputs",
    ):
        CandidateRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=request,
            plan=plan,
        )


def test_orchestrator_rejects_source_mismatch() -> None:
    workflow = MismatchedSourceWorkflow(
        outputs=(
            "Candidate one.",
            "Candidate two.",
        )
    )
    request = _request()
    plan = CandidateGenerationPlanner().plan(
        request=request,
        candidate_count=2,
    )

    with pytest.raises(
        CandidateGenerationError,
        match="source text does not match",
    ):
        CandidateRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=request,
            plan=plan,
        )


def test_frozen_v1_workflow_satisfies_executor_contract() -> None:
    workflow: RewriteWorkflowExecutor = RewriteWorkflow()

    assert isinstance(
        workflow,
        RewriteWorkflow,
    )
