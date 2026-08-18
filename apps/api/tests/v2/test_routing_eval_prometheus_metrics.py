from __future__ import annotations

from datetime import UTC, datetime

from app.observability.metrics import MetricsRegistry
from app.v2.domain.eval_ops import (
    EvaluationComparator,
    EvaluationDatasetIdentity,
    EvaluationGateDecision,
    EvaluationGateResult,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationQualityGate,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
    EvaluationThreshold,
)
from app.v2.domain.provider_routing import (
    FallbackPolicy,
    RoutingCandidate,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceAttemptOutcome,
    RoutingEvidenceExecutionOutcome,
    RoutingEvidenceRecord,
    RoutingExecutionAttemptEvidence,
)


def _observed_at() -> datetime:
    return datetime(
        2026,
        8,
        17,
        12,
        0,
        tzinfo=UTC,
    )


def _routing_success_with_fallback() -> RoutingEvidenceRecord:
    policy = RoutingPolicy(
        policy_id="sensitive-policy-id",
        ordered_target_ids=(
            "sensitive-target-a",
            "sensitive-target-b",
        ),
        fallback_policy=FallbackPolicy(
            enabled=True,
            failure_categories=(
                RoutingFailureCategory.TRANSPORT,
            ),
        ),
    )

    decision = RoutingDecision(
        policy_id=policy.policy_id,
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="sensitive-target-a",
        candidates=(
            RoutingCandidate(
                target_id="sensitive-target-a",
                eligible=True,
            ),
            RoutingCandidate(
                target_id="sensitive-target-b",
                eligible=True,
            ),
        ),
    )

    return RoutingEvidenceRecord(
        evidence_id="sensitive-routing-evidence-id",
        policy=policy,
        decision=decision,
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.SUCCEEDED
        ),
        executed_target_id="sensitive-target-b",
        execution_fallback_used=True,
        attempts=(
            RoutingExecutionAttemptEvidence(
                target_id="sensitive-target-a",
                outcome=(
                    RoutingEvidenceAttemptOutcome.PROVIDER_ERROR
                ),
                failure_category=(
                    RoutingFailureCategory.TRANSPORT
                ),
            ),
            RoutingExecutionAttemptEvidence(
                target_id="sensitive-target-b",
                outcome=(
                    RoutingEvidenceAttemptOutcome.SUCCEEDED
                ),
            ),
        ),
        observed_at=_observed_at(),
    )


def _evaluation_with_gate() -> EvaluationEvidenceRecord:
    metric_results = (
        EvaluationMetricResult(
            metric=EvaluationMetric.CLAIM_PRESERVATION,
            value=0.95,
        ),
        EvaluationMetricResult(
            metric=EvaluationMetric.PROVIDER_ERROR_RATE,
            value=0.0,
        ),
    )

    run = EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id="sensitive-run-id",
            dataset=EvaluationDatasetIdentity(
                dataset_id="sensitive-dataset-id",
                dataset_version="secret-version",
            ),
            target_id="sensitive-eval-target",
        ),
        outcome=EvaluationRunOutcome.SUCCEEDED,
        evaluated_case_count=10,
        failed_case_count=2,
        metric_results=metric_results,
    )

    gate = EvaluationQualityGate(
        gate_id="sensitive-gate-id",
        thresholds=(
            EvaluationThreshold(
                metric=(
                    EvaluationMetric.CLAIM_PRESERVATION
                ),
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.9,
            ),
            EvaluationThreshold(
                metric=(
                    EvaluationMetric.PROVIDER_ERROR_RATE
                ),
                comparator=EvaluationComparator.AT_MOST,
                threshold=0.1,
            ),
        ),
    )

    gate_result = EvaluationGateResult(
        gate=gate,
        run_id=run.identity.run_id,
        decision=EvaluationGateDecision.PASSED,
        metric_results=metric_results,
    )

    return EvaluationEvidenceRecord(
        evidence_id="sensitive-eval-evidence-id",
        run=run,
        gate_result=gate_result,
        observed_at=_observed_at(),
    )


def test_routing_evidence_records_low_cardinality_metrics() -> None:
    registry = MetricsRegistry()

    registry.record_routing_evidence(
        _routing_success_with_fallback()
    )

    rendered = registry.render_prometheus()

    assert (
        'humanize_v2_routing_decisions_total'
        '{status="selected",reason="primary_selected"} 1'
        in rendered
    )
    assert (
        'humanize_v2_routing_executions_total'
        '{outcome="succeeded",fallback_used="true"} 1'
        in rendered
    )
    assert (
        'humanize_v2_routing_attempts_total'
        '{outcome="provider_error",'
        'failure_category="transport"} 1'
        in rendered
    )
    assert (
        'humanize_v2_routing_attempts_total'
        '{outcome="succeeded",failure_category="none"} 1'
        in rendered
    )


def test_evaluation_evidence_records_operational_metrics() -> None:
    registry = MetricsRegistry()

    registry.record_evaluation_evidence(
        _evaluation_with_gate()
    )

    rendered = registry.render_prometheus()

    assert (
        'humanize_v2_eval_runs_total'
        '{outcome="succeeded"} 1'
        in rendered
    )
    assert (
        'humanize_v2_eval_cases_total'
        '{outcome="evaluated"} 10'
        in rendered
    )
    assert (
        'humanize_v2_eval_cases_total'
        '{outcome="failed"} 2'
        in rendered
    )
    assert (
        'humanize_v2_eval_gate_decisions_total'
        '{decision="passed"} 1'
        in rendered
    )
    assert (
        'humanize_v2_eval_metric_value_sum'
        '{metric="claim_preservation"} 0.950000000'
        in rendered
    )
    assert (
        'humanize_v2_eval_metric_value_count'
        '{metric="claim_preservation"} 1'
        in rendered
    )


def test_eval_metric_values_accumulate_as_summary() -> None:
    registry = MetricsRegistry()
    record = _evaluation_with_gate()

    registry.record_evaluation_evidence(record)
    registry.record_evaluation_evidence(record)

    rendered = registry.render_prometheus()

    assert (
        'humanize_v2_eval_metric_value_sum'
        '{metric="claim_preservation"} 1.900000000'
        in rendered
    )
    assert (
        'humanize_v2_eval_metric_value_count'
        '{metric="claim_preservation"} 2'
        in rendered
    )


def test_prometheus_output_does_not_leak_evidence_identities() -> None:
    registry = MetricsRegistry()

    registry.record_routing_evidence(
        _routing_success_with_fallback()
    )
    registry.record_evaluation_evidence(
        _evaluation_with_gate()
    )

    rendered = registry.render_prometheus()

    forbidden = (
        "sensitive-routing-evidence-id",
        "sensitive-policy-id",
        "sensitive-target-a",
        "sensitive-target-b",
        "sensitive-eval-evidence-id",
        "sensitive-run-id",
        "sensitive-dataset-id",
        "secret-version",
        "sensitive-eval-target",
        "sensitive-gate-id",
    )

    for value in forbidden:
        assert value not in rendered


def test_reset_clears_routing_and_eval_metrics() -> None:
    registry = MetricsRegistry()

    registry.record_routing_evidence(
        _routing_success_with_fallback()
    )
    registry.record_evaluation_evidence(
        _evaluation_with_gate()
    )

    registry.reset_for_tests()

    rendered = registry.render_prometheus()

    assert (
        'humanize_v2_routing_decisions_total{'
        not in rendered
    )
    assert (
        'humanize_v2_routing_executions_total{'
        not in rendered
    )
    assert (
        'humanize_v2_routing_attempts_total{'
        not in rendered
    )
    assert 'humanize_v2_eval_runs_total{' not in rendered
    assert 'humanize_v2_eval_cases_total{' not in rendered
    assert (
        'humanize_v2_eval_gate_decisions_total{'
        not in rendered
    )
    assert (
        'humanize_v2_eval_metric_value_sum{'
        not in rendered
    )
