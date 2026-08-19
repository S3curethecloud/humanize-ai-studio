from app.services.rewrite_necessity import (
    RewriteDecision,
    RewriteNecessityAnalyzer,
    RewriteNecessityRequest,
    RewriteNecessityResult,
    RewriteSignalType,
)


def analyze(
    text: str,
    *,
    intensity: str = "natural_rewrite",
) -> RewriteNecessityResult:
    return RewriteNecessityAnalyzer().analyze(
        RewriteNecessityRequest(
            text=text,
            intensity=intensity,
        )
    )


def test_natural_rewrite_clear_text_requires_provider() -> None:
    result = analyze(
        "The policy engine evaluates every proposed tool call before execution."
    )

    assert result.decision is RewriteDecision.FULL_REWRITE
    assert result.candidate_text is None
    assert result.provider_required is True
    assert any(
        signal.signal_type
        is RewriteSignalType.INTENSITY_REQUEST
        for signal in result.signals
    )


def test_natural_rewrite_formulaic_text_requires_provider() -> None:
    result = analyze(
        "Furthermore, the migration completed in 30 days."
    )

    assert result.decision is RewriteDecision.FULL_REWRITE
    assert result.provider_required is True
    assert result.candidate_text is None
    assert any(
        signal.signal_type
        is RewriteSignalType.FORMULAIC_LANGUAGE
        for signal in result.signals
    )
    assert any(
        signal.signal_type
        is RewriteSignalType.INTENSITY_REQUEST
        for signal in result.signals
    )


def test_light_edit_clear_text_preserves_exact_text() -> None:
    text = (
        "The gateway validates identity context "
        "and creates an audit trace."
    )

    result = analyze(
        text,
        intensity="light_edit",
    )

    assert result.decision is RewriteDecision.NO_CHANGE
    assert result.original_text == text
    assert result.candidate_text == text
    assert result.provider_required is False


def test_light_edit_formulaic_transition_is_deterministic() -> None:
    result = analyze(
        "Furthermore, the migration completed in 30 days.",
        intensity="light_edit",
    )

    assert result.decision is RewriteDecision.MINIMAL_EDIT
    assert result.provider_required is False
    assert result.candidate_text == (
        "The migration completed in 30 days."
    )


def test_light_edit_removes_multiple_formulaic_phrases() -> None:
    result = analyze(
        (
            "Moreover, it is important to note that "
            "the service remained available."
        ),
        intensity="light_edit",
    )

    assert result.decision is RewriteDecision.MINIMAL_EDIT
    assert result.candidate_text == (
        "The service remained available."
    )


def test_light_edit_preserves_numbers() -> None:
    result = analyze(
        (
            "Additionally, the platform processed "
            "12,000 requests with 99.9% availability."
        ),
        intensity="light_edit",
    )

    assert result.decision is RewriteDecision.MINIMAL_EDIT
    assert result.candidate_text is not None
    assert "12,000" in result.candidate_text
    assert "99.9%" in result.candidate_text


def test_repeated_sentence_openings_require_provider() -> None:
    result = analyze(
        (
            "The platform provides governance controls. "
            "The platform provides trace evidence. "
            "The platform provides policy enforcement. "
            "This system records audit evidence. "
            "This system records policy outcomes. "
            "This system records execution history."
        ),
        intensity="light_edit",
    )

    assert result.decision is RewriteDecision.FULL_REWRITE
    assert result.provider_required is True
    assert result.candidate_text is None
    assert any(
        signal.signal_type
        is RewriteSignalType.REPETITION
        for signal in result.signals
    )


def test_long_sentence_requires_provider() -> None:
    sentence = " ".join(
        [
            "The",
            "platform",
            "coordinates",
            *["multiple"] * 43,
            "controls.",
        ]
    )

    result = analyze(
        sentence,
        intensity="light_edit",
    )

    assert result.decision is RewriteDecision.FULL_REWRITE
    assert result.provider_required is True
    assert any(
        signal.signal_type
        is RewriteSignalType.VERBOSITY
        for signal in result.signals
    )


def test_explicit_full_rewrite_intensity_requires_provider() -> None:
    result = analyze(
        "The policy engine evaluates tool calls.",
        intensity="full_rewrite",
    )

    assert result.decision is RewriteDecision.FULL_REWRITE
    assert result.provider_required is True
    assert result.candidate_text is None


def test_substantial_rewrite_intensity_requires_provider() -> None:
    result = analyze(
        "The policy engine evaluates tool calls.",
        intensity="substantial_rewrite",
    )

    assert result.decision is RewriteDecision.FULL_REWRITE
    assert result.provider_required is True


def test_deep_reconstruction_requires_provider() -> None:
    result = analyze(
        "The policy engine evaluates tool calls.",
        intensity="deep_reconstruction",
    )

    assert result.decision is RewriteDecision.FULL_REWRITE
    assert result.provider_required is True
    assert any(
        signal.signal_type
        is RewriteSignalType.INTENSITY_REQUEST
        for signal in result.signals
    )


def test_full_rewrite_has_auditable_rationale() -> None:
    result = analyze(
        "The platform provides controls. "
        "The platform provides evidence. "
        "The platform provides enforcement."
    )

    assert result.decision is RewriteDecision.FULL_REWRITE
    assert result.rationale
    assert result.signals


def test_analyzer_is_deterministic() -> None:
    request = RewriteNecessityRequest(
        text=(
            "Additionally, the service "
            "processed 12,000 requests."
        )
    )
    analyzer = RewriteNecessityAnalyzer()

    first = analyzer.analyze(request)
    second = analyzer.analyze(request)

    assert first == second
