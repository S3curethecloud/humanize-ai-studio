from app.domain.models import RewriteIntensity
from app.providers.rewrite_distance import (
    evaluate_rewrite_distance,
)

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
    assert result.moved_token_count == 0
    assert result.similarity_ratio == 1.0
    assert "identical" in result.reason


def test_deep_reconstruction_accepts_information_reordering() -> None:
    result = evaluate_rewrite_distance(
        source_text=SOURCE,
        rewritten_text=(
            "Across RAG and agentic workflows, I have "
            "hands-on experience designing generative "
            "AI systems."
        ),
        intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
    )

    assert result.acceptable is True
    assert result.changed_token_count >= 3
    assert result.moved_token_count >= 3


def test_deep_reconstruction_accepts_sentence_restructuring() -> None:
    source = "I design generative AI systems. I work across RAG and agentic workflows."
    rewritten = "I design generative AI systems across RAG and agentic workflows."

    result = evaluate_rewrite_distance(
        source_text=source,
        rewritten_text=rewritten,
        intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
    )

    assert result.acceptable is True
    assert result.changed_token_count >= 1
    assert result.source_sentence_count == 2
    assert result.rewritten_sentence_count == 1


def test_deep_reconstruction_rejects_lexical_only_substitution() -> None:
    source = (
        "In my current role, I combine multi-stage "
        "retrieval, hybrid search, reranking, vector "
        "databases, and LLM APIs."
    )
    rewritten = (
        "In my current role, I work with technologies "
        "including multi-stage retrieval, hybrid search, "
        "reranking, vector databases, and LLM APIs."
    )

    result = evaluate_rewrite_distance(
        source_text=source,
        rewritten_text=rewritten,
        intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
    )

    assert result.changed_token_count >= 3
    assert result.moved_token_count < 3
    assert result.acceptable is False
    assert "information order" in result.reason


def test_deep_reconstruction_rejects_punctuation_only_change() -> None:
    result = evaluate_rewrite_distance(
        source_text=SOURCE,
        rewritten_text=SOURCE.replace(".", "!"),
        intensity=RewriteIntensity.DEEP_RECONSTRUCTION,
    )

    assert result.acceptable is False
    assert result.changed_token_count == 0
    assert result.moved_token_count == 0


def test_natural_rewrite_accepts_lexical_change_without_reordering() -> None:
    result = evaluate_rewrite_distance(
        source_text="The platform is reliable.",
        rewritten_text="The platform remains reliable.",
        intensity=RewriteIntensity.NATURAL_REWRITE,
    )

    assert result.acceptable is True
    assert result.changed_token_count >= 1
    assert result.moved_token_count == 0


def test_light_edit_accepts_small_textual_change() -> None:
    result = evaluate_rewrite_distance(
        source_text="This system is reliable",
        rewritten_text="This system is reliable.",
        intensity=RewriteIntensity.LIGHT_EDIT,
    )

    assert result.acceptable is True
