from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationCaseReference,
    EvaluationDatasetCase,
    EvaluationReferenceKind,
)
from app.v2.domain.eval_metrics import (
    EvaluationCaseExecutionEvidence,
    EvaluationMetricMethod,
)
from app.v2.domain.eval_ops import (
    EVAL_OPS_VERSION,
    EvaluationMetric,
)
from app.v2.services.eval_metric_service import (
    DeterministicEvaluationMetricService,
    EvaluationMetricEvidenceUnavailableError,
)


def _reference(
    *,
    reference_id: str,
    kind: EvaluationReferenceKind,
    value: str,
) -> EvaluationCaseReference:
    return EvaluationCaseReference(
        reference_id=reference_id,
        kind=kind,
        value=value,
    )


def _case(
    *,
    case_id: str = "case-001",
    text: str = "The launch was on May 3.",
    references: tuple[
        EvaluationCaseReference,
        ...,
    ] = (),
) -> EvaluationDatasetCase:
    return EvaluationDatasetCase(
        case_id=case_id,
        input=EvaluationCaseInput(
            text=text
        ),
        references=references,
    )


def _evidence(
    *,
    case_id: str = "case-001",
    output_text: str | None = "The launch was on May 3.",
    latency_ms: float | None = 125.0,
    provider_error: bool = False,
    provider_error_category: str | None = None,
    naturalness_score: float | None = 0.9,
) -> EvaluationCaseExecutionEvidence:
    return EvaluationCaseExecutionEvidence(
        case_id=case_id,
        output_text=output_text,
        latency_ms=latency_ms,
        provider_error=provider_error,
        provider_error_category=provider_error_category,
        naturalness_score=naturalness_score,
    )


def _service() -> DeterministicEvaluationMetricService:
    return DeterministicEvaluationMetricService()


def test_execution_evidence_uses_eval_ops_version() -> None:
    evidence = _evidence()

    assert evidence.eval_version == EVAL_OPS_VERSION


def test_execution_evidence_is_frozen() -> None:
    evidence = _evidence()

    with pytest.raises(ValidationError):
        evidence.case_id = "changed"


def test_execution_evidence_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EvaluationCaseExecutionEvidence(
            case_id="case-001",
            unexpected=True,
        )


def test_provider_error_requires_category() -> None:
    with pytest.raises(
        ValidationError,
        match="requires provider_error_category",
    ):
        _evidence(
            provider_error=True,
            provider_error_category=None,
        )


def test_provider_error_category_requires_error() -> None:
    with pytest.raises(
        ValidationError,
        match="requires provider_error evidence",
    ):
        _evidence(
            provider_error=False,
            provider_error_category="transport",
        )


def test_case_identity_mismatch_fails() -> None:
    with pytest.raises(
        ValueError,
        match="case_id",
    ):
        _service().evaluate(
            case=_case(),
            evidence=_evidence(
                case_id="different-case"
            ),
            metric=EvaluationMetric.LATENCY_MS,
        )


def test_claim_preservation_all_checks_pass() -> None:
    case = _case(
        references=(
            _reference(
                reference_id="required-1",
                kind=EvaluationReferenceKind.REQUIRED_CLAIM,
                value="The launch was on May 3.",
            ),
            _reference(
                reference_id="forbidden-1",
                kind=EvaluationReferenceKind.FORBIDDEN_CLAIM,
                value="The launch was delayed.",
            ),
        )
    )

    measurement = _service().evaluate(
        case=case,
        evidence=_evidence(
            output_text="The launch was on May 3."
        ),
        metric=EvaluationMetric.CLAIM_PRESERVATION,
    )

    assert measurement.result.value == 1.0
    assert (
        measurement.method
        is EvaluationMetricMethod.CLAIM_REFERENCE_CHECKS
    )


def test_claim_preservation_partial_score() -> None:
    case = _case(
        references=(
            _reference(
                reference_id="required-1",
                kind=EvaluationReferenceKind.REQUIRED_CLAIM,
                value="May 3",
            ),
            _reference(
                reference_id="required-2",
                kind=EvaluationReferenceKind.REQUIRED_CLAIM,
                value="Seattle",
            ),
        )
    )

    measurement = _service().evaluate(
        case=case,
        evidence=_evidence(
            output_text="The launch was on May 3."
        ),
        metric=EvaluationMetric.CLAIM_PRESERVATION,
    )

    assert measurement.result.value == 0.5


def test_claim_preservation_detects_forbidden_claim() -> None:
    case = _case(
        references=(
            _reference(
                reference_id="forbidden-1",
                kind=EvaluationReferenceKind.FORBIDDEN_CLAIM,
                value="launch was delayed",
            ),
        )
    )

    measurement = _service().evaluate(
        case=case,
        evidence=_evidence(
            output_text="The launch was delayed."
        ),
        metric=EvaluationMetric.CLAIM_PRESERVATION,
    )

    assert measurement.result.value == 0.0


def test_claim_matching_normalizes_case_and_whitespace() -> None:
    case = _case(
        references=(
            _reference(
                reference_id="required-1",
                kind=EvaluationReferenceKind.REQUIRED_CLAIM,
                value="THE   LAUNCH",
            ),
        )
    )

    measurement = _service().evaluate(
        case=case,
        evidence=_evidence(
            output_text="The launch happened."
        ),
        metric=EvaluationMetric.CLAIM_PRESERVATION,
    )

    assert measurement.result.value == 1.0


def test_reference_rewrite_is_not_claim_check() -> None:
    case = _case(
        references=(
            _reference(
                reference_id="rewrite-1",
                kind=EvaluationReferenceKind.REFERENCE_REWRITE,
                value="A preferred rewrite.",
            ),
        )
    )

    with pytest.raises(
        EvaluationMetricEvidenceUnavailableError,
        match="claim reference",
    ):
        _service().evaluate(
            case=case,
            evidence=_evidence(),
            metric=EvaluationMetric.CLAIM_PRESERVATION,
        )


def test_claim_preservation_requires_output() -> None:
    case = _case(
        references=(
            _reference(
                reference_id="required-1",
                kind=EvaluationReferenceKind.REQUIRED_CLAIM,
                value="Claim",
            ),
        )
    )

    with pytest.raises(
        EvaluationMetricEvidenceUnavailableError,
        match="output text",
    ):
        _service().evaluate(
            case=case,
            evidence=_evidence(
                output_text=None
            ),
            metric=EvaluationMetric.CLAIM_PRESERVATION,
        )


def test_claim_preservation_requires_claim_reference() -> None:
    with pytest.raises(
        EvaluationMetricEvidenceUnavailableError,
        match="claim reference",
    ):
        _service().evaluate(
            case=_case(),
            evidence=_evidence(),
            metric=EvaluationMetric.CLAIM_PRESERVATION,
        )


def test_naturalness_uses_explicit_score() -> None:
    measurement = _service().evaluate(
        case=_case(),
        evidence=_evidence(
            naturalness_score=0.83
        ),
        metric=EvaluationMetric.NATURALNESS,
    )

    assert measurement.result.value == 0.83
    assert (
        measurement.method
        is EvaluationMetricMethod.EXPLICIT_NATURALNESS_SCORE
    )


def test_naturalness_requires_explicit_score() -> None:
    with pytest.raises(
        EvaluationMetricEvidenceUnavailableError,
        match="naturalness score",
    ):
        _service().evaluate(
            case=_case(),
            evidence=_evidence(
                naturalness_score=None
            ),
            metric=EvaluationMetric.NATURALNESS,
        )


def test_naturalness_score_is_bounded() -> None:
    with pytest.raises(ValidationError):
        _evidence(
            naturalness_score=1.1
        )


def test_identical_text_has_zero_rewrite_distance() -> None:
    source = "The launch was on May 3."

    measurement = _service().evaluate(
        case=_case(
            text=source
        ),
        evidence=_evidence(
            output_text=source
        ),
        metric=EvaluationMetric.REWRITE_DISTANCE,
    )

    assert measurement.result.value == 0.0


def test_changed_text_has_positive_rewrite_distance() -> None:
    measurement = _service().evaluate(
        case=_case(
            text="Alpha beta gamma."
        ),
        evidence=_evidence(
            output_text="Completely different."
        ),
        metric=EvaluationMetric.REWRITE_DISTANCE,
    )

    assert 0.0 < measurement.result.value <= 1.0
    assert (
        measurement.method
        is EvaluationMetricMethod.CHARACTER_SEQUENCE_DISTANCE
    )


def test_rewrite_distance_requires_output() -> None:
    with pytest.raises(
        EvaluationMetricEvidenceUnavailableError,
        match="output text",
    ):
        _service().evaluate(
            case=_case(),
            evidence=_evidence(
                output_text=None
            ),
            metric=EvaluationMetric.REWRITE_DISTANCE,
        )


def test_latency_returns_explicit_latency() -> None:
    measurement = _service().evaluate(
        case=_case(),
        evidence=_evidence(
            latency_ms=42.5
        ),
        metric=EvaluationMetric.LATENCY_MS,
    )

    assert measurement.result.value == 42.5
    assert (
        measurement.method
        is EvaluationMetricMethod.EXECUTION_LATENCY
    )


def test_latency_requires_evidence() -> None:
    with pytest.raises(
        EvaluationMetricEvidenceUnavailableError,
        match="latency evidence",
    ):
        _service().evaluate(
            case=_case(),
            evidence=_evidence(
                latency_ms=None
            ),
            metric=EvaluationMetric.LATENCY_MS,
        )


def test_latency_must_be_nonnegative() -> None:
    with pytest.raises(ValidationError):
        _evidence(
            latency_ms=-1.0
        )


def test_provider_success_has_zero_error_indicator() -> None:
    measurement = _service().evaluate(
        case=_case(),
        evidence=_evidence(),
        metric=EvaluationMetric.PROVIDER_ERROR_RATE,
    )

    assert measurement.result.value == 0.0
    assert (
        measurement.method
        is EvaluationMetricMethod.PROVIDER_ERROR_INDICATOR
    )


def test_provider_error_has_one_error_indicator() -> None:
    measurement = _service().evaluate(
        case=_case(),
        evidence=_evidence(
            output_text=None,
            provider_error=True,
            provider_error_category="transport",
        ),
        metric=EvaluationMetric.PROVIDER_ERROR_RATE,
    )

    assert measurement.result.value == 1.0


def test_measurement_identifies_case_and_metric() -> None:
    measurement = _service().evaluate(
        case=_case(
            case_id="case-specific"
        ),
        evidence=_evidence(
            case_id="case-specific",
            latency_ms=10.0,
        ),
        metric=EvaluationMetric.LATENCY_MS,
    )

    assert measurement.case_id == "case-specific"
    assert (
        measurement.result.metric
        is EvaluationMetric.LATENCY_MS
    )


def test_measurement_is_frozen() -> None:
    measurement = _service().evaluate(
        case=_case(),
        evidence=_evidence(),
        metric=EvaluationMetric.LATENCY_MS,
    )

    with pytest.raises(ValidationError):
        measurement.case_id = "changed"


def test_evaluate_many_preserves_requested_metric_order() -> None:
    metrics = (
        EvaluationMetric.LATENCY_MS,
        EvaluationMetric.NATURALNESS,
        EvaluationMetric.PROVIDER_ERROR_RATE,
    )

    measurements = _service().evaluate_many(
        case=_case(),
        evidence=_evidence(),
        metrics=metrics,
    )

    assert tuple(
        measurement.result.metric
        for measurement in measurements
    ) == metrics


def test_evaluate_many_rejects_empty_metric_request() -> None:
    with pytest.raises(
        ValueError,
        match="at least one metric",
    ):
        _service().evaluate_many(
            case=_case(),
            evidence=_evidence(),
            metrics=(),
        )


def test_evaluate_many_rejects_duplicate_metrics() -> None:
    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        _service().evaluate_many(
            case=_case(),
            evidence=_evidence(),
            metrics=(
                EvaluationMetric.LATENCY_MS,
                EvaluationMetric.LATENCY_MS,
            ),
        )


@pytest.mark.parametrize(
    "metric",
    list(EvaluationMetric),
)
def test_every_declared_metric_has_deterministic_evaluator(
    metric: EvaluationMetric,
) -> None:
    case = _case(
        references=(
            _reference(
                reference_id="required-1",
                kind=EvaluationReferenceKind.REQUIRED_CLAIM,
                value="May 3",
            ),
        )
    )

    measurement = _service().evaluate(
        case=case,
        evidence=_evidence(),
        metric=metric,
    )

    assert measurement.result.metric is metric
