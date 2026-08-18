from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.observability.metrics import (
    MetricsRegistry,
    metrics_registry,
)
from app.providers.exceptions import (
    RewriteProviderTransportError,
)
from app.v2.api.dependencies import V2Services
from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.domain.provider_routing import (
    RoutingCandidate,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceRecord,
)
from app.v2.repositories.routing_eval_evidence import (
    InMemoryEvaluationEvidenceRepository,
    InMemoryRoutingEvidenceRepository,
)
from app.v2.services.eval_evidence_service import (
    EvaluationEvidenceService,
)
from app.v2.services.provider_routing_execution_service import (
    ProviderExecutionAttempt,
    ProviderExecutionAttemptOutcome,
    ProviderRoutingExecutionFailureResult,
)
from app.v2.services.routing_execution_evidence_service import (
    RoutingExecutionEvidenceService,
)


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        12,
        30,
        tzinfo=UTC,
    )


def _run() -> EvaluationRunRecord:
    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id="run-a",
            dataset=EvaluationDatasetIdentity(
                dataset_id="dataset-a",
                dataset_version="v1",
            ),
            target_id="target-a",
        ),
        outcome=EvaluationRunOutcome.SUCCEEDED,
        evaluated_case_count=2,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                value=0.9,
            ),
        ),
    )


def _routing_inputs() -> tuple[
    RoutingPolicy,
    RoutingDecision,
    ProviderRoutingExecutionFailureResult,
]:
    policy = RoutingPolicy(
        policy_id="policy-a",
        ordered_target_ids=("target-a",),
    )

    decision = RoutingDecision(
        policy_id=policy.policy_id,
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="target-a",
        candidates=(
            RoutingCandidate(
                target_id="target-a",
                eligible=True,
            ),
        ),
    )

    outcome = ProviderRoutingExecutionFailureResult(
        error=RewriteProviderTransportError(
            "provider transport failure"
        ),
        initial_target_id="target-a",
        attempts=(
            ProviderExecutionAttempt(
                target_id="target-a",
                outcome=(
                    ProviderExecutionAttemptOutcome.PROVIDER_ERROR
                ),
                failure_category=(
                    RoutingFailureCategory.TRANSPORT
                ),
            ),
        ),
    )

    return policy, decision, outcome


class FailingEvaluationRepository:
    def create(
        self,
        record: EvaluationEvidenceRecord,
    ) -> EvaluationEvidenceRecord:
        raise RuntimeError("persistence failed")

    def get(
        self,
        evidence_id: str,
    ) -> EvaluationEvidenceRecord | None:
        return None

    def list_records(
        self,
        *,
        run_id: str | None = None,
        dataset_id: str | None = None,
        dataset_version: str | None = None,
        target_id: str | None = None,
        run_outcome: EvaluationRunOutcome | None = None,
        gate_id: str | None = None,
        limit: int = 1000,
    ) -> tuple[EvaluationEvidenceRecord, ...]:
        return ()


class CountingTelemetry:
    def __init__(self) -> None:
        self.routing_calls = 0
        self.evaluation_calls = 0

    def record_routing_evidence(
        self,
        record: RoutingEvidenceRecord,
    ) -> None:
        self.routing_calls += 1

    def record_evaluation_evidence(
        self,
        record: EvaluationEvidenceRecord,
    ) -> None:
        self.evaluation_calls += 1


class FailingTelemetry:
    def record_routing_evidence(
        self,
        record: RoutingEvidenceRecord,
    ) -> None:
        raise RuntimeError("telemetry failed")

    def record_evaluation_evidence(
        self,
        record: EvaluationEvidenceRecord,
    ) -> None:
        raise RuntimeError("telemetry failed")


def test_routing_metrics_emit_after_durable_create() -> None:
    repository = InMemoryRoutingEvidenceRepository()
    telemetry = MetricsRegistry()

    service = RoutingExecutionEvidenceService(
        repository=repository,
        telemetry=telemetry,
    )

    policy, decision, outcome = _routing_inputs()

    persisted = service.record(
        evidence_id="routing-evidence-a",
        policy=policy,
        decision=decision,
        outcome=outcome,
        observed_at=_observed_at(),
    )

    assert (
        repository.get("routing-evidence-a")
        is persisted
    )

    rendered = telemetry.render_prometheus()

    assert (
        'humanize_v2_routing_executions_total'
        '{outcome="failed",fallback_used="false"} 1'
        in rendered
    )


def test_eval_metrics_emit_after_durable_create() -> None:
    repository = InMemoryEvaluationEvidenceRepository()
    telemetry = MetricsRegistry()

    service = EvaluationEvidenceService(
        repository=repository,
        telemetry=telemetry,
    )

    persisted = service.record_run(
        evidence_id="eval-evidence-a",
        run=_run(),
        observed_at=_observed_at(),
    )

    assert (
        repository.get("eval-evidence-a")
        is persisted
    )

    rendered = telemetry.render_prometheus()

    assert (
        'humanize_v2_eval_runs_total'
        '{outcome="succeeded"} 1'
        in rendered
    )


def test_persistence_failure_emits_no_telemetry() -> None:
    telemetry = CountingTelemetry()

    service = EvaluationEvidenceService(
        repository=FailingEvaluationRepository(),
        telemetry=telemetry,
    )

    with pytest.raises(
        RuntimeError,
        match="persistence failed",
    ):
        service.record_run(
            evidence_id="eval-evidence-a",
            run=_run(),
            observed_at=_observed_at(),
        )

    assert telemetry.evaluation_calls == 0


def test_telemetry_failure_does_not_invalidate_persistence() -> None:
    repository = InMemoryEvaluationEvidenceRepository()

    service = EvaluationEvidenceService(
        repository=repository,
        telemetry=FailingTelemetry(),
    )

    persisted = service.record_run(
        evidence_id="eval-evidence-a",
        run=_run(),
        observed_at=_observed_at(),
    )

    assert (
        repository.get("eval-evidence-a")
        is persisted
    )


def test_existing_recorder_callers_need_no_telemetry() -> None:
    repository = InMemoryEvaluationEvidenceRepository()

    service = EvaluationEvidenceService(
        repository=repository,
    )

    persisted = service.record_run(
        evidence_id="eval-evidence-a",
        run=_run(),
        observed_at=_observed_at(),
    )

    assert (
        repository.get("eval-evidence-a")
        is persisted
    )


def test_v2_runtime_injects_global_prometheus_registry() -> None:
    metrics_registry.reset_for_tests()

    try:
        services = V2Services()

        services.evaluation_evidence.record_run(
            evidence_id="runtime-eval-evidence",
            run=_run(),
            observed_at=_observed_at(),
        )

        rendered = metrics_registry.render_prometheus()

        assert (
            'humanize_v2_eval_runs_total'
            '{outcome="succeeded"} 1'
            in rendered
        )

        queried = services.evaluation_evidence_query.get(
            evidence_id="runtime-eval-evidence",
        )

        assert (
            queried.evidence_id
            == "runtime-eval-evidence"
        )
    finally:
        metrics_registry.reset_for_tests()
