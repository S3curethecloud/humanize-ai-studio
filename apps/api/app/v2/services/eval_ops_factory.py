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
from app.v2.services.eval_metric_service import (
    DeterministicEvaluationMetricService,
)
from app.v2.services.eval_provider_case_executor import (
    EvaluationProviderCaseExecutor,
)
from app.v2.services.eval_quality_gate_service import (
    EvaluationQualityGateService,
)
from app.v2.services.eval_run_execution_service import (
    EvaluationRunExecutionService,
)
from app.v2.services.provider_execution_factory import (
    build_provider_execution_adapter,
)


@dataclass(
    frozen=True,
    slots=True,
)
class EvaluationOpsRuntime:
    case_executor: EvaluationProviderCaseExecutor
    metric_service: DeterministicEvaluationMetricService
    run_execution: EvaluationRunExecutionService
    quality_gate: EvaluationQualityGateService


def build_evaluation_ops_runtime(
    *,
    settings: Settings,
    catalog: ProviderCatalogRepository,
    datasets: EvaluationDatasetRepository,
    runs: EvaluationRunRepository,
) -> EvaluationOpsRuntime:
    provider_executor = (
        build_provider_execution_adapter(
            settings=settings,
            catalog=catalog,
        )
    )

    case_executor = EvaluationProviderCaseExecutor(
        catalog=catalog,
        executor=provider_executor,
    )

    metric_service = (
        DeterministicEvaluationMetricService()
    )

    run_execution = EvaluationRunExecutionService(
        datasets=datasets,
        runs=runs,
        case_executor=case_executor,
        metrics=metric_service,
    )

    quality_gate = EvaluationQualityGateService(
        runs=runs
    )

    return EvaluationOpsRuntime(
        case_executor=case_executor,
        metric_service=metric_service,
        run_execution=run_execution,
        quality_gate=quality_gate,
    )
