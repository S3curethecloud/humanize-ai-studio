from __future__ import annotations

import pytest

from app.providers.claim_integrity import (
    find_claim_integrity_violations,
)


@pytest.mark.parametrize(
    "added_phrase",
    [
        "extensive experience",
        "deep experience",
        "developed expertise",
        "proven expertise",
        "expert in",
        "mastered",
        "leveraging a range of technologies",
        "across various areas",
        "to drive effective solutions",
        "proven track record",
        "robust and seamless",
    ],
)
def test_rejects_prohibited_phrase_added_by_rewrite(
    added_phrase: str,
) -> None:
    violations = find_claim_integrity_violations(
        source_text=("I have hands-on experience designing generative AI systems."),
        rewritten_text=(
            f"I have hands-on experience designing generative AI systems and {added_phrase}."
        ),
    )

    assert violations
    assert any(violation.phrase == added_phrase for violation in violations)


def test_allows_phrase_when_already_present_in_source() -> None:
    violations = find_claim_integrity_violations(
        source_text=("I have extensive experience designing generative AI systems."),
        rewritten_text=("My work reflects extensive experience designing generative AI systems."),
    )

    assert not any(violation.phrase == "extensive experience" for violation in violations)


@pytest.mark.parametrize(
    "protected_phrase",
    [
        "hands-on experience",
        "some experience",
        "limited experience",
        "familiar with",
        "contributed to",
        "helped build",
        "worked with",
    ],
)
def test_rejects_removal_of_protected_qualification(
    protected_phrase: str,
) -> None:
    violations = find_claim_integrity_violations(
        source_text=(f"I {protected_phrase} the platform implementation."),
        rewritten_text=("I owned the platform implementation."),
    )

    assert any(
        violation.rule_id == "qualification_removed" and violation.phrase == protected_phrase
        for violation in violations
    )


def test_accepts_claim_preserving_reconstruction() -> None:
    violations = find_claim_integrity_violations(
        source_text=(
            "I have hands-on experience designing "
            "production-grade generative AI systems across "
            "RAG and agentic workflows."
        ),
        rewritten_text=(
            "I design production-grade generative AI systems "
            "and have hands-on experience across RAG and "
            "agentic workflows."
        ),
    )

    assert violations == []
