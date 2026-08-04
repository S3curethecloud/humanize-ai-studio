from app.domain.models import ProtectedFact, ReleaseDecision, TextSpan
from app.services.verifier import RewriteVerifier


def number_fact(value: str = "30") -> ProtectedFact:
    return ProtectedFact(
        fact_id="number-1",
        value=value,
        fact_type="number",
        source_span=TextSpan(start=0, end=len(value)),
    )


def date_fact(value: str = "August 4, 2026") -> ProtectedFact:
    return ProtectedFact(
        fact_id="date-1",
        value=value,
        fact_type="date",
        source_span=TextSpan(start=0, end=len(value)),
    )


def test_verifier_passes_when_protected_number_is_preserved() -> None:
    verifier = RewriteVerifier()

    result = verifier.verify(
        source_text="The migration took 30 days.",
        rewritten_text="The team completed the migration in 30 days.",
        protected_facts=[number_fact()],
    )

    assert result.decision is ReleaseDecision.PASS
    assert result.preserved_facts == ["number-1"]
    assert result.missing_facts == []
    assert result.unexpected_facts == []


def test_verifier_fails_when_protected_number_is_removed() -> None:
    verifier = RewriteVerifier()

    result = verifier.verify(
        source_text="The migration took 30 days.",
        rewritten_text="The team completed the migration.",
        protected_facts=[number_fact()],
    )

    assert result.decision is ReleaseDecision.FAIL
    assert result.missing_facts == ["number-1"]
    assert result.unexpected_facts == []
    assert result.warnings == ["One or more protected facts were removed or changed."]


def test_verifier_fails_when_protected_date_is_changed() -> None:
    verifier = RewriteVerifier()

    result = verifier.verify(
        source_text="The review is scheduled for August 4, 2026.",
        rewritten_text="The review is scheduled for August 5, 2026.",
        protected_facts=[date_fact()],
    )

    assert result.decision is ReleaseDecision.FAIL
    assert result.missing_facts == ["date-1"]
    assert result.unexpected_facts == ["August 5, 2026"]
    assert result.warnings == [
        "One or more protected facts were removed or changed.",
        "The rewrite introduced numbers or dates not present in the source.",
    ]


def test_verifier_warns_when_new_number_is_introduced() -> None:
    verifier = RewriteVerifier()

    result = verifier.verify(
        source_text="The migration was completed.",
        rewritten_text="The migration was completed in 14 days.",
        protected_facts=[],
    )

    assert result.decision is ReleaseDecision.WARN
    assert result.missing_facts == []
    assert result.unexpected_facts == ["14"]
    assert result.warnings == ["The rewrite introduced numbers or dates not present in the source."]


def test_verifier_does_not_double_count_numbers_inside_dates() -> None:
    verifier = RewriteVerifier()

    result = verifier.verify(
        source_text="The review is scheduled for August 4, 2026.",
        rewritten_text="The architecture review is scheduled for August 4, 2026.",
        protected_facts=[date_fact()],
    )

    assert result.decision is ReleaseDecision.PASS
    assert result.preserved_facts == ["date-1"]
    assert result.unexpected_facts == []
