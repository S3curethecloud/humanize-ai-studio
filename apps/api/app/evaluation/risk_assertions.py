from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.evaluation.models import (
    RiskAssertion,
    RiskAssertionResult,
    RiskAssertionType,
)
from app.evaluation.text_normalization import normalize_evaluation_text

_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}

_NEGATION_MARKERS = (
    " not ",
    " no ",
    " never ",
    " cannot ",
    " can't ",
    " does not ",
    " do not ",
    " did not ",
    " will not ",
    " won't ",
)

_PROHIBITION_MARKERS = (
    " must not ",
    " shall not ",
    " may not ",
    " cannot ",
    " never ",
    " prohibited ",
    " forbidden ",
    " do not ",
    " does not ",
)

_REQUIREMENT_MARKERS = (
    " must ",
    " shall ",
    " required ",
    " requires ",
    " require ",
    " needs to ",
    " has to ",
    " cannot be exceeded ",
)

_P95_PATTERN = re.compile(
    r"\b(?:p95|95th[\s-]*percentile)\b",
    re.IGNORECASE,
)


class RiskAssertionEvaluator:
    def evaluate(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertions: list[RiskAssertion],
    ) -> list[RiskAssertionResult]:
        return [
            self._evaluate_assertion(
                source_text=source_text,
                rewritten_text=rewritten_text,
                assertion=assertion,
            )
            for assertion in assertions
        ]

    def _evaluate_assertion(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> RiskAssertionResult:
        evaluator = {
            RiskAssertionType.EXACT_PRESERVATION: (self._evaluate_exact_preservation),
            RiskAssertionType.NUMERIC_EQUIVALENCE: (self._evaluate_numeric_equivalence),
            RiskAssertionType.NEGATION: self._evaluate_negation,
            RiskAssertionType.PROHIBITION: self._evaluate_prohibition,
            RiskAssertionType.REQUIREMENT: self._evaluate_requirement,
            RiskAssertionType.CONCEPT_GROUPS: (self._evaluate_concept_groups),
            RiskAssertionType.MINIMAL_CHANGE: (self._evaluate_minimal_change),
        }[assertion.assertion_type]

        passed, details = evaluator(
            source_text=source_text,
            rewritten_text=rewritten_text,
            assertion=assertion,
        )

        return RiskAssertionResult(
            assertion_type=assertion.assertion_type,
            description=assertion.description,
            passed=passed,
            details=details,
        )

    def _evaluate_exact_preservation(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> tuple[bool, list[str]]:
        del source_text

        normalized_rewrite = normalize_evaluation_text(rewritten_text)

        missing = [
            value
            for value in assertion.values
            if normalize_evaluation_text(value) not in normalized_rewrite
        ]

        return not missing, [f"Missing exact value: {value}" for value in missing]

    def _evaluate_numeric_equivalence(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> tuple[bool, list[str]]:
        del source_text

        canonical_rewrite = _canonicalize_numeric_text(rewritten_text)

        missing = [
            value
            for value in assertion.values
            if _canonicalize_numeric_text(value) not in canonical_rewrite
        ]

        return not missing, [f"Missing numeric equivalent: {value}" for value in missing]

    def _evaluate_negation(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> tuple[bool, list[str]]:
        del source_text

        normalized = f" {normalize_evaluation_text(rewritten_text)} "
        has_negation = any(marker in normalized for marker in _NEGATION_MARKERS)

        concepts_pass, concept_details = _concept_groups_present(
            normalized_text=normalized,
            groups=assertion.concept_groups,
        )

        details: list[str] = []

        if not has_negation:
            details.append("No negation marker remained.")

        details.extend(concept_details)

        return has_negation and concepts_pass, details

    def _evaluate_prohibition(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> tuple[bool, list[str]]:
        del source_text

        normalized = f" {normalize_evaluation_text(rewritten_text)} "
        has_prohibition = any(marker in normalized for marker in _PROHIBITION_MARKERS)

        concepts_pass, concept_details = _concept_groups_present(
            normalized_text=normalized,
            groups=assertion.concept_groups,
        )

        details: list[str] = []

        if not has_prohibition:
            details.append("No prohibition marker remained.")

        details.extend(concept_details)

        return has_prohibition and concepts_pass, details

    def _evaluate_requirement(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> tuple[bool, list[str]]:
        del source_text

        normalized = f" {normalize_evaluation_text(rewritten_text)} "
        has_requirement = any(marker in normalized for marker in _REQUIREMENT_MARKERS)

        concepts_pass, concept_details = _concept_groups_present(
            normalized_text=normalized,
            groups=assertion.concept_groups,
        )

        details: list[str] = []

        if not has_requirement:
            details.append("No mandatory-language marker remained.")

        details.extend(concept_details)

        return has_requirement and concepts_pass, details

    def _evaluate_concept_groups(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> tuple[bool, list[str]]:
        del source_text

        normalized = normalize_evaluation_text(rewritten_text)

        return _concept_groups_present(
            normalized_text=normalized,
            groups=assertion.concept_groups,
        )

    def _evaluate_minimal_change(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> tuple[bool, list[str]]:
        threshold = assertion.minimum_similarity

        if threshold is None:
            threshold = 0.85

        normalized_source = normalize_evaluation_text(source_text)
        normalized_rewrite = normalize_evaluation_text(rewritten_text)

        similarity = SequenceMatcher(
            None,
            normalized_source,
            normalized_rewrite,
        ).ratio()

        passed = similarity >= threshold

        details = (
            [(f"Similarity {similarity:.3f} was below the required threshold {threshold:.3f}.")]
            if not passed
            else []
        )

        return passed, details


def _concept_groups_present(
    *,
    normalized_text: str,
    groups: list[list[str]],
) -> tuple[bool, list[str]]:
    missing_groups: list[list[str]] = []

    for group in groups:
        group_present = any(
            normalize_evaluation_text(alternative) in normalized_text for alternative in group
        )

        if not group_present:
            missing_groups.append(group)

    details = ["Missing concept alternatives: " + " | ".join(group) for group in missing_groups]

    return not missing_groups, details


def _canonicalize_numeric_text(text: str) -> str:
    normalized = normalize_evaluation_text(text)

    for word, number in _NUMBER_WORDS.items():
        normalized = re.sub(
            rf"\b{word}\b",
            number,
            normalized,
            flags=re.IGNORECASE,
        )

    normalized = _P95_PATTERN.sub("p95", normalized)
    normalized = normalized.replace(",", "")

    return normalized
