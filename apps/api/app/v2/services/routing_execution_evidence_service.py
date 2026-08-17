from __future__ import annotations

from datetime import datetime

from app.v2.domain.provider_routing import (
    RoutingDecision,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceAttemptOutcome,
    RoutingEvidenceExecutionOutcome,
    RoutingEvidenceRecord,
    RoutingExecutionAttemptEvidence,
)
from app.v2.repositories.routing_eval_evidence import (
    RoutingEvidenceRepository,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderExecutionAttempt,
    ProviderExecutionAttemptOutcome,
    ProviderRoutingExecutionOutcome,
    ProviderRoutingExecutionResult,
)


class RoutingExecutionEvidenceIntegrityError(RuntimeError):
    pass


class RoutingExecutionEvidenceService:
    def __init__(
        self,
        *,
        repository: RoutingEvidenceRepository,
    ) -> None:
        self._repository = repository

    def record(
        self,
        *,
        evidence_id: str,
        policy: RoutingPolicy,
        decision: RoutingDecision,
        outcome: ProviderRoutingExecutionOutcome,
        observed_at: datetime,
    ) -> RoutingEvidenceRecord:
        self._require_outcome_identity(
            decision=decision,
            outcome=outcome,
        )

        attempts = tuple(
            _to_attempt_evidence(attempt)
            for attempt in outcome.attempts
        )

        if isinstance(
            outcome,
            ProviderRoutingExecutionResult,
        ):
            record = RoutingEvidenceRecord(
                evidence_id=evidence_id,
                policy=policy,
                decision=decision,
                execution_outcome=(
                    RoutingEvidenceExecutionOutcome.SUCCEEDED
                ),
                executed_target_id=(
                    outcome.executed_target_id
                ),
                execution_fallback_used=(
                    outcome.execution_fallback_used
                ),
                attempts=attempts,
                observed_at=observed_at,
            )
        else:
            record = RoutingEvidenceRecord(
                evidence_id=evidence_id,
                policy=policy,
                decision=decision,
                execution_outcome=(
                    RoutingEvidenceExecutionOutcome.FAILED
                ),
                execution_fallback_used=(
                    len(outcome.attempts) > 1
                ),
                attempts=attempts,
                observed_at=observed_at,
            )

        return self._repository.create(record)

    @staticmethod
    def _require_outcome_identity(
        *,
        decision: RoutingDecision,
        outcome: ProviderRoutingExecutionOutcome,
    ) -> None:
        if decision.selected_target_id is None:
            raise RoutingExecutionEvidenceIntegrityError(
                "routing execution evidence requires "
                "a selected routing decision"
            )

        if (
            outcome.initial_target_id
            != decision.selected_target_id
        ):
            raise RoutingExecutionEvidenceIntegrityError(
                "routing execution outcome initial target "
                "must match the selected routing target"
            )


def _to_attempt_evidence(
    attempt: ProviderExecutionAttempt,
) -> RoutingExecutionAttemptEvidence:
    if (
        attempt.outcome
        is ProviderExecutionAttemptOutcome.SUCCEEDED
    ):
        return RoutingExecutionAttemptEvidence(
            target_id=attempt.target_id,
            outcome=(
                RoutingEvidenceAttemptOutcome.SUCCEEDED
            ),
        )

    return RoutingExecutionAttemptEvidence(
        target_id=attempt.target_id,
        outcome=(
            RoutingEvidenceAttemptOutcome.PROVIDER_ERROR
        ),
        failure_category=attempt.failure_category,
    )
