from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import Settings
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)
from app.v2.repositories.routing_eval_evidence import (
    RoutingEvidenceRepository,
)
from app.v2.services.governed_provider_routing_execution_service import (
    GovernedProviderRoutingExecutionService,
)
from app.v2.services.governed_provider_routing_service import (
    GovernedProviderRoutingService,
)
from app.v2.services.provider_execution_adapter import (
    BoundRewriteProviderExecutionAdapter,
)
from app.v2.services.provider_execution_factory import (
    build_provider_execution_adapter,
)
from app.v2.services.provider_routing_decision_service import (
    ProviderRoutingDecisionService,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderRoutingExecutionService,
)
from app.v2.services.routing_decision_evidence_service import (
    RoutingDecisionEvidenceService,
)
from app.v2.services.routing_eval_evidence_telemetry import (
    RoutingEvalEvidenceTelemetry,
)
from app.v2.services.routing_execution_evidence_service import (
    RoutingExecutionEvidenceService,
)


class ProviderRoutingRuntimeCompositionError(RuntimeError):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderRoutingRuntime:
    catalog: ProviderCatalogRepository
    execution_adapter: BoundRewriteProviderExecutionAdapter
    decision: ProviderRoutingDecisionService
    execution: ProviderRoutingExecutionService
    execution_evidence: RoutingExecutionEvidenceService
    governed_execution: GovernedProviderRoutingExecutionService
    decision_evidence: RoutingDecisionEvidenceService
    routing: GovernedProviderRoutingService


def build_provider_routing_runtime(
    *,
    settings: Settings,
    catalog: ProviderCatalogRepository,
    evidence: RoutingEvidenceRepository,
    telemetry: RoutingEvalEvidenceTelemetry | None = None,
) -> ProviderRoutingRuntime:
    _require_provisioned_catalog(catalog)

    execution_adapter = build_provider_execution_adapter(
        settings=settings,
        catalog=catalog,
    )

    decision = ProviderRoutingDecisionService(
        catalog=catalog,
    )

    execution = ProviderRoutingExecutionService(
        catalog=catalog,
        executor=execution_adapter,
    )

    execution_evidence = RoutingExecutionEvidenceService(
        repository=evidence,
        telemetry=telemetry,
    )

    governed_execution = (
        GovernedProviderRoutingExecutionService(
            execution=execution,
            evidence=execution_evidence,
        )
    )

    decision_evidence = RoutingDecisionEvidenceService(
        repository=evidence,
        telemetry=telemetry,
    )

    routing = GovernedProviderRoutingService(
        decision=decision,
        execution=governed_execution,
        non_execution_evidence=decision_evidence,
    )

    return ProviderRoutingRuntime(
        catalog=catalog,
        execution_adapter=execution_adapter,
        decision=decision,
        execution=execution,
        execution_evidence=execution_evidence,
        governed_execution=governed_execution,
        decision_evidence=decision_evidence,
        routing=routing,
    )


def _require_provisioned_catalog(
    catalog: ProviderCatalogRepository,
) -> None:
    try:
        targets = catalog.list_targets(
            enabled_only=False,
            limit=10_000,
        )
    except Exception as exc:
        raise ProviderRoutingRuntimeCompositionError(
            "provider routing runtime catalog listing failed"
        ) from exc

    if not targets:
        raise ProviderRoutingRuntimeCompositionError(
            "provider routing runtime requires a provisioned catalog"
        )
