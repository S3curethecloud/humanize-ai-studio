from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import Settings
from app.v2.repositories.eval_dataset import (
    EvaluationDatasetRepository,
)
from app.v2.repositories.eval_run import (
    EvaluationRunRepository,
)
from app.v2.repositories.provider_catalog import (
    ProviderCatalogRepository,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)
from app.v2.services.eval_ops_factory import (
    EvaluationOpsRuntime,
    build_evaluation_ops_runtime,
)
from app.v2.services.governed_eval_quality_gate_service import (
    GovernedEvaluationQualityGateService,
)
from app.v2.services.governed_eval_run_execution_service import (
    GovernedEvaluationRunExecutionService,
)


@dataclass(
    frozen=True,
    slots=True,
)
class GovernedEvaluationOpsRuntime:
    raw: EvaluationOpsRuntime
    run_execution: GovernedEvaluationRunExecutionService
    quality_gate: GovernedEvaluationQualityGateService


def build_governed_evaluation_ops_runtime(
    *,
    settings: Settings,
    catalog: ProviderCatalogRepository,
    datasets: EvaluationDatasetRepository,
    runs: EvaluationRunRepository,
    evidence: EvaluationEvidenceService,
) -> GovernedEvaluationOpsRuntime:
    raw = build_evaluation_ops_runtime(
        settings=settings,
        catalog=catalog,
        datasets=datasets,
        runs=runs,
    )

    governed_run_execution = (
        GovernedEvaluationRunExecutionService(
            execution=raw.run_execution,
            evidence=evidence,
        )
    )

    governed_quality_gate = (
        GovernedEvaluationQualityGateService(
            quality_gate=raw.quality_gate,
            runs=runs,
            evidence=evidence,
        )
    )

    return GovernedEvaluationOpsRuntime(
        raw=raw,
        run_execution=governed_run_execution,
        quality_gate=governed_quality_gate,
    )
