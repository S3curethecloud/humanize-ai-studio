from __future__ import annotations

from datetime import datetime

from app.v2.domain.enterprise_evaluation_operation import (
    EnterpriseEvaluationEvidenceKind,
    EnterpriseWorkspaceEvaluationEvidenceBinding,
    EnterpriseWorkspaceEvaluationOperation,
)
from app.v2.domain.eval_ops import (
    EvaluationRunOutcome,
)


class EnterpriseEvaluationEvidenceIntegrityError(
    RuntimeError
):
    pass


def require_enterprise_evaluation_evidence_integrity(
    *,
    operation: EnterpriseWorkspaceEvaluationOperation,
    binding: EnterpriseWorkspaceEvaluationEvidenceBinding,
    evidence: object,
) -> None:
    evidence_id = getattr(
        evidence,
        "evidence_id",
        None,
    )

    if evidence_id != binding.evidence_id:
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "platform evaluation evidence identity "
            "does not match reserved evidence"
        )

    observed_at = getattr(
        evidence,
        "observed_at",
        None,
    )

    if (
        not isinstance(
            observed_at,
            datetime,
        )
        or observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "platform evaluation evidence observed_at "
            "must be timezone-aware"
        )

    if observed_at < binding.created_at:
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "platform evaluation evidence observed_at "
            "predates reserved binding"
        )

    run = getattr(
        evidence,
        "run",
        None,
    )

    run_identity = getattr(
        run,
        "identity",
        None,
    )

    run_id = getattr(
        run_identity,
        "run_id",
        None,
    )

    if (
        run_id != operation.run_id
        or run_id != binding.run_id
    ):
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "platform evaluation evidence run identity "
            "does not match enterprise operation"
        )

    dataset = getattr(
        run_identity,
        "dataset",
        None,
    )

    dataset_id = getattr(
        dataset,
        "dataset_id",
        None,
    )

    dataset_version = getattr(
        dataset,
        "dataset_version",
        None,
    )

    if (
        dataset_id != operation.dataset_id
        or dataset_version != operation.dataset_version
    ):
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "platform evaluation evidence dataset identity "
            "does not match enterprise operation"
        )

    target_id = getattr(
        run_identity,
        "target_id",
        None,
    )

    if target_id != operation.target_id:
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "platform evaluation evidence target identity "
            "does not match enterprise operation"
        )

    metric_results = getattr(
        run,
        "metric_results",
        (),
    )

    actual_metrics = frozenset(
        getattr(
            result,
            "metric",
            None,
        )
        for result in metric_results
    )

    expected_metrics = frozenset(
        operation.requested_metrics
    )

    if None in actual_metrics:
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "platform evaluation evidence contains "
            "an invalid metric identity"
        )

    if not actual_metrics.issubset(
        expected_metrics
    ):
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "platform evaluation evidence contains "
            "metrics not requested by enterprise operation"
        )

    run_outcome = getattr(
        run,
        "outcome",
        None,
    )

    if (
        run_outcome
        is EvaluationRunOutcome.SUCCEEDED
        and actual_metrics != expected_metrics
    ):
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "successful platform evaluation evidence "
            "metrics do not match enterprise operation request"
        )

    gate_result = getattr(
        evidence,
        "gate_result",
        None,
    )

    if (
        binding.evidence_kind
        is EnterpriseEvaluationEvidenceKind.RUN
    ):
        if gate_result is not None:
            raise EnterpriseEvaluationEvidenceIntegrityError(
                "run evidence binding resolved "
                "to gate evidence"
            )

        return

    if gate_result is None:
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "gate evidence binding resolved "
            "to run-only evidence"
        )

    gate_result_run_id = getattr(
        gate_result,
        "run_id",
        None,
    )

    if gate_result_run_id != operation.run_id:
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "gate evidence run identity "
            "does not match enterprise operation"
        )

    gate = getattr(
        gate_result,
        "gate",
        None,
    )

    gate_id = getattr(
        gate,
        "gate_id",
        None,
    )

    if gate_id != binding.gate_id:
        raise EnterpriseEvaluationEvidenceIntegrityError(
            "gate evidence identity "
            "does not match reserved gate"
        )
