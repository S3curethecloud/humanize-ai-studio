from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.candidate_generation import (
    CandidateGenerationPlan,
    CandidateGenerationVariant,
)
from app.v2.domain.rewrite_candidates import (
    RewriteCandidate,
    RewriteCandidateSet,
)


class RewriteWorkflowExecutor(Protocol):
    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse: ...


class CandidateGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CandidateGenerationExecution:
    plan: CandidateGenerationPlan
    candidate_set: RewriteCandidateSet
    responses: tuple[
        RewriteResponse,
        ...,
    ]


class CandidateRewriteOrchestrator:
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
        plan: CandidateGenerationPlan,
    ) -> CandidateGenerationExecution:
        responses: list[RewriteResponse] = []
        candidates: list[RewriteCandidate] = []
        rewritten_outputs: set[str] = set()

        for variant in plan.variants:
            candidate_request = request.model_copy(
                update={
                    "tone": self._candidate_tone(
                        original_tone=request.tone,
                        variant=variant,
                    )
                }
            )

            response = self._workflow.execute(candidate_request)

            if response.source_text != request.text:
                raise CandidateGenerationError(
                    "candidate workflow response source text does not match the original request"
                )

            if response.rewritten_text in rewritten_outputs:
                raise CandidateGenerationError(
                    "candidate generation produced duplicate rewritten outputs"
                )

            rewritten_outputs.add(response.rewritten_text)
            responses.append(response)

            candidates.append(
                RewriteCandidate(
                    candidate_id=variant.candidate_id,
                    ordinal=variant.ordinal,
                    rewritten_text=(response.rewritten_text),
                )
            )

        candidate_set = RewriteCandidateSet(
            candidate_set_id=plan.candidate_set_id,
            source_text=request.text,
            candidates=tuple(candidates),
        )

        return CandidateGenerationExecution(
            plan=plan,
            candidate_set=candidate_set,
            responses=tuple(responses),
        )

    @staticmethod
    def _candidate_tone(
        *,
        original_tone: str,
        variant: CandidateGenerationVariant,
    ) -> str:
        return (
            f"{original_tone}\n\n"
            "CANDIDATE GENERATION DIRECTIVE "
            f"({variant.strategy.value}):\n"
            f"{variant.instruction}"
        )
