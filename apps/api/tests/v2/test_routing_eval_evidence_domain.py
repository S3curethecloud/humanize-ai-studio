from __future__ import annotations

from datetime import datetime

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
from app.v2.domain.provider_routing import (
    FallbackPolicy,
    RoutingCandidate,
    RoutingCandidateIneligibilityReason,
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


def _policy() -> RoutingPolicy:
    return RoutingPolicy(
        policy_id="policy-1",
        ordered_target_ids=(
            "target-a",
            "target-b",
            "target-c",
        ),
        fallback_policy=FallbackPolicy(
            enabled=True,
            failure_categories=(
                RoutingFailureCategory.TRANSPORT,
                RoutingFailureCategory.RESPONSE,
            ),
        ),
    )


def _primary_decision() -> RoutingDecision:
    return RoutingDecision(
        policy_id="policy-1",
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="target-a",
        candidates=(
            RoutingCandidate(
                target_id="target-a",
                eligible=True,
            ),
            RoutingCandidate(
                target_id="target-b",
                eligible=True,
            ),
            RoutingCandidate(
                target_id="target-c",
                eligible=True,
            ),
        ),
    )


def _static_fallback_decision() -> RoutingDecision:
    return RoutingDecision(
        policy_id="policy-1",
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.FALLBACK_SELECTED,
        selected_target_id="target-b",
        candidates=(
            RoutingCandidate(
                target_id="target-a",
                eligible=False,
                ineligibility_reasons=(
                    RoutingCandidateIneligibilityReason.TARGET_DISABLED,
                ),
            ),
            RoutingCandidate(
                target_id="target-b",
                eligible=True,
            ),
            RoutingCandidate(
                target_id="target-c",
                eligible=True,
            ),
        ),
    )


def _no_eligible_decision() -> RoutingDecision:
    return RoutingDecision(
        policy_id="policy-1",
        status=(
            RoutingDecisionStatus.NO_ELIGIBLE_TARGET
        ),
        reason=(
            RoutingDecisionReason.NO_ELIGIBLE_TARGET
        ),
        selected_target_id=None,
        candidates=(
            RoutingCandidate(
                target_id="target-a",
                eligible=False,
                ineligibility_reasons=(
                    RoutingCandidateIneligibilityReason.TARGET_DISABLED,
                ),
            ),
            RoutingCandidate(
                target_id="target-b",
                eligible=False,
                ineligibility_reasons=(
                    RoutingCandidateIneligibilityReason.MISSING_CAPABILITY,
                ),
            ),
            RoutingCandidate(
                target_id="target-c",
                eligible=False,
                ineligibility_reasons=(
                    RoutingCandidateIneligibilityReason.EXCLUDED_BY_REQUIREMENT,
                ),
            ),
        ),
    )


def _provider_error_attempt(
    target_id: str,
) -> RoutingExecutionAttemptEvidence:
    return RoutingExecutionAttemptEvidence(
        target_id=target_id,
        outcome=(
            RoutingEvidenceAttemptOutcome.PROVIDER_ERROR
        ),
        failure_category=(
            RoutingFailureCategory.TRANSPORT
        ),
    )


def _success_attempt(
    target_id: str,
) -> RoutingExecutionAttemptEvidence:
    return RoutingExecutionAttemptEvidence(
        target_id=target_id,
        outcome=RoutingEvidenceAttemptOutcome.SUCCEEDED,
    )


def test_successful_primary_execution_evidence() -> None:
    evidence = RoutingEvidenceRecord(
        evidence_id="route-evidence-1",
        policy=_policy(),
        decision=_primary_decision(),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.SUCCEEDED
        ),
        executed_target_id="target-a",
        execution_fallback_used=False,
        attempts=(
            _success_attempt("target-a"),
        ),
    )

    assert evidence.executed_target_id == "target-a"
    assert evidence.execution_fallback_used is False


def test_execution_fallback_success_is_recorded() -> None:
    evidence = RoutingEvidenceRecord(
        evidence_id="route-evidence-2",
        policy=_policy(),
        decision=_primary_decision(),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.SUCCEEDED
        ),
        executed_target_id="target-b",
        execution_fallback_used=True,
        attempts=(
            _provider_error_attempt("target-a"),
            _success_attempt("target-b"),
        ),
    )

    assert evidence.decision.reason is (
        RoutingDecisionReason.PRIMARY_SELECTED
    )
    assert evidence.execution_fallback_used is True
    assert evidence.executed_target_id == "target-b"


def test_static_fallback_selection_is_not_execution_fallback() -> None:
    evidence = RoutingEvidenceRecord(
        evidence_id="route-evidence-3",
        policy=_policy(),
        decision=_static_fallback_decision(),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.SUCCEEDED
        ),
        executed_target_id="target-b",
        execution_fallback_used=False,
        attempts=(
            _success_attempt("target-b"),
        ),
    )

    assert evidence.decision.reason is (
        RoutingDecisionReason.FALLBACK_SELECTED
    )
    assert evidence.execution_fallback_used is False


def test_failed_execution_records_provider_attempts() -> None:
    evidence = RoutingEvidenceRecord(
        evidence_id="route-evidence-4",
        policy=_policy(),
        decision=_primary_decision(),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.FAILED
        ),
        executed_target_id=None,
        execution_fallback_used=True,
        attempts=(
            _provider_error_attempt("target-a"),
            _provider_error_attempt("target-b"),
        ),
    )

    assert evidence.executed_target_id is None
    assert len(evidence.attempts) == 2


def test_selected_decision_may_be_observed_before_execution() -> None:
    evidence = RoutingEvidenceRecord(
        evidence_id="route-evidence-5",
        policy=_policy(),
        decision=_primary_decision(),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.NOT_EXECUTED
        ),
    )

    assert evidence.attempts == ()
    assert evidence.executed_target_id is None


def test_no_eligible_target_has_no_execution() -> None:
    evidence = RoutingEvidenceRecord(
        evidence_id="route-evidence-6",
        policy=_policy(),
        decision=_no_eligible_decision(),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.NOT_EXECUTED
        ),
    )

    assert evidence.executed_target_id is None
    assert evidence.attempts == ()


def test_success_attempt_rejects_failure_category() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain failure_category",
    ):
        RoutingExecutionAttemptEvidence(
            target_id="target-a",
            outcome=(
                RoutingEvidenceAttemptOutcome.SUCCEEDED
            ),
            failure_category=(
                RoutingFailureCategory.TRANSPORT
            ),
        )


def test_provider_error_attempt_requires_category() -> None:
    with pytest.raises(
        ValidationError,
        match="requires failure_category",
    ):
        RoutingExecutionAttemptEvidence(
            target_id="target-a",
            outcome=(
                RoutingEvidenceAttemptOutcome.PROVIDER_ERROR
            ),
        )


def test_policy_identity_must_match_decision() -> None:
    decision = _primary_decision().model_copy(
        update={
            "policy_id": "different-policy",
        }
    )

    with pytest.raises(
        ValidationError,
        match="policy identity",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-7",
            policy=_policy(),
            decision=decision,
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.NOT_EXECUTED
            ),
        )


def test_policy_order_must_match_decision_candidates() -> None:
    policy = RoutingPolicy(
        policy_id="policy-1",
        ordered_target_ids=(
            "target-b",
            "target-a",
            "target-c",
        ),
        fallback_policy=_policy().fallback_policy,
    )

    with pytest.raises(
        ValidationError,
        match="candidate order",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-8",
            policy=policy,
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.NOT_EXECUTED
            ),
        )


@pytest.mark.parametrize(
    "field",
    [
        "attempts",
        "executed_target_id",
        "execution_fallback_used",
    ],
)
def test_no_eligible_target_rejects_execution_facts(
    field: str,
) -> None:
    values = {
        "evidence_id": "route-evidence-9",
        "policy": _policy(),
        "decision": _no_eligible_decision(),
        "execution_outcome": (
            RoutingEvidenceExecutionOutcome.NOT_EXECUTED
        ),
    }

    if field == "attempts":
        values[field] = (
            _provider_error_attempt("target-a"),
        )
    elif field == "executed_target_id":
        values[field] = "target-a"
    else:
        values[field] = True

    with pytest.raises(ValidationError):
        RoutingEvidenceRecord(**values)


def test_no_eligible_target_rejects_executed_outcome() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain an execution outcome",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-10",
            policy=_policy(),
            decision=_no_eligible_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.FAILED
            ),
            attempts=(
                _provider_error_attempt("target-a"),
            ),
        )


def test_not_executed_selected_decision_rejects_attempts() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain execution attempts",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-11",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.NOT_EXECUTED
            ),
            attempts=(
                _provider_error_attempt("target-a"),
            ),
        )


def test_attempts_must_start_with_selected_target() -> None:
    with pytest.raises(
        ValidationError,
        match="follow eligible routing targets in order",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-12",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.SUCCEEDED
            ),
            executed_target_id="target-b",
            execution_fallback_used=False,
            attempts=(
                _success_attempt("target-b"),
            ),
        )


def test_attempts_cannot_skip_eligible_target() -> None:
    with pytest.raises(
        ValidationError,
        match="follow eligible routing targets in order",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-13",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.SUCCEEDED
            ),
            executed_target_id="target-c",
            execution_fallback_used=True,
            attempts=(
                _provider_error_attempt("target-a"),
                _success_attempt("target-c"),
            ),
        )


def test_execution_fallback_flag_must_match_attempts() -> None:
    with pytest.raises(
        ValidationError,
        match="execution_fallback_used",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-14",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.SUCCEEDED
            ),
            executed_target_id="target-b",
            execution_fallback_used=False,
            attempts=(
                _provider_error_attempt("target-a"),
                _success_attempt("target-b"),
            ),
        )


def test_success_requires_successful_final_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match="successful final execution attempt",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-15",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.SUCCEEDED
            ),
            executed_target_id="target-a",
            attempts=(
                _provider_error_attempt("target-a"),
            ),
        )


def test_success_rejects_success_before_final_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match="attempts before success",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-16",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.SUCCEEDED
            ),
            executed_target_id="target-b",
            execution_fallback_used=True,
            attempts=(
                _success_attempt("target-a"),
                _success_attempt("target-b"),
            ),
        )


def test_executed_target_must_match_final_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match="executed target",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-17",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.SUCCEEDED
            ),
            executed_target_id="target-a",
            execution_fallback_used=True,
            attempts=(
                _provider_error_attempt("target-a"),
                _success_attempt("target-b"),
            ),
        )


def test_failed_execution_rejects_executed_target() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain executed_target_id",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-18",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.FAILED
            ),
            executed_target_id="target-a",
            attempts=(
                _provider_error_attempt("target-a"),
            ),
        )


def test_failed_execution_rejects_success_attempt() -> None:
    with pytest.raises(
        ValidationError,
        match="provider-error attempts only",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-19",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.FAILED
            ),
            executed_target_id=None,
            attempts=(
                _success_attempt("target-a"),
            ),
        )


def test_routing_evidence_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        RoutingEvidenceRecord(
            evidence_id="route-evidence-20",
            policy=_policy(),
            decision=_primary_decision(),
            execution_outcome=(
                RoutingEvidenceExecutionOutcome.NOT_EXECUTED
            ),
            observed_at=datetime(
                2026,
                8,
                16,
                12,
                0,
                0,
            ),
        )


def _dataset_identity() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="quality-suite",
        dataset_version="v1",
    )


def _run(
    *,
    run_id: str = "run-1",
    outcome: EvaluationRunOutcome = (
        EvaluationRunOutcome.SUCCEEDED
    ),
    metrics: tuple[
        EvaluationMetricResult,
        ...,
    ] = (
        EvaluationMetricResult(
            metric=EvaluationMetric.CLAIM_PRESERVATION,
            value=0.95,
        ),
        EvaluationMetricResult(
            metric=EvaluationMetric.LATENCY_MS,
            value=200.0,
        ),
        EvaluationMetricResult(
            metric=EvaluationMetric.PROVIDER_ERROR_RATE,
            value=0.0,
        ),
    ),
) -> EvaluationRunRecord:
    identity = EvaluationRunIdentity(
        run_id=run_id,
        dataset=_dataset_identity(),
        target_id="target-a",
    )

    if outcome is EvaluationRunOutcome.FAILED:
        return EvaluationRunRecord(
            identity=identity,
            outcome=outcome,
            evaluated_case_count=10,
            failed_case_count=1,
            metric_results=metrics,
            failure_reason="evaluation run failed",
        )

    return EvaluationRunRecord(
        identity=identity,
        outcome=outcome,
        evaluated_case_count=10,
        failed_case_count=0,
        metric_results=metrics,
    )


def _gate_result(
    *,
    run_id: str = "run-1",
    claim_value: float = 0.95,
) -> EvaluationGateResult:
    gate = EvaluationQualityGate(
        gate_id="quality-gate-1",
        thresholds=(
            EvaluationThreshold(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                comparator=EvaluationComparator.AT_LEAST,
                threshold=0.90,
            ),
            EvaluationThreshold(
                metric=EvaluationMetric.LATENCY_MS,
                comparator=EvaluationComparator.AT_MOST,
                threshold=500.0,
            ),
        ),
    )

    return EvaluationGateResult(
        gate=gate,
        run_id=run_id,
        decision=(
            EvaluationGateDecision.PASSED
            if claim_value >= 0.90
            else EvaluationGateDecision.FAILED
        ),
        metric_results=(
            EvaluationMetricResult(
                metric=EvaluationMetric.CLAIM_PRESERVATION,
                value=claim_value,
            ),
            EvaluationMetricResult(
                metric=EvaluationMetric.LATENCY_MS,
                value=200.0,
            ),
        ),
    )


def test_evaluation_run_evidence_without_gate() -> None:
    evidence = EvaluationEvidenceRecord(
        evidence_id="eval-evidence-1",
        run=_run(),
    )

    assert evidence.run.identity.run_id == "run-1"
    assert evidence.gate_result is None


def test_evaluation_evidence_with_gate_result() -> None:
    gate_result = _gate_result()

    evidence = EvaluationEvidenceRecord(
        evidence_id="eval-evidence-2",
        run=_run(),
        gate_result=gate_result,
    )

    assert evidence.gate_result == gate_result


def test_gate_result_run_id_must_match_run() -> None:
    with pytest.raises(
        ValidationError,
        match="run identity",
    ):
        EvaluationEvidenceRecord(
            evidence_id="eval-evidence-3",
            run=_run(
                run_id="run-1"
            ),
            gate_result=_gate_result(
                run_id="run-2"
            ),
        )


def test_failed_run_cannot_contain_gate_result() -> None:
    with pytest.raises(
        ValidationError,
        match="successful evaluation run",
    ):
        EvaluationEvidenceRecord(
            evidence_id="eval-evidence-4",
            run=_run(
                outcome=EvaluationRunOutcome.FAILED
            ),
            gate_result=_gate_result(),
        )


def test_gate_metric_must_exist_in_run() -> None:
    run = _run(
        metrics=(
            EvaluationMetricResult(
                metric=EvaluationMetric.LATENCY_MS,
                value=200.0,
            ),
        )
    )

    with pytest.raises(
        ValidationError,
        match="must exist in evaluation run",
    ):
        EvaluationEvidenceRecord(
            evidence_id="eval-evidence-5",
            run=run,
            gate_result=_gate_result(),
        )


def test_gate_metric_value_must_match_run() -> None:
    with pytest.raises(
        ValidationError,
        match="metric value",
    ):
        EvaluationEvidenceRecord(
            evidence_id="eval-evidence-6",
            run=_run(),
            gate_result=_gate_result(
                claim_value=0.91
            ),
        )


def test_evaluation_evidence_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        EvaluationEvidenceRecord(
            evidence_id="eval-evidence-7",
            run=_run(),
            observed_at=datetime(
                2026,
                8,
                16,
                12,
                0,
                0,
            ),
        )


def test_routing_evidence_is_frozen() -> None:
    evidence = RoutingEvidenceRecord(
        evidence_id="route-evidence-frozen",
        policy=_policy(),
        decision=_primary_decision(),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.NOT_EXECUTED
        ),
    )

    with pytest.raises(ValidationError):
        evidence.execution_fallback_used = True


def test_evaluation_evidence_is_frozen() -> None:
    evidence = EvaluationEvidenceRecord(
        evidence_id="eval-evidence-frozen",
        run=_run(),
    )

    with pytest.raises(ValidationError):
        evidence.gate_result = _gate_result()


def test_evidence_models_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EvaluationEvidenceRecord(
            evidence_id="eval-evidence-extra",
            run=_run(),
            unknown_field="forbidden",
        )
