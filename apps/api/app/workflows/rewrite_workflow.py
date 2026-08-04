from __future__ import annotations

from uuid import uuid4

from app.domain.models import (
    ProviderExecutionEvidence,
    ProviderUsageEvidence,
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

    def execute(
        self,
        request: RewriteRequest,
        *,
        trace_id: str | None = None,
    ) -> RewriteResponse:
        resolved_trace_id = trace_id or f"rewrite_{uuid4().hex}"

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

        primary_provider_name = rewrite_result.primary_provider_name or rewrite_result.provider_name

        return RewriteResponse(
            trace_id=resolved_trace_id,
            workflow_states=states,
            source_text=request.text,
            rewritten_text=rewrite_result.text,
            provider_name=rewrite_result.provider_name,
            model_name=rewrite_result.model_name,
            prompt_version=rewrite_result.prompt_version,
            provider_execution=ProviderExecutionEvidence(
                latency_ms=rewrite_result.latency_ms,
                primary_provider_name=primary_provider_name,
                actual_provider_name=rewrite_result.provider_name,
                fallback_used=rewrite_result.fallback_used,
                provider_error_category=rewrite_result.provider_error_category,
                usage=ProviderUsageEvidence(
                    input_tokens=rewrite_result.usage.input_tokens,
                    output_tokens=rewrite_result.usage.output_tokens,
                    total_tokens=rewrite_result.usage.total_tokens,
                ),
            ),
            analysis=analysis,
            protected_facts=protected_facts,
            changes=rewrite_result.changes,
            verification=verification,
        )
