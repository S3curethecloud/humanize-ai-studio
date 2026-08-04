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
    " may not be exceeded ",
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
            RiskAssertionType.PERSONAL_OWNERSHIP: (self._evaluate_personal_ownership),
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

    def _evaluate_personal_ownership(
        self,
        *,
        source_text: str,
        rewritten_text: str,
        assertion: RiskAssertion,
    ) -> tuple[bool, list[str]]:
        del source_text

        normalized = normalize_evaluation_text(rewritten_text)

        ownership_patterns = (
            re.compile(
                r"\bi personally\s+"
                r"(?:handled|defined|designed|implemented|built|led)\b"
            ),
            re.compile(
                r"\bi\s+"
                r"(?:handled|defined|designed|implemented|built|led)\b"
                r"[^.!?]{0,120}\bmyself\b"
            ),
            re.compile(
                r"\bi myself\s+"
                r"(?:handled|defined|designed|implemented|built|led)\b"
            ),
            re.compile(r"\bi did not delegate\b"),
            re.compile(
                r"\bi directly\s+"
                r"(?:handled|defined|designed|implemented|built|led)\b"
            ),
            re.compile(r"\bi owned\b"),
            re.compile(
                r"\bi was responsible for\s+"
                r"(?:designing|defining|implementing|building|leading)\b"
            ),
        )

        has_personal_ownership = any(pattern.search(normalized) for pattern in ownership_patterns)

        concepts_pass, concept_details = _concept_groups_present(
            normalized_text=normalized,
            groups=assertion.concept_groups,
        )

        details: list[str] = []

        if not has_personal_ownership:
            details.append("No direct personal-ownership marker remained.")

        details.extend(concept_details)

        return has_personal_ownership and concepts_pass, details

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
            _concept_alternative_present(
                normalized_text=normalized_text,
                alternative=alternative,
            )
            for alternative in group
        )

        if not group_present:
            missing_groups.append(group)

    details = ["Missing concept alternatives: " + " | ".join(group) for group in missing_groups]

    return not missing_groups, details


def _concept_alternative_present(
    *,
    normalized_text: str,
    alternative: str,
) -> bool:
    normalized_alternative = normalize_evaluation_text(alternative)

    if normalized_alternative in normalized_text:
        return True

    text_tokens = _semantic_tokens(normalized_text)
    alternative_tokens = _semantic_tokens(normalized_alternative)

    if not alternative_tokens:
        return False

    return _is_ordered_subsequence(
        expected=alternative_tokens,
        actual=text_tokens,
    )


def _semantic_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())

    ignored_tokens = {
        "a",
        "an",
        "the",
        "to",
        "of",
        "for",
        "and",
        "or",
        "but",
        "it",
        "is",
        "are",
        "be",
        "by",
        "with",
        "when",
        "then",
        "can",
        "may",
        "does",
        "do",
    }

    return [_stem_semantic_token(token) for token in tokens if token not in ignored_tokens]


def _stem_semantic_token(token: str) -> str:
    explicit_stems = {
        "actions": "action",
        "authorization": "authorize",
        "authorizations": "authorize",
        "authorized": "authorize",
        "authorizing": "authorize",
        "authorizes": "authorize",
        "escalation": "escalate",
        "escalations": "escalate",
        "escalated": "escalate",
        "escalates": "escalate",
        "escalating": "escalate",
        "regulations": "regulation",
        "requirements": "requirement",
        "creates": "create",
        "created": "create",
        "creating": "create",
        "initiates": "initiate",
        "initiated": "initiate",
        "initiating": "initiate",
        "approvals": "approval",
        "controls": "control",
        "prompts": "prompt",
        "tools": "tool",
        "calls": "call",
    }

    explicit = explicit_stems.get(token)

    if explicit is not None:
        return explicit

    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"

    if len(token) > 4 and token.endswith("s"):
        return token[:-1]

    return token


def _is_ordered_subsequence(
    *,
    expected: list[str],
    actual: list[str],
) -> bool:
    expected_index = 0

    for token in actual:
        if token != expected[expected_index]:
            continue

        expected_index += 1

        if expected_index == len(expected):
            return True

    return False


_SHARED_UNIT_RANGE_PATTERN = re.compile(
    r"\b"
    r"(?P<first>\d+(?:\.\d+)?)"
    r"\s*(?:to|through|-)\s*"
    r"(?P<second>\d+(?:\.\d+)?)"
    r"\s*"
    r"(?P<unit>"
    r"business days|days|seconds|minutes|hours|"
    r"weeks|months|years"
    r")"
    r"\b",
    re.IGNORECASE,
)


def _expand_shared_unit_ranges(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        first = match.group("first")
        second = match.group("second")
        unit = match.group("unit")

        return f"{first} {unit} to {second} {unit}"

    return _SHARED_UNIT_RANGE_PATTERN.sub(replace, text)


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
    normalized = _expand_shared_unit_ranges(normalized)

    return normalized
