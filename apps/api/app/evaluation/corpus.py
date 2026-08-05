from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.models import RewriteIntensity
from app.evaluation.quality_report import RejectionCategory

EvaluationCohort = Literal[
    "performance",
    "safety_control",
]


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    cohort: EvaluationCohort
    source_text: str
    intensity: RewriteIntensity
    initial_output: str
    repair_output: str | None
    expected_provider_success: bool
    expected_repair_attempted: bool
    expected_repair_succeeded: bool
    expected_fallback_used: bool
    expected_rejection_category: RejectionCategory
    expected_model_call_count: int
    expected_claim_integrity_preserved: bool
    expected_useful_distance_satisfied: bool
    expected_structural_blueprint_satisfied: bool


def default_evaluation_corpus() -> tuple[EvaluationCase, ...]:
    return (
        EvaluationCase(
            case_id="light-edit-direct-success",
            cohort="performance",
            source_text="The platform is reliable",
            intensity=RewriteIntensity.LIGHT_EDIT,
            initial_output="The platform is reliable.",
            repair_output=None,
            expected_provider_success=True,
            expected_repair_attempted=False,
            expected_repair_succeeded=False,
            expected_fallback_used=False,
            expected_rejection_category="none",
            expected_model_call_count=1,
            expected_claim_integrity_preserved=True,
            expected_useful_distance_satisfied=True,
            expected_structural_blueprint_satisfied=True,
        ),
        EvaluationCase(
            case_id="natural-rewrite-direct-success",
            cohort="performance",
            source_text=("The team completed the migration and the system remained available."),
            intensity=RewriteIntensity.NATURAL_REWRITE,
            initial_output=(
                "The team completed the migration while the system remained available."
            ),
            repair_output=None,
            expected_provider_success=True,
            expected_repair_attempted=False,
            expected_repair_succeeded=False,
            expected_fallback_used=False,
            expected_rejection_category="none",
            expected_model_call_count=1,
            expected_claim_integrity_preserved=True,
            expected_useful_distance_satisfied=True,
            expected_structural_blueprint_satisfied=True,
        ),
        EvaluationCase(
            case_id="deep-direct-structural-success",
            cohort="performance",
            source_text=(
                "I have hands-on experience designing generative AI "
                "systems. In my current role, I work across RAG and "
                "agentic workflows."
            ),
            intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
            initial_output=(
                "In my current role, I work across RAG and agentic "
                "workflows. That work draws on my hands-on experience "
                "designing generative AI systems."
            ),
            repair_output=None,
            expected_provider_success=True,
            expected_repair_attempted=False,
            expected_repair_succeeded=False,
            expected_fallback_used=False,
            expected_rejection_category="none",
            expected_model_call_count=1,
            expected_claim_integrity_preserved=True,
            expected_useful_distance_satisfied=True,
            expected_structural_blueprint_satisfied=True,
        ),
        EvaluationCase(
            case_id="deep-repair-success",
            cohort="performance",
            source_text=(
                "I have hands-on experience designing generative AI "
                "systems. In my current role, I work across RAG and "
                "agentic workflows."
            ),
            intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
            initial_output=(
                "I developed expertise designing generative AI systems "
                "across RAG and agentic workflows."
            ),
            repair_output=(
                "In my current role, I work across RAG and agentic "
                "workflows. That work draws on my hands-on experience "
                "designing generative AI systems."
            ),
            expected_provider_success=True,
            expected_repair_attempted=True,
            expected_repair_succeeded=True,
            expected_fallback_used=False,
            expected_rejection_category="none",
            expected_model_call_count=2,
            expected_claim_integrity_preserved=True,
            expected_useful_distance_satisfied=True,
            expected_structural_blueprint_satisfied=True,
        ),
        EvaluationCase(
            case_id="repair-claim-integrity-fallback",
            cohort="safety_control",
            source_text=("I have hands-on experience contributing to the platform migration."),
            intensity=RewriteIntensity.NATURAL_REWRITE,
            initial_output=("I led the platform migration and delivered the production rollout."),
            repair_output=("I owned the platform migration and delivered the production rollout."),
            expected_provider_success=False,
            expected_repair_attempted=True,
            expected_repair_succeeded=False,
            expected_fallback_used=True,
            expected_rejection_category="claim_integrity",
            expected_model_call_count=2,
            expected_claim_integrity_preserved=False,
            expected_useful_distance_satisfied=False,
            expected_structural_blueprint_satisfied=True,
        ),
        EvaluationCase(
            case_id="repair-useful-distance-fallback",
            cohort="safety_control",
            source_text=(
                "I have hands-on experience contributing to secure enterprise integration."
            ),
            intensity=RewriteIntensity.NATURAL_REWRITE,
            initial_output=("I developed expertise leading secure enterprise integration."),
            repair_output=(
                "I have hands-on experience contributing to secure enterprise integration."
            ),
            expected_provider_success=False,
            expected_repair_attempted=True,
            expected_repair_succeeded=False,
            expected_fallback_used=True,
            expected_rejection_category="useful_distance",
            expected_model_call_count=2,
            expected_claim_integrity_preserved=True,
            expected_useful_distance_satisfied=False,
            expected_structural_blueprint_satisfied=True,
        ),
        EvaluationCase(
            case_id="repair-blueprint-fallback",
            cohort="safety_control",
            source_text=(
                "I have hands-on experience designing generative AI "
                "systems. In my current role, I work across RAG and "
                "agentic workflows."
            ),
            intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
            initial_output=(
                "I developed expertise designing generative AI systems "
                "across RAG and agentic workflows."
            ),
            repair_output=(
                "I have hands-on experience designing generative AI "
                "systems, which in my current role involves work across "
                "RAG and agentic workflows."
            ),
            expected_provider_success=False,
            expected_repair_attempted=True,
            expected_repair_succeeded=False,
            expected_fallback_used=True,
            expected_rejection_category="structural_blueprint",
            expected_model_call_count=2,
            expected_claim_integrity_preserved=True,
            expected_useful_distance_satisfied=True,
            expected_structural_blueprint_satisfied=False,
        ),
    )
