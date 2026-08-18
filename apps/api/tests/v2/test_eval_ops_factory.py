from __future__ import annotations

from app.core.settings import (
    ProviderName,
    Settings,
)
from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationDataset,
    EvaluationDatasetCase,
)
from app.v2.domain.eval_execution import (
    EvaluationRunRequest,
)
from app.v2.domain.eval_ops import (
    EvaluationComparator,
    EvaluationDatasetIdentity,
    EvaluationGateDecision,
    EvaluationMetric,
    EvaluationQualityGate,
    EvaluationRunOutcome,
    EvaluationThreshold,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.repositories.eval_dataset import (
    InMemoryEvaluationDatasetRepository,
)
from app.v2.repositories.eval_run import (
    InMemoryEvaluationRunRepository,
)
from app.v2.repositories.provider_catalog import (
    InMemoryProviderCatalogRepository,
)
from app.v2.services.eval_metric_service import (
    DeterministicEvaluationMetricService,
)
from app.v2.services.eval_ops_factory import (
    EvaluationOpsRuntime,
    build_evaluation_ops_runtime,
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


def _settings() -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/test/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=False,
    )


def _target() -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id="deterministic-eval",
        provider=ProviderIdentity(
            provider_id="deterministic",
            display_name="Deterministic",
        ),
        model=ModelIdentity(
            provider_id="deterministic",
            model_id="rules-v1",
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
    )


def _dataset_identity() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="integration-suite",
        dataset_version="v1",
    )


def _dataset() -> EvaluationDataset:
    return EvaluationDataset(
        identity=_dataset_identity(),
        cases=(
            EvaluationDatasetCase(
                case_id="case-1",
                input=EvaluationCaseInput(
                    text=(
                        "This is a clear sentence "
                        "for deterministic evaluation."
                    )
                ),
            ),
        ),
    )


def _dependencies():
    catalog = InMemoryProviderCatalogRepository()
    catalog.create(_target())

    datasets = InMemoryEvaluationDatasetRepository()
    datasets.create(_dataset())

    runs = InMemoryEvaluationRunRepository()

    return catalog, datasets, runs


def test_factory_builds_complete_evalops_runtime() -> None:
    catalog, datasets, runs = _dependencies()

    runtime = build_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
    )

    assert isinstance(
        runtime,
        EvaluationOpsRuntime,
    )
    assert isinstance(
        runtime.case_executor,
        EvaluationProviderCaseExecutor,
    )
    assert isinstance(
        runtime.metric_service,
        DeterministicEvaluationMetricService,
    )
    assert isinstance(
        runtime.run_execution,
        EvaluationRunExecutionService,
    )
    assert isinstance(
        runtime.quality_gate,
        EvaluationQualityGateService,
    )


def test_runtime_executes_and_persists_exact_target_run() -> None:
    catalog, datasets, runs = _dependencies()

    runtime = build_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
    )

    record = runtime.run_execution.execute(
        EvaluationRunRequest(
            run_id="runtime-run",
            dataset=_dataset_identity(),
            target_id="deterministic-eval",
            metrics=(
                EvaluationMetric.LATENCY_MS,
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        )
    )

    assert (
        record.outcome
        is EvaluationRunOutcome.SUCCEEDED
    )
    assert (
        record.identity.target_id
        == "deterministic-eval"
    )
    assert runs.get("runtime-run") == record


def test_runtime_provider_error_rate_is_zero_on_success() -> None:
    catalog, datasets, runs = _dependencies()

    runtime = build_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
    )

    record = runtime.run_execution.execute(
        EvaluationRunRequest(
            run_id="provider-rate-run",
            dataset=_dataset_identity(),
            target_id="deterministic-eval",
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        )
    )

    assert (
        record.metric_results[0].metric
        is EvaluationMetric.PROVIDER_ERROR_RATE
    )
    assert record.metric_results[0].value == 0.0


def test_runtime_does_not_invent_naturalness() -> None:
    catalog, datasets, runs = _dependencies()

    runtime = build_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
    )

    record = runtime.run_execution.execute(
        EvaluationRunRequest(
            run_id="naturalness-run",
            dataset=_dataset_identity(),
            target_id="deterministic-eval",
            metrics=(
                EvaluationMetric.NATURALNESS,
            ),
        )
    )

    assert (
        record.outcome
        is EvaluationRunOutcome.FAILED
    )
    assert record.metric_results == ()
    assert record.failure_reason is not None
    assert "naturalness" in record.failure_reason


def test_runtime_quality_gate_reads_persisted_run() -> None:
    catalog, datasets, runs = _dependencies()

    runtime = build_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
    )

    record = runtime.run_execution.execute(
        EvaluationRunRequest(
            run_id="gate-run",
            dataset=_dataset_identity(),
            target_id="deterministic-eval",
            metrics=(
                EvaluationMetric.LATENCY_MS,
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        )
    )

    gate = EvaluationQualityGate(
        gate_id="runtime-gate",
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.LATENCY_MS,
                comparator=EvaluationComparator.AT_MOST,
                threshold=1_000_000.0,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.PROVIDER_ERROR_RATE,
                comparator=EvaluationComparator.AT_MOST,
                threshold=0.0,
            ),
        ),
    )

    result = runtime.quality_gate.evaluate(
        gate=gate,
        run_id=record.identity.run_id,
    )

    assert (
        result.decision
        is EvaluationGateDecision.PASSED
    )
    assert result.run_id == "gate-run"


def test_runtime_uses_injected_run_repository_identity() -> None:
    catalog, datasets, runs = _dependencies()

    runtime = build_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
    )

    runtime.run_execution.execute(
        EvaluationRunRequest(
            run_id="shared-repository-run",
            dataset=_dataset_identity(),
            target_id="deterministic-eval",
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        )
    )

    stored = runs.get(
        "shared-repository-run"
    )

    assert stored is not None

    result = runtime.quality_gate.evaluate(
        gate=EvaluationQualityGate(
            gate_id="shared-repository-gate",
            thresholds=(
                EvaluationThreshold(
                    metric=(
                        EvaluationMetric.PROVIDER_ERROR_RATE
                    ),
                    comparator=(
                        EvaluationComparator.AT_MOST
                    ),
                    threshold=0.0,
                ),
            ),
        ),
        run_id="shared-repository-run",
    )

    assert result.run_id == stored.identity.run_id
