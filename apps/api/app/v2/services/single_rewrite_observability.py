from __future__ import annotations

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
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
from app.v2.services.observability_recording_service import (
    ObservabilityRecordingService,
    ObservabilityRecordInput,
)


class SingleRewriteObservability:
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
        response: RewriteResponse,
        history: RewriteHistoryRecord,
        claim_lock_validation: (ClaimLockValidationResult),
        duration_ms: float,
    ) -> PersistentObservabilityEvent:
        provider_execution_count = int(response.rewrite_necessity.provider_required)

        provider_name = (
            response.provider_execution.actual_provider_name if provider_execution_count else None
        )

        usage = response.provider_execution.usage

        input_tokens = usage.input_tokens if usage.input_tokens is not None else 0

        output_tokens = usage.output_tokens if usage.output_tokens is not None else 0

        command = ObservabilityRecordInput(
            workspace_id=workspace_id,
            user_id=user_id,
            operation=(ObservabilityOperation.SINGLE_REWRITE),
            outcome=(ObservabilityOutcome.SUCCEEDED),
            duration_ms=duration_ms,
            input_char_count=len(request.text),
            output_char_count=len(response.rewritten_text),
            provider_execution_count=(provider_execution_count),
            provider_name=provider_name,
            fallback_used=(response.provider_execution.fallback_used),
            token_usage=(
                ObservabilityTokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=(input_tokens + output_tokens),
                )
            ),
            v1_release_decision=(_map_release_decision(response.verification.decision)),
            claim_lock_decision=(_map_claim_lock_decision(claim_lock_validation.decision)),
            rewrite_history_id=(history.rewrite_id),
        )

        return self._recording_service.record(command)


def _map_release_decision(
    decision: ReleaseDecision,
) -> ObservabilityControlDecision:
    return ObservabilityControlDecision(decision.value)


def _map_claim_lock_decision(
    decision: ClaimLockValidationDecision,
) -> ObservabilityControlDecision:
    return ObservabilityControlDecision(decision.value)
