from app.domain.models import ReleaseDecision
from app.services.fact_extractor import FactExtractor
from app.services.fact_normalization import normalize_fact_text
from app.services.verifier import RewriteVerifier


def test_fact_normalization_preserves_character_count() -> None:
    source = "August\u202f8,\u202f2026"

    normalized = normalize_fact_text(source)

    assert normalized == "August 8, 2026"
    assert len(normalized) == len(source)


def test_extractor_recognizes_date_with_narrow_no_break_spaces() -> None:
    extractor = FactExtractor()

    facts = extractor.extract(
        "Please respond by August\u202f8,\u202f2026.",
        preserve_numbers=True,
        preserve_dates=True,
    )

    assert len(facts) == 1
    assert facts[0].fact_id == "date-1"
    assert facts[0].fact_type == "date"
    assert facts[0].value == "August 8, 2026"


def test_verifier_accepts_unicode_equivalent_date() -> None:
    extractor = FactExtractor()
    verifier = RewriteVerifier()

    source = "Please respond by August 8, 2026."
    rewrite = "Please respond by August\u202f8,\u202f2026."

    facts = extractor.extract(
        source,
        preserve_numbers=True,
        preserve_dates=True,
    )

    result = verifier.verify(
        source_text=source,
        rewritten_text=rewrite,
        protected_facts=facts,
    )

    assert result.decision == ReleaseDecision.PASS
    assert result.preserved_facts == ["date-1"]
    assert result.missing_facts == []
    assert result.unexpected_facts == []


def test_verifier_rejects_changed_unicode_spaced_date() -> None:
    extractor = FactExtractor()
    verifier = RewriteVerifier()

    source = "Please respond by August 8, 2026."
    rewrite = "Please respond by August\u202f9,\u202f2026."

    facts = extractor.extract(
        source,
        preserve_numbers=True,
        preserve_dates=True,
    )

    result = verifier.verify(
        source_text=source,
        rewritten_text=rewrite,
        protected_facts=facts,
    )

    assert result.decision == ReleaseDecision.FAIL
    assert result.preserved_facts == []
    assert result.missing_facts == ["date-1"]
    assert result.unexpected_facts == ["August 9, 2026"]
