from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from app.domain.models import (
    EditorialQualityDecision,
    ProviderExecutionEvidence,
    ProviderUsageEvidence,
    ReleaseDecision,
    RewriteChange,
    RewriteRequest,
    RewriteResponse,
    WorkflowState,
)
from app.providers.base import (
    ProviderUsage,
    RewriteProvider,
    RewriteProviderResult,
)
from app.providers.deterministic import DeterministicRewriteProvider
from app.services.editorial_quality import EditorialQualityEvaluator
from app.services.fact_extractor import FactExtractor
from app.services.pattern_analyzer import PatternAnalyzer
from app.services.rewrite_necessity import (
    RewriteDecision,
    RewriteNecessityAnalyzer,
    RewriteNecessityRequest,
    RewriteNecessityResult,
)
from app.services.verifier import RewriteVerifier

_BYPASS_PROVIDER_NAME = "rewrite-necessity-analyzer"
_BYPASS_PROMPT_VERSION = "rewrite-necessity-v1"


class RewriteWorkflow:
    def __init__(
        self,
        analyzer: PatternAnalyzer | None = None,
        fact_extractor: FactExtractor | None = None,
        provider: RewriteProvider | None = None,
        verifier: RewriteVerifier | None = None,
        quality_evaluator: EditorialQualityEvaluator | None = None,
        necessity_analyzer: RewriteNecessityAnalyzer | None = None,
    ) -> None:
        self._analyzer = analyzer or PatternAnalyzer()
        self._fact_extractor = fact_extractor or FactExtractor()
        self._provider = provider or DeterministicRewriteProvider()
        self._verifier = verifier or RewriteVerifier()
        self._quality_evaluator = quality_evaluator or EditorialQualityEvaluator(
            analyzer=self._analyzer
        )
        self._necessity_analyzer = necessity_analyzer or RewriteNecessityAnalyzer()

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

        necessity_started_at = perf_counter()
        necessity = self._necessity_analyzer.analyze(
            RewriteNecessityRequest(
                text=request.text,
                document_type=request.document_type.value,
                audience=request.audience,
                tone=request.tone,
                intensity=request.intensity.value,
            )
        )
        necessity_latency_ms = round(
            (perf_counter() - necessity_started_at) * 1000,
            3,
        )

        rewrite_result = self._resolve_rewrite_result(
            request=request,
            necessity=necessity,
            necessity_latency_ms=necessity_latency_ms,
        )
        states.append(WorkflowState.REWRITE_GENERATED)

        verification = self._verifier.verify(
            source_text=request.text,
            rewritten_text=rewrite_result.text,
            protected_facts=protected_facts,
        )

        editorial_quality = self._quality_evaluator.evaluate(
            source_analysis=analysis,
            rewritten_text=rewrite_result.text,
        )

        states.append(WorkflowState.OUTPUT_VERIFIED)

        if verification.decision is ReleaseDecision.FAIL:
            states.append(WorkflowState.BLOCKED)
        elif (
            verification.decision is ReleaseDecision.WARN
            or editorial_quality.decision is EditorialQualityDecision.REVIEW
        ):
            states.append(WorkflowState.REQUIRES_REVIEW)
        else:
            states.append(WorkflowState.READY_FOR_REVIEW)

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
                provider_error_category=(rewrite_result.provider_error_category),
                usage=ProviderUsageEvidence(
                    input_tokens=rewrite_result.usage.input_tokens,
                    output_tokens=rewrite_result.usage.output_tokens,
                    total_tokens=rewrite_result.usage.total_tokens,
                ),
            ),
            analysis=analysis,
            editorial_quality=editorial_quality,
            protected_facts=protected_facts,
            changes=rewrite_result.changes,
            verification=verification,
        )

    def _resolve_rewrite_result(
        self,
        *,
        request: RewriteRequest,
        necessity: RewriteNecessityResult,
        necessity_latency_ms: float,
    ) -> RewriteProviderResult:
        if necessity.decision is RewriteDecision.FULL_REWRITE:
            return self._provider.rewrite(request)

        if necessity.candidate_text is None:
            raise RuntimeError("A deterministic rewrite decision must include candidate_text.")

        if necessity.decision is RewriteDecision.NO_CHANGE:
            model_name = "deterministic-no-change"
            changes: list[RewriteChange] = []
        else:
            model_name = "deterministic-minimal-edit"
            changes = self._build_minimal_edit_changes(
                source_text=request.text,
                candidate_text=necessity.candidate_text,
            )

        return RewriteProviderResult(
            text=necessity.candidate_text,
            changes=changes,
            provider_name=_BYPASS_PROVIDER_NAME,
            model_name=model_name,
            prompt_version=_BYPASS_PROMPT_VERSION,
            latency_ms=necessity_latency_ms,
            primary_provider_name=_BYPASS_PROVIDER_NAME,
            fallback_used=False,
            provider_error_category=None,
            usage=ProviderUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            ),
        )

    def _build_minimal_edit_changes(
        self,
        *,
        source_text: str,
        candidate_text: str,
    ) -> list[RewriteChange]:
        if source_text == candidate_text:
            return []

        return [
            RewriteChange(
                change_id="necessity-change-1",
                original=source_text,
                replacement=candidate_text,
                reason=(
                    "Applied deterministic localized editorial "
                    "cleanup without invoking a generative provider."
                ),
                change_type="minimal_edit",
            )
        ]
