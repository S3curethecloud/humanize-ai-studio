from app.evaluation.text_normalization import normalize_evaluation_text


def test_normalizes_narrow_no_break_spaces() -> None:
    assert normalize_evaluation_text("August\u202f8,\u202f2026") == normalize_evaluation_text(
        "August 8, 2026"
    )


def test_normalizes_non_breaking_hyphens() -> None:
    assert normalize_evaluation_text("least\u2011privilege") == normalize_evaluation_text(
        "least-privilege"
    )


def test_normalizes_case_and_quote_punctuation() -> None:
    assert normalize_evaluation_text(
        '"The model proposes; the verifier decides."'
    ) == normalize_evaluation_text("the model proposes, the verifier decides")


def test_preserves_numbers_currency_and_percentages() -> None:
    normalized = normalize_evaluation_text("$75,000 at 99.9% availability")

    assert "$75 000" in normalized
    assert "99.9%" in normalized
