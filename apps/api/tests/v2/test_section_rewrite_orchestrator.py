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
from app.v2.domain.long_documents import (
    DocumentStructure,
    SectionRewriteDisposition,
    SectionRewritePlan,
)
from app.v2.services.document_structure_detector import (
    DocumentStructureDetector,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteExecutionError,
    SectionRewriteOrchestrator,
)
from app.v2.services.section_rewrite_planner import (
    SectionRewritePlanner,
)

SOURCE = (
    "# Overview\n"
    "Project Atlas completed the review.\n"
    "\n"
    "## Financials\n"
    "Revenue was 42 million in 2025.\n"
)


def _request() -> RewriteRequest:
    return RewriteRequest(
        text=SOURCE,
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
            rationale="Section rewrite test.",
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
        outputs: tuple[str, ...],
        decisions: tuple[
            ReleaseDecision,
            ...,
        ]
        | None = None,
    ) -> None:
        self.requests: list[RewriteRequest] = []
        self._outputs = outputs
        self._decisions = decisions or tuple(ReleaseDecision.PASS for _ in outputs)

    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        del trace_id

        index = len(self.requests)

        if index >= len(self._outputs):
            raise AssertionError("workflow received more section executions than expected")

        self.requests.append(request)

        return _response(
            source_text=request.text,
            rewritten_text=self._outputs[index],
            trace_id=f"trace-{index + 1}",
            decision=self._decisions[index],
        )


class MismatchedSourceWorkflow(RecordingWorkflow):
    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        response = super().execute(
            request,
            trace_id=trace_id,
        )

        return response.model_copy(update={"source_text": ("Unexpected section source.")})


class FailingWorkflow(RecordingWorkflow):
    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        index = len(self.requests)

        if index == 1:
            raise RuntimeError("provider execution failed")

        return super().execute(
            request,
            trace_id=trace_id,
        )


def _structure() -> DocumentStructure:
    return DocumentStructureDetector().detect(
        source_text=SOURCE,
    )


def _plan() -> SectionRewritePlan:
    return SectionRewritePlanner().plan(
        structure=_structure(),
    )


def test_rewrite_entries_execute_in_section_order() -> None:
    structure = _structure()
    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    workflow = RecordingWorkflow(
        outputs=(
            "# Overview\nThe Project Atlas review is complete.\n\n",
            "## Financials\nIn 2025, revenue was 42 million.\n",
        ),
    )

    execution = SectionRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=_request(),
        structure=structure,
        plan=plan,
    )

    assert tuple(request.text for request in workflow.requests) == tuple(
        section.source_text for section in structure.sections
    )

    assert tuple(result.section_id for result in execution.results) == tuple(
        section.section_id for section in structure.sections
    )


def test_section_requests_preserve_original_request_constraints() -> None:
    structure = _structure()

    workflow = RecordingWorkflow(
        outputs=(
            "Overview rewritten.",
            "Financials rewritten.",
        ),
    )

    original = _request()

    SectionRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=original,
        structure=structure,
        plan=SectionRewritePlanner().plan(
            structure=structure,
        ),
    )

    for section, section_request in zip(
        structure.sections,
        workflow.requests,
        strict=True,
    ):
        assert section_request.text == (section.source_text)
        assert section_request.document_type == original.document_type
        assert section_request.audience == original.audience
        assert section_request.tone == original.tone
        assert section_request.intensity == original.intensity
        assert section_request.preserve_numbers == original.preserve_numbers
        assert section_request.preserve_dates == original.preserve_dates


def test_original_request_is_not_mutated() -> None:
    structure = _structure()
    request = _request()

    before = request.model_dump(
        mode="json",
    )

    workflow = RecordingWorkflow(
        outputs=(
            "Overview rewritten.",
            "Financials rewritten.",
        ),
    )

    SectionRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=request,
        structure=structure,
        plan=SectionRewritePlanner().plan(
            structure=structure,
        ),
    )

    assert (
        request.model_dump(
            mode="json",
        )
        == before
    )


def test_preserve_entry_skips_workflow_and_keeps_exact_source() -> None:
    structure = _structure()

    second = structure.sections[1].model_copy(
        update={
            "eligible_for_rewrite": False,
        }
    )

    structure = structure.model_copy(
        update={
            "sections": (
                structure.sections[0],
                second,
            ),
        }
    )

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    workflow = RecordingWorkflow(
        outputs=("Overview rewritten.",),
    )

    execution = SectionRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=_request(),
        structure=structure,
        plan=plan,
    )

    assert len(workflow.requests) == 1

    preserved = execution.results[1]

    assert preserved.disposition is SectionRewriteDisposition.PRESERVE
    assert preserved.source_text == structure.sections[1].source_text
    assert preserved.rewritten_text == structure.sections[1].source_text


def test_rewrite_response_source_mismatch_aborts() -> None:
    structure = _structure()

    workflow = MismatchedSourceWorkflow(
        outputs=(
            "Overview rewritten.",
            "Financials rewritten.",
        ),
    )

    with pytest.raises(
        SectionRewriteExecutionError,
        match="does not match the planned section source",
    ):
        SectionRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=_request(),
            structure=structure,
            plan=SectionRewritePlanner().plan(
                structure=structure,
            ),
        )


def test_v1_verification_fail_aborts_execution() -> None:
    structure = _structure()

    workflow = RecordingWorkflow(
        outputs=(
            "Overview rewritten.",
            "Financials rewritten.",
        ),
        decisions=(
            ReleaseDecision.FAIL,
            ReleaseDecision.PASS,
        ),
    )

    with pytest.raises(
        SectionRewriteExecutionError,
        match="section workflow verification failed",
    ):
        SectionRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=_request(),
            structure=structure,
            plan=SectionRewritePlanner().plan(
                structure=structure,
            ),
        )

    assert len(workflow.requests) == 1


def test_workflow_exception_aborts_remaining_sections() -> None:
    structure = _structure()

    workflow = FailingWorkflow(
        outputs=(
            "Overview rewritten.",
            "Financials rewritten.",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="provider execution failed",
    ):
        SectionRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=_request(),
            structure=structure,
            plan=SectionRewritePlanner().plan(
                structure=structure,
            ),
        )

    assert len(workflow.requests) == 1


def test_execution_returns_only_rewrite_responses() -> None:
    structure = _structure()

    second = structure.sections[1].model_copy(
        update={
            "eligible_for_rewrite": False,
        }
    )

    structure = structure.model_copy(
        update={
            "sections": (
                structure.sections[0],
                second,
            ),
        }
    )

    workflow = RecordingWorkflow(
        outputs=("Overview rewritten.",),
    )

    execution = SectionRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=_request(),
        structure=structure,
        plan=SectionRewritePlanner().plan(
            structure=structure,
        ),
    )

    assert len(execution.results) == 2
    assert len(execution.rewrite_responses) == 1


def test_request_source_mismatch_fails_before_workflow_call() -> None:
    structure = _structure()

    workflow = RecordingWorkflow(
        outputs=(),
    )

    bad_request = _request().model_copy(
        update={
            "text": "Different document.",
        }
    )

    with pytest.raises(
        SectionRewriteExecutionError,
        match="request source text must match",
    ):
        SectionRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=bad_request,
            structure=structure,
            plan=SectionRewritePlanner().plan(
                structure=structure,
            ),
        )

    assert workflow.requests == []


def test_plan_structure_id_mismatch_fails_before_workflow_call() -> None:
    structure = _structure()
    valid = SectionRewritePlanner().plan(
        structure=structure,
    )

    bad_plan = valid.model_copy(
        update={
            "structure_id": "wrong-structure",
        }
    )

    workflow = RecordingWorkflow(
        outputs=(),
    )

    with pytest.raises(
        SectionRewriteExecutionError,
        match="structure ID must match",
    ):
        SectionRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=_request(),
            structure=structure,
            plan=bad_plan,
        )

    assert workflow.requests == []


def test_plan_section_id_mismatch_fails_before_workflow_call() -> None:
    structure = _structure()
    valid = SectionRewritePlanner().plan(
        structure=structure,
    )

    first = valid.entries[0].model_copy(
        update={
            "section_id": "wrong-section",
        }
    )

    bad_plan = valid.model_copy(
        update={
            "entries": (
                first,
                valid.entries[1],
            ),
        }
    )

    workflow = RecordingWorkflow(
        outputs=(),
    )

    with pytest.raises(
        SectionRewriteExecutionError,
        match="section IDs must match",
    ):
        SectionRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=_request(),
            structure=structure,
            plan=bad_plan,
        )

    assert workflow.requests == []


def test_plan_ordinal_mismatch_fails_before_workflow_call() -> None:
    structure = _structure()
    valid = SectionRewritePlanner().plan(
        structure=structure,
    )

    first = valid.entries[0].model_copy(
        update={
            "ordinal": 2,
        }
    )

    second = valid.entries[1].model_copy(
        update={
            "ordinal": 1,
        }
    )

    bad_plan = valid.model_copy(
        update={
            "entries": (
                first,
                second,
            ),
        }
    )

    workflow = RecordingWorkflow(
        outputs=(),
    )

    with pytest.raises(
        SectionRewriteExecutionError,
        match="ordinals must match document structure order",
    ):
        SectionRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=_request(),
            structure=structure,
            plan=bad_plan,
        )

    assert workflow.requests == []


def test_ineligible_rewrite_plan_fails_before_workflow_call() -> None:
    structure = _structure()

    second = structure.sections[1].model_copy(
        update={
            "eligible_for_rewrite": False,
        }
    )

    structure = structure.model_copy(
        update={
            "sections": (
                structure.sections[0],
                second,
            ),
        }
    )

    valid = SectionRewritePlanner().plan(
        structure=structure,
    )

    forced_rewrite = valid.entries[1].model_copy(
        update={
            "disposition": (SectionRewriteDisposition.REWRITE),
            "rationale": "Tampered plan.",
        }
    )

    bad_plan = valid.model_copy(
        update={
            "entries": (
                valid.entries[0],
                forced_rewrite,
            ),
        }
    )

    workflow = RecordingWorkflow(
        outputs=(),
    )

    with pytest.raises(
        SectionRewriteExecutionError,
        match="ineligible document sections must be preserved",
    ):
        SectionRewriteOrchestrator(
            workflow=workflow,
        ).execute(
            request=_request(),
            structure=structure,
            plan=bad_plan,
        )

    assert workflow.requests == []


def test_eligible_preserve_entry_is_respected_as_plan_authority() -> None:
    structure = _structure()
    valid = SectionRewritePlanner().plan(
        structure=structure,
    )

    preserve_first = valid.entries[0].model_copy(
        update={
            "disposition": (SectionRewriteDisposition.PRESERVE),
            "rationale": "Explicit preserve plan.",
        }
    )

    plan = valid.model_copy(
        update={
            "entries": (
                preserve_first,
                valid.entries[1],
            ),
        }
    )

    workflow = RecordingWorkflow(
        outputs=("Financials rewritten.",),
    )

    execution = SectionRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=_request(),
        structure=structure,
        plan=plan,
    )

    assert len(workflow.requests) == 1
    assert workflow.requests[0].text == structure.sections[1].source_text
    assert execution.results[0].rewritten_text == structure.sections[0].source_text


def test_orchestrator_does_not_reconstruct_document() -> None:
    structure = _structure()

    workflow = RecordingWorkflow(
        outputs=(
            "Overview rewritten.",
            "Financials rewritten.",
        ),
    )

    execution = SectionRewriteOrchestrator(
        workflow=workflow,
    ).execute(
        request=_request(),
        structure=structure,
        plan=SectionRewritePlanner().plan(
            structure=structure,
        ),
    )

    assert not hasattr(
        execution,
        "reconstructed_text",
    )
