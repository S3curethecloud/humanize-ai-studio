from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimIntegrityViolation:
    rule_id: str
    phrase: str
    description: str


PROHIBITED_ADDITIONS: tuple[tuple[str, str, str], ...] = (
    (
        "qualification_inflation",
        "extensive experience",
        "The rewrite strengthened experience beyond the source.",
    ),
    (
        "qualification_inflation",
        "deep experience",
        "The rewrite strengthened experience beyond the source.",
    ),
    (
        "expertise_inflation",
        "developed expertise",
        "The rewrite converted experience into expertise.",
    ),
    (
        "expertise_inflation",
        "proven expertise",
        "The rewrite introduced an unsupported expertise claim.",
    ),
    (
        "expertise_inflation",
        "expert in",
        "The rewrite introduced an unsupported expert claim.",
    ),
    (
        "mastery_inflation",
        "mastered",
        "The rewrite introduced an unsupported mastery claim.",
    ),
    (
        "promotional_filler",
        "leveraging a range of technologies",
        "The rewrite introduced generic promotional language.",
    ),
    (
        "promotional_filler",
        "across various areas",
        "The rewrite introduced vague scope language.",
    ),
    (
        "invented_outcome",
        "to drive effective solutions",
        "The rewrite introduced an unsupported outcome.",
    ),
    (
        "promotional_filler",
        "proven track record",
        "The rewrite introduced an unsupported promotional claim.",
    ),
    (
        "promotional_filler",
        "robust and seamless",
        "The rewrite introduced generic promotional language.",
    ),
)


def find_claim_integrity_violations(
    *,
    source_text: str,
    rewritten_text: str,
) -> list[ClaimIntegrityViolation]:
    source = _normalize(source_text)
    rewritten = _normalize(rewritten_text)

    violations: list[ClaimIntegrityViolation] = []

    for rule_id, phrase, description in PROHIBITED_ADDITIONS:
        normalized_phrase = _normalize(phrase)

        if normalized_phrase in source:
            continue

        if normalized_phrase not in rewritten:
            continue

        violations.append(
            ClaimIntegrityViolation(
                rule_id=rule_id,
                phrase=phrase,
                description=description,
            )
        )

    violations.extend(
        _find_protected_qualification_removals(
            source=source,
            rewritten=rewritten,
        )
    )

    return violations


def _find_protected_qualification_removals(
    *,
    source: str,
    rewritten: str,
) -> list[ClaimIntegrityViolation]:
    protected_qualifications = (
        "hands-on experience",
        "some experience",
        "limited experience",
        "familiar with",
        "contributed to",
        "helped build",
        "worked with",
    )

    violations: list[ClaimIntegrityViolation] = []

    for phrase in protected_qualifications:
        if phrase not in source:
            continue

        if phrase in rewritten:
            continue

        violations.append(
            ClaimIntegrityViolation(
                rule_id="qualification_removed",
                phrase=phrase,
                description=(
                    "The rewrite removed a protected qualification or participation boundary."
                ),
            )
        )

    return violations


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
