from __future__ import annotations

import pytest
from pydantic import ValidationError

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


def _dataset() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="rewrite-regression",
        dataset_version="2026-08-16",
    )


def _run_identity() -> EvaluationRunIdentity:
    return EvaluationRunIdentity(
        run_id="run-001",
        dataset=_dataset(),
        target_id="cloudflare-primary",
    )


def _claim_result(
    value: float = 0.99,
) -> EvaluationMetricResult:
    return EvaluationMetricResult(
        metric=EvaluationMetric.CLAIM_PRESERVATION,
        value=value,
    )


def _latency_result(
    value: float = 800.0,
) -> EvaluationMetricResult:
    return EvaluationMetricResult(
        metric=EvaluationMetric.LATENCY_MS,
        value=value,
    )


def _gate() -> EvaluationQualityGate:
    return EvaluationQualityGate(
        gate_id="production-promotion",
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.98,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.LATENCY_MS,
                comparator=EvaluationComparator.AT_MOST,
                threshold=1000.0,
            ),
        ),
    )


def test_dataset_identity_is_versioned() -> None:
    dataset = _dataset()

    assert dataset.dataset_id == "rewrite-regression"
    assert dataset.dataset_version == "2026-08-16"
    assert dataset.eval_version == "eval-ops-v1"


def test_run_identity_binds_dataset_and_target() -> None:
    identity = _run_identity()

    assert identity.dataset == _dataset()
    assert identity.target_id == "cloudflare-primary"


def test_successful_run_requires_evaluated_cases() -> None:
    with pytest.raises(
        ValidationError,
        match="at least one evaluated case",
    ):
        EvaluationRunRecord(
            identity=_run_identity(),
            outcome=EvaluationRunOutcome.SUCCEEDED,
            evaluated_case_count=0,
            failed_case_count=0,
            metric_results=(_claim_result(),),
        )


def test_successful_run_requires_metrics() -> None:
    with pytest.raises(
        ValidationError,
        match="requires metric results",
    ):
        EvaluationRunRecord(
            identity=_run_identity(),
            outcome=EvaluationRunOutcome.SUCCEEDED,
            evaluated_case_count=10,
            failed_case_count=0,
        )


def test_successful_run_cannot_have_failure_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain failure_reason",
    ):
        EvaluationRunRecord(
            identity=_run_identity(),
            outcome=EvaluationRunOutcome.SUCCEEDED,
            evaluated_case_count=10,
            failed_case_count=0,
            metric_results=(_claim_result(),),
            failure_reason="unexpected",
        )


def test_failed_run_requires_failure_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="requires failure_reason",
    ):
        EvaluationRunRecord(
            identity=_run_identity(),
            outcome=EvaluationRunOutcome.FAILED,
            evaluated_case_count=2,
            failed_case_count=1,
        )


def test_failed_case_count_cannot_exceed_evaluated_cases() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot exceed",
    ):
        EvaluationRunRecord(
            identity=_run_identity(),
            outcome=EvaluationRunOutcome.FAILED,
            evaluated_case_count=2,
            failed_case_count=3,
            failure_reason="provider failure",
        )


def test_run_metrics_must_be_unique() -> None:
    with pytest.raises(
        ValidationError,
        match="metric results must be unique",
    ):
        EvaluationRunRecord(
            identity=_run_identity(),
            outcome=EvaluationRunOutcome.SUCCEEDED,
            evaluated_case_count=10,
            failed_case_count=0,
            metric_results=(
                _claim_result(),
                _claim_result(0.98),
            ),
        )


def test_successful_run_accepts_metric_evidence() -> None:
    record = EvaluationRunRecord(
        identity=_run_identity(),
        outcome=EvaluationRunOutcome.SUCCEEDED,
        evaluated_case_count=100,
        failed_case_count=0,
        metric_results=(
            _claim_result(),
            _latency_result(),
        ),
    )

    assert record.evaluated_case_count == 100
    assert len(record.metric_results) == 2


def test_quality_gate_requires_at_least_one_threshold() -> None:
    with pytest.raises(ValidationError):
        EvaluationQualityGate(
            gate_id="gate",
            thresholds=(),
        )


def test_quality_gate_metrics_must_be_unique() -> None:
    with pytest.raises(
        ValidationError,
        match="gate metrics must be unique",
    ):
        EvaluationQualityGate(
            gate_id="gate",
            thresholds=(
                EvaluationThreshold(
                    metric=EvaluationMetric.NATURALNESS,
                    comparator=EvaluationComparator.AT_LEAST,
                    threshold=0.8,
                ),
                EvaluationThreshold(
                    metric=EvaluationMetric.NATURALNESS,
                    comparator=EvaluationComparator.AT_LEAST,
                    threshold=0.9,
                ),
            ),
        )


def test_gate_passes_when_all_thresholds_pass() -> None:
    result = EvaluationGateResult(
        gate=_gate(),
        run_id="run-001",
        decision=EvaluationGateDecision.PASSED,
        metric_results=(
            _claim_result(0.99),
            _latency_result(900.0),
        ),
    )

    assert result.decision is EvaluationGateDecision.PASSED


def test_at_least_threshold_is_inclusive() -> None:
    result = EvaluationGateResult(
        gate=_gate(),
        run_id="run-001",
        decision=EvaluationGateDecision.PASSED,
        metric_results=(
            _claim_result(0.98),
            _latency_result(1000.0),
        ),
    )

    assert result.decision is EvaluationGateDecision.PASSED


def test_gate_fails_when_at_least_threshold_misses() -> None:
    result = EvaluationGateResult(
        gate=_gate(),
        run_id="run-001",
        decision=EvaluationGateDecision.FAILED,
        metric_results=(
            _claim_result(0.97),
            _latency_result(900.0),
        ),
    )

    assert result.decision is EvaluationGateDecision.FAILED


def test_gate_fails_when_at_most_threshold_misses() -> None:
    result = EvaluationGateResult(
        gate=_gate(),
        run_id="run-001",
        decision=EvaluationGateDecision.FAILED,
        metric_results=(
            _claim_result(0.99),
            _latency_result(1001.0),
        ),
    )

    assert result.decision is EvaluationGateDecision.FAILED


def test_gate_decision_cannot_contradict_metrics() -> None:
    with pytest.raises(
        ValidationError,
        match="decision does not match",
    ):
        EvaluationGateResult(
            gate=_gate(),
            run_id="run-001",
            decision=EvaluationGateDecision.PASSED,
            metric_results=(
                _claim_result(0.50),
                _latency_result(900.0),
            ),
        )


def test_gate_result_requires_exact_metric_set() -> None:
    with pytest.raises(
        ValidationError,
        match="must exactly match",
    ):
        EvaluationGateResult(
            gate=_gate(),
            run_id="run-001",
            decision=EvaluationGateDecision.PASSED,
            metric_results=(
                _claim_result(),
            ),
        )


def test_gate_result_rejects_duplicate_metrics() -> None:
    with pytest.raises(
        ValidationError,
        match="metric results must be unique",
    ):
        EvaluationGateResult(
            gate=_gate(),
            run_id="run-001",
            decision=EvaluationGateDecision.FAILED,
            metric_results=(
                _claim_result(),
                _claim_result(0.50),
            ),
        )


def test_domain_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvaluationDatasetIdentity(
            dataset_id="dataset",
            dataset_version="v1",
            unexpected=True,
        )
