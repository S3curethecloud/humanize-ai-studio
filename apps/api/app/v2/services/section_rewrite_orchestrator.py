from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.long_documents import (
    DocumentStructure,
    SectionRewriteDisposition,
    SectionRewritePlan,
    SectionRewriteResult,
)


class RewriteWorkflowExecutor(Protocol):
    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse: ...


class SectionRewriteExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class SectionRewriteExecution:
    structure: DocumentStructure
    plan: SectionRewritePlan
    results: tuple[
        SectionRewriteResult,
        ...,
    ]
    rewrite_responses: tuple[
        RewriteResponse,
        ...,
    ]


class SectionRewriteOrchestrator:
    def __init__(
        self,
        *,
        workflow: RewriteWorkflowExecutor,
    ) -> None:
        self._workflow = workflow

    def execute(
        self,
        *,
        request: RewriteRequest,
        structure: DocumentStructure,
        plan: SectionRewritePlan,
    ) -> SectionRewriteExecution:
        self._require_execution_contract(
            request=request,
            structure=structure,
            plan=plan,
        )

        results: list[SectionRewriteResult] = []
        rewrite_responses: list[RewriteResponse] = []

        for section, entry in zip(
            structure.sections,
            plan.entries,
            strict=True,
        ):
            if entry.disposition is SectionRewriteDisposition.PRESERVE:
                results.append(
                    SectionRewriteResult(
                        section_id=section.section_id,
                        ordinal=section.ordinal,
                        disposition=(SectionRewriteDisposition.PRESERVE),
                        source_text=section.source_text,
                        rewritten_text=section.source_text,
                    )
                )
                continue

            section_request = request.model_copy(
                update={
                    "text": section.source_text,
                }
            )

            response = self._workflow.execute(section_request)

            if response.source_text != section.source_text:
                raise SectionRewriteExecutionError(
                    "section workflow response source text "
                    "does not match the planned section source"
                )

            if response.verification.decision is ReleaseDecision.FAIL:
                raise SectionRewriteExecutionError("section workflow verification failed")

            rewrite_responses.append(response)

            results.append(
                SectionRewriteResult(
                    section_id=section.section_id,
                    ordinal=section.ordinal,
                    disposition=(SectionRewriteDisposition.REWRITE),
                    source_text=section.source_text,
                    rewritten_text=response.rewritten_text,
                )
            )

        if len(results) != len(structure.sections):
            raise SectionRewriteExecutionError(
                "section rewrite execution did not produce "
                "exactly one result for every document section"
            )

        return SectionRewriteExecution(
            structure=structure,
            plan=plan,
            results=tuple(results),
            rewrite_responses=tuple(rewrite_responses),
        )

    def _require_execution_contract(
        self,
        *,
        request: RewriteRequest,
        structure: DocumentStructure,
        plan: SectionRewritePlan,
    ) -> None:
        if request.text != structure.source_text:
            raise SectionRewriteExecutionError(
                "rewrite request source text must match document structure source text"
            )

        if plan.structure_id != structure.structure_id:
            raise SectionRewriteExecutionError(
                "section rewrite plan structure ID must match document structure"
            )

        if len(plan.entries) != len(structure.sections):
            raise SectionRewriteExecutionError(
                "section rewrite plan must contain exactly one entry for every document section"
            )

        expected_ids = tuple(section.section_id for section in structure.sections)

        actual_ids = tuple(entry.section_id for entry in plan.entries)

        if actual_ids != expected_ids:
            raise SectionRewriteExecutionError(
                "section rewrite plan section IDs must match document structure order"
            )

        expected_ordinals = tuple(section.ordinal for section in structure.sections)

        actual_ordinals = tuple(entry.ordinal for entry in plan.entries)

        if actual_ordinals != expected_ordinals:
            raise SectionRewriteExecutionError(
                "section rewrite plan ordinals must match document structure order"
            )

        for section, entry in zip(
            structure.sections,
            plan.entries,
            strict=True,
        ):
            if (
                not section.eligible_for_rewrite
                and entry.disposition is not SectionRewriteDisposition.PRESERVE
            ):
                raise SectionRewriteExecutionError(
                    "ineligible document sections must be preserved before execution"
                )
