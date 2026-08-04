from __future__ import annotations

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
    WorkflowState,
)
from app.providers.base import RewriteProvider
from app.providers.deterministic import DeterministicRewriteProvider
from app.services.fact_extractor import FactExtractor
from app.services.pattern_analyzer import PatternAnalyzer
from app.services.verifier import RewriteVerifier


class RewriteWorkflow:
    def __init__(
        self,
        analyzer: PatternAnalyzer | None = None,
        fact_extractor: FactExtractor | None = None,
        provider: RewriteProvider | None = None,
        verifier: RewriteVerifier | None = None,
    ) -> None:
        self._analyzer = analyzer or PatternAnalyzer()
        self._fact_extractor = fact_extractor or FactExtractor()
        self._provider = provider or DeterministicRewriteProvider()
        self._verifier = verifier or RewriteVerifier()

    def execute(self, request: RewriteRequest) -> RewriteResponse:
        states = [
            WorkflowState.RECEIVED,
            WorkflowState.VALIDATED,
        ]

        protected_facts = self._fact_extractor.extract(
            request.text,
            preserve_numbers=request.preserve_numbers,
            preserve_dates=request.preserve_dates,
        )
        states.append(WorkflowState.CLAIMS_EXTRACTED)

        analysis = self._analyzer.analyze(request.text)
        states.append(WorkflowState.PATTERNS_ANALYZED)

        rewrite_result = self._provider.rewrite(request)
        states.append(WorkflowState.REWRITE_GENERATED)

        verification = self._verifier.verify(
            source_text=request.text,
            rewritten_text=rewrite_result.text,
            protected_facts=protected_facts,
        )
        states.append(WorkflowState.OUTPUT_VERIFIED)

        if verification.decision is ReleaseDecision.PASS:
            states.append(WorkflowState.READY_FOR_REVIEW)
        elif verification.decision is ReleaseDecision.WARN:
            states.append(WorkflowState.REQUIRES_REVIEW)
        else:
            states.append(WorkflowState.BLOCKED)

        return RewriteResponse(
            workflow_states=states,
            source_text=request.text,
            rewritten_text=rewrite_result.text,
            provider_name=rewrite_result.provider_name,
            model_name=rewrite_result.model_name,
            prompt_version=rewrite_result.prompt_version,
            analysis=analysis,
            protected_facts=protected_facts,
            changes=rewrite_result.changes,
            verification=verification,
        )
