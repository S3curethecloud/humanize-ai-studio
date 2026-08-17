from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.models import RewriteRequest
from app.v2.domain.provider_routing import (
    RoutingDecision,
    RoutingDecisionStatus,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceRecord,
)
from app.v2.services.governed_provider_routing_execution_service import (
    GovernedProviderRoutingExecutionService,
)
from app.v2.services.provider_routing_decision_service import (
    ProviderRoutingDecisionService,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderRoutingExecutionResult,
)
from app.v2.services.routing_decision_evidence_service import (
    RoutingDecisionEvidenceService,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderRoutingSelectedResult:
    decision: RoutingDecision
    execution: ProviderRoutingExecutionResult


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderRoutingNotExecutedResult:
    decision: RoutingDecision
    evidence: RoutingEvidenceRecord


ProviderRoutingRuntimeResult = (
    ProviderRoutingSelectedResult
    | ProviderRoutingNotExecutedResult
)


class GovernedProviderRoutingService:
    def __init__(
        self,
        *,
        decision: ProviderRoutingDecisionService,
        execution: GovernedProviderRoutingExecutionService,
        non_execution_evidence: RoutingDecisionEvidenceService,
    ) -> None:
        self._decision = decision
        self._execution = execution
        self._non_execution_evidence = non_execution_evidence

    def route_and_execute(
        self,
        *,
        evidence_id: str,
        policy: RoutingPolicy,
        requirement: RoutingRequirement,
        request: RewriteRequest,
        observed_at: datetime,
    ) -> ProviderRoutingRuntimeResult:
        decision = self._decision.evaluate(
            policy=policy,
            requirement=requirement,
        )

        if (
            decision.status
            is RoutingDecisionStatus.NO_ELIGIBLE_TARGET
        ):
            evidence = (
                self._non_execution_evidence.record_not_executed(
                    evidence_id=evidence_id,
                    policy=policy,
                    decision=decision,
                    observed_at=observed_at,
                )
            )

            return ProviderRoutingNotExecutedResult(
                decision=decision,
                evidence=evidence,
            )

        execution = self._execution.execute(
            evidence_id=evidence_id,
            policy=policy,
            decision=decision,
            request=request,
            observed_at=observed_at,
        )

        return ProviderRoutingSelectedResult(
            decision=decision,
            execution=execution,
        )
