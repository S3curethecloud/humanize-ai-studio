from __future__ import annotations

from datetime import UTC, datetime

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
from app.v2.repositories.routing_eval_evidence import (
    InMemoryEvaluationEvidenceRepository,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)
from app.v2.services.eval_ops_factory import (
    EvaluationOpsRuntime,
)
from app.v2.services.governed_eval_ops_runtime_factory import (
    GovernedEvaluationOpsRuntime,
    build_governed_evaluation_ops_runtime,
)
from app.v2.services.governed_eval_quality_gate_service import (
    GovernedEvaluationQualityGateService,
)
from app.v2.services.governed_eval_run_execution_service import (
    GovernedEvaluationRunExecutionService,
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
        dataset_id="governed-runtime-suite",
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
                        "This is a clear deterministic "
                        "evaluation sentence."
                    ),
                ),
            ),
        ),
    )


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        22,
        0,
        tzinfo=UTC,
    )


def _dependencies():
    catalog = InMemoryProviderCatalogRepository()
    catalog.create(_target())

    datasets = (
        InMemoryEvaluationDatasetRepository()
    )
    datasets.create(_dataset())

    runs = InMemoryEvaluationRunRepository()

    evidence_repository = (
        InMemoryEvaluationEvidenceRepository()
    )
    evidence = EvaluationEvidenceService(
        repository=evidence_repository,
    )

    return (
        catalog,
        datasets,
        runs,
        evidence_repository,
        evidence,
    )


def test_factory_composes_raw_and_governed_authorities() -> None:
    (
        catalog,
        datasets,
        runs,
        _,
        evidence,
    ) = _dependencies()

    runtime = build_governed_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
        evidence=evidence,
    )

    assert isinstance(
        runtime,
        GovernedEvaluationOpsRuntime,
    )
    assert isinstance(
        runtime.raw,
        EvaluationOpsRuntime,
    )
    assert isinstance(
        runtime.run_execution,
        GovernedEvaluationRunExecutionService,
    )
    assert isinstance(
        runtime.quality_gate,
        GovernedEvaluationQualityGateService,
    )


def test_governed_runtime_records_run_evidence() -> None:
    (
        catalog,
        datasets,
        runs,
        evidence_repository,
        evidence,
    ) = _dependencies()

    runtime = build_governed_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
        evidence=evidence,
    )

    run = runtime.run_execution.execute(
        evidence_id="runtime-run-evidence",
        request=EvaluationRunRequest(
            run_id="runtime-run",
            dataset=_dataset_identity(),
            target_id="deterministic-eval",
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(),
    )

    assert runs.get(
        "runtime-run"
    ) == run

    record = evidence_repository.get(
        "runtime-run-evidence"
    )
    assert record is not None
    assert record.run == run
    assert record.gate_result is None


def test_governed_runtime_records_gate_evidence() -> None:
    (
        catalog,
        datasets,
        runs,
        evidence_repository,
        evidence,
    ) = _dependencies()

    runtime = build_governed_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
        evidence=evidence,
    )

    run = runtime.run_execution.execute(
        evidence_id="runtime-run-before-gate",
        request=EvaluationRunRequest(
            run_id="runtime-gate-run",
            dataset=_dataset_identity(),
            target_id="deterministic-eval",
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(),
    )

    gate = EvaluationQualityGate(
        gate_id="runtime-governed-gate",
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
    )

    result = runtime.quality_gate.evaluate(
        evidence_id="runtime-gate-evidence",
        gate=gate,
        run_id=run.identity.run_id,
        observed_at=_observed_at(),
    )

    assert (
        result.decision
        is EvaluationGateDecision.PASSED
    )

    record = evidence_repository.get(
        "runtime-gate-evidence"
    )
    assert record is not None
    assert record.run == run
    assert record.gate_result == result


def test_factory_reuses_injected_run_repository() -> None:
    (
        catalog,
        datasets,
        runs,
        _,
        evidence,
    ) = _dependencies()

    runtime = build_governed_evaluation_ops_runtime(
        settings=_settings(),
        catalog=catalog,
        datasets=datasets,
        runs=runs,
        evidence=evidence,
    )

    run = runtime.run_execution.execute(
        evidence_id="shared-run-evidence",
        request=EvaluationRunRequest(
            run_id="shared-run",
            dataset=_dataset_identity(),
            target_id="deterministic-eval",
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(),
    )

    stored = runs.get(
        "shared-run"
    )

    assert stored == run

    result = runtime.quality_gate.evaluate(
        evidence_id="shared-gate-evidence",
        gate=EvaluationQualityGate(
            gate_id="shared-gate",
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
        run_id="shared-run",
        observed_at=_observed_at(),
    )

    assert result.run_id == stored.identity.run_id
