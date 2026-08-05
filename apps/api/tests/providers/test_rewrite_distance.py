from app.domain.models import RewriteIntensity
from app.providers.rewrite_distance import evaluate_rewrite_distance

SOURCE = (
    "I have hands-on experience designing generative AI systems across RAG and agentic workflows."
)


def test_deep_reconstruction_rejects_source_no_op() -> None:
    result = evaluate_rewrite_distance(
        source_text=SOURCE,
        rewritten_text=SOURCE,
        intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
    )

    assert result.acceptable is False
    assert result.changed_token_count == 0
    assert result.similarity_ratio == 1.0
    assert "identical" in result.reason


def test_deep_reconstruction_accepts_claim_preserving_reordering() -> None:
    result = evaluate_rewrite_distance(
        source_text=SOURCE,
        rewritten_text=(
            "Across RAG and agentic workflows, I have hands-on "
            "experience designing generative AI systems."
        ),
        intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
    )

    assert result.acceptable is True
    assert result.changed_token_count >= 3


def test_deep_reconstruction_rejects_punctuation_only_change() -> None:
    result = evaluate_rewrite_distance(
        source_text=SOURCE,
        rewritten_text=SOURCE.replace(".", "!"),
        intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
    )

    assert result.acceptable is False
    assert result.changed_token_count == 0


def test_light_polish_accepts_small_textual_change() -> None:
    result = evaluate_rewrite_distance(
        source_text="This system is reliable",
        rewritten_text="This system is reliable.",
        intensity=RewriteIntensity.LIGHT_EDIT,
    )

    assert result.acceptable is True
