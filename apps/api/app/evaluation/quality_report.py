from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from app.domain.models import RewriteIntensity

RejectionCategory = Literal[
    "claim_integrity",
    "useful_distance",
    "structural_blueprint",
    "provider_response",
    "provider_transport",
    "none",
]


@dataclass(frozen=True)
class EvaluationCaseResult:
    case_id: str
    intensity: RewriteIntensity
    provider_succeeded: bool
    repair_attempted: bool
    repair_succeeded: bool
    fallback_used: bool
    rejection_category: RejectionCategory
    model_call_count: int
    claim_integrity_preserved: bool
    useful_distance_satisfied: bool
    structural_blueprint_satisfied: bool
    unsafe_output_released: bool

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["intensity"] = self.intensity.value
        return result


@dataclass(frozen=True)
class EvaluationReleaseThresholds:
    minimum_provider_success_rate: float = 0.70
    minimum_repair_success_rate: float = 0.50
    maximum_fallback_rate: float = 0.30
    maximum_model_call_count: int = 2
    maximum_unsafe_output_release_count: int = 0
    maximum_deep_structural_failure_release_count: int = 0


@dataclass(frozen=True)
class ReleaseGateResult:
    passed: bool
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "failures": list(self.failures),
        }


@dataclass(frozen=True)
class EvaluationSummary:
    total_cases: int
    provider_success_count: int
    repair_attempt_count: int
    repair_success_count: int
    fallback_count: int
    claim_integrity_rejection_count: int
    useful_distance_rejection_count: int
    structural_blueprint_rejection_count: int
    provider_response_rejection_count: int
    provider_transport_rejection_count: int
    unsafe_output_release_count: int
    deep_structural_failure_release_count: int
    maximum_observed_model_call_count: int
    provider_success_rate: float
    repair_attempt_rate: float
    repair_success_rate: float
    fallback_rate: float
    claim_integrity_rejection_rate: float
    useful_distance_rejection_rate: float
    structural_blueprint_rejection_rate: float
    release_gate: ReleaseGateResult

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["release_gate"] = self.release_gate.to_dict()
        return result


def summarize_evaluation(
    results: tuple[EvaluationCaseResult, ...],
    thresholds: EvaluationReleaseThresholds | None = None,
) -> EvaluationSummary:
    active_thresholds = thresholds or EvaluationReleaseThresholds()
    total_cases = len(results)

    provider_success_count = sum(result.provider_succeeded for result in results)
    repair_attempt_count = sum(result.repair_attempted for result in results)
    repair_success_count = sum(result.repair_succeeded for result in results)
    fallback_count = sum(result.fallback_used for result in results)

    claim_integrity_rejection_count = _rejection_count(
        results,
        "claim_integrity",
    )
    useful_distance_rejection_count = _rejection_count(
        results,
        "useful_distance",
    )
    structural_blueprint_rejection_count = _rejection_count(
        results,
        "structural_blueprint",
    )
    provider_response_rejection_count = _rejection_count(
        results,
        "provider_response",
    )
    provider_transport_rejection_count = _rejection_count(
        results,
        "provider_transport",
    )

    unsafe_output_release_count = sum(result.unsafe_output_released for result in results)
    deep_structural_failure_release_count = sum(
        (
            result.intensity == RewriteIntensity.DEEP_RECONSTRUCTION
            and result.provider_succeeded
            and not result.structural_blueprint_satisfied
        )
        for result in results
    )

    maximum_observed_model_call_count = max(
        (result.model_call_count for result in results),
        default=0,
    )

    provider_success_rate = _rate(
        provider_success_count,
        total_cases,
    )
    repair_attempt_rate = _rate(
        repair_attempt_count,
        total_cases,
    )
    repair_success_rate = _rate(
        repair_success_count,
        repair_attempt_count,
    )
    fallback_rate = _rate(
        fallback_count,
        total_cases,
    )

    failures: list[str] = []

    if provider_success_rate < active_thresholds.minimum_provider_success_rate:
        failures.append(
            "provider_success_rate "
            f"{provider_success_rate:.4f} is below "
            f"{active_thresholds.minimum_provider_success_rate:.4f}"
        )

    if (
        repair_attempt_count > 0
        and repair_success_rate < active_thresholds.minimum_repair_success_rate
    ):
        failures.append(
            "repair_success_rate "
            f"{repair_success_rate:.4f} is below "
            f"{active_thresholds.minimum_repair_success_rate:.4f}"
        )

    if fallback_rate > active_thresholds.maximum_fallback_rate:
        failures.append(
            "fallback_rate "
            f"{fallback_rate:.4f} exceeds "
            f"{active_thresholds.maximum_fallback_rate:.4f}"
        )

    if maximum_observed_model_call_count > active_thresholds.maximum_model_call_count:
        failures.append(
            "maximum_observed_model_call_count "
            f"{maximum_observed_model_call_count} exceeds "
            f"{active_thresholds.maximum_model_call_count}"
        )

    if unsafe_output_release_count > active_thresholds.maximum_unsafe_output_release_count:
        failures.append(
            "unsafe_output_release_count "
            f"{unsafe_output_release_count} exceeds "
            f"{active_thresholds.maximum_unsafe_output_release_count}"
        )

    if (
        deep_structural_failure_release_count
        > active_thresholds.maximum_deep_structural_failure_release_count
    ):
        failures.append(
            "deep_structural_failure_release_count "
            f"{deep_structural_failure_release_count} exceeds "
            f"{active_thresholds.maximum_deep_structural_failure_release_count}"
        )

    return EvaluationSummary(
        total_cases=total_cases,
        provider_success_count=provider_success_count,
        repair_attempt_count=repair_attempt_count,
        repair_success_count=repair_success_count,
        fallback_count=fallback_count,
        claim_integrity_rejection_count=(claim_integrity_rejection_count),
        useful_distance_rejection_count=(useful_distance_rejection_count),
        structural_blueprint_rejection_count=(structural_blueprint_rejection_count),
        provider_response_rejection_count=(provider_response_rejection_count),
        provider_transport_rejection_count=(provider_transport_rejection_count),
        unsafe_output_release_count=unsafe_output_release_count,
        deep_structural_failure_release_count=(deep_structural_failure_release_count),
        maximum_observed_model_call_count=(maximum_observed_model_call_count),
        provider_success_rate=provider_success_rate,
        repair_attempt_rate=repair_attempt_rate,
        repair_success_rate=repair_success_rate,
        fallback_rate=fallback_rate,
        claim_integrity_rejection_rate=_rate(
            claim_integrity_rejection_count,
            total_cases,
        ),
        useful_distance_rejection_rate=_rate(
            useful_distance_rejection_count,
            total_cases,
        ),
        structural_blueprint_rejection_rate=_rate(
            structural_blueprint_rejection_count,
            total_cases,
        ),
        release_gate=ReleaseGateResult(
            passed=not failures,
            failures=tuple(failures),
        ),
    )


def _rejection_count(
    results: tuple[EvaluationCaseResult, ...],
    category: RejectionCategory,
) -> int:
    return sum(result.rejection_category == category for result in results)


def _rate(
    numerator: int,
    denominator: int,
) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator
