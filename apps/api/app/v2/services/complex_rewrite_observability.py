from __future__ import annotations

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.long_document_audit import (
    LongDocumentAuditRecord,
)
from app.v2.domain.long_documents import (
    DocumentReconstruction,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.domain.observability import (
    ObservabilityControlDecision,
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
    PersistentObservabilityEvent,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
)
from app.v2.services.long_document_control_evaluator import (
    LongDocumentControlEvaluation,
)
from app.v2.services.observability_recording_service import (
    ObservabilityRecordingService,
    ObservabilityRecordInput,
)


class MultiCandidateObservability:
    def __init__(
        self,
        *,
        recording_service: ObservabilityRecordingService,
    ) -> None:
        self._recording_service = recording_service

    def record_success(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        selected_response: RewriteResponse,
        generated_responses: tuple[
            RewriteResponse,
            ...,
        ],
        history: RewriteHistoryRecord,
        claim_lock_validation: (ClaimLockValidationResult),
        candidate_count: int,
        candidate_set_id: str,
        duration_ms: float,
    ) -> PersistentObservabilityEvent:
        provider = _provider_summary(generated_responses)

        return self._recording_service.record(
            ObservabilityRecordInput(
                workspace_id=workspace_id,
                user_id=user_id,
                operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
                outcome=(ObservabilityOutcome.SUCCEEDED),
                duration_ms=duration_ms,
                input_char_count=len(request.text),
                output_char_count=len(selected_response.rewritten_text),
                provider_execution_count=(provider.execution_count),
                provider_name=(provider.provider_name),
                fallback_used=(provider.fallback_used),
                token_usage=(provider.token_usage),
                v1_release_decision=(
                    _map_release_decision(selected_response.verification.decision)
                ),
                claim_lock_decision=(_map_claim_lock_decision(claim_lock_validation.decision)),
                candidate_count=(candidate_count),
                rewrite_history_id=(history.rewrite_id),
                candidate_set_id=(candidate_set_id),
            )
        )


class LongDocumentObservability:
    def __init__(
        self,
        *,
        recording_service: ObservabilityRecordingService,
    ) -> None:
        self._recording_service = recording_service

    def record_success(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        evaluation: LongDocumentControlEvaluation,
        reconstruction: DocumentReconstruction,
        audit: LongDocumentAuditRecord,
        duration_ms: float,
    ) -> PersistentObservabilityEvent:
        responses = evaluation.execution.rewrite_responses

        provider = _provider_summary(responses)

        return self._recording_service.record(
            ObservabilityRecordInput(
                workspace_id=workspace_id,
                user_id=user_id,
                operation=(ObservabilityOperation.LONG_DOCUMENT_REWRITE),
                outcome=(ObservabilityOutcome.SUCCEEDED),
                duration_ms=duration_ms,
                input_char_count=len(request.text),
                output_char_count=len(reconstruction.reconstructed_text),
                provider_execution_count=(provider.execution_count),
                provider_name=(provider.provider_name),
                fallback_used=(provider.fallback_used),
                token_usage=(provider.token_usage),
                v1_release_decision=(_aggregate_release_decision(responses)),
                claim_lock_decision=(
                    _map_claim_lock_decision(evaluation.claim_lock_validation.decision)
                ),
                section_count=len(evaluation.execution.structure.sections),
                long_document_audit_id=(audit.audit_id),
            )
        )


class _ProviderSummary:
    def __init__(
        self,
        *,
        execution_count: int,
        provider_name: str | None,
        fallback_used: bool,
        token_usage: ObservabilityTokenUsage,
    ) -> None:
        self.execution_count = execution_count
        self.provider_name = provider_name
        self.fallback_used = fallback_used
        self.token_usage = token_usage


def _provider_summary(
    responses: tuple[
        RewriteResponse,
        ...,
    ],
) -> _ProviderSummary:
    executed = tuple(
        response for response in responses if (response.rewrite_necessity.provider_required)
    )

    provider_names = {response.provider_execution.actual_provider_name for response in executed}

    if not provider_names:
        provider_name = None
    elif len(provider_names) == 1:
        provider_name = next(iter(provider_names))
    else:
        provider_name = "multiple"

    input_tokens = sum(
        (response.provider_execution.usage.input_tokens or 0) for response in executed
    )

    output_tokens = sum(
        (response.provider_execution.usage.output_tokens or 0) for response in executed
    )

    return _ProviderSummary(
        execution_count=len(executed),
        provider_name=provider_name,
        fallback_used=any(response.provider_execution.fallback_used for response in executed),
        token_usage=(
            ObservabilityTokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=(input_tokens + output_tokens),
            )
        ),
    )


def _aggregate_release_decision(
    responses: tuple[
        RewriteResponse,
        ...,
    ],
) -> ObservabilityControlDecision | None:
    decisions = {response.verification.decision for response in responses}

    if ReleaseDecision.FAIL in decisions:
        return ObservabilityControlDecision.FAIL

    if ReleaseDecision.WARN in decisions:
        return ObservabilityControlDecision.WARN

    if ReleaseDecision.PASS in decisions:
        return ObservabilityControlDecision.PASS

    return None


def _map_release_decision(
    decision: ReleaseDecision,
) -> ObservabilityControlDecision:
    return ObservabilityControlDecision(decision.value)


def _map_claim_lock_decision(
    decision: ClaimLockValidationDecision,
) -> ObservabilityControlDecision:
    return ObservabilityControlDecision(decision.value)
