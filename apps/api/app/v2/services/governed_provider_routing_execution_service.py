from __future__ import annotations

from datetime import datetime

from app.domain.models import RewriteRequest
from app.v2.domain.provider_routing import (
    RoutingDecision,
    RoutingPolicy,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderRoutingExecutionFailureResult,
    ProviderRoutingExecutionResult,
    ProviderRoutingExecutionService,
)
from app.v2.services.routing_execution_evidence_service import (
    RoutingExecutionEvidenceService,
)


class GovernedProviderRoutingExecutionService:
    def __init__(
        self,
        *,
        execution: ProviderRoutingExecutionService,
        evidence: RoutingExecutionEvidenceService,
    ) -> None:
        self._execution = execution
        self._evidence = evidence

    def execute(
        self,
        *,
        evidence_id: str,
        policy: RoutingPolicy,
        decision: RoutingDecision,
        request: RewriteRequest,
        observed_at: datetime,
    ) -> ProviderRoutingExecutionResult:
        outcome = self._execution.execute_outcome(
            policy=policy,
            decision=decision,
            request=request,
        )

        self._evidence.record(
            evidence_id=evidence_id,
            policy=policy,
            decision=decision,
            outcome=outcome,
            observed_at=observed_at,
        )

        if isinstance(
            outcome,
            ProviderRoutingExecutionFailureResult,
        ):
            raise outcome.error

        return outcome
