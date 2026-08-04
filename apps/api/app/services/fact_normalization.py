from __future__ import annotations

_TRANSLATION_TABLE = str.maketrans(
    {
        "\u00a0": " ",
        "\u202f": " ",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)


def normalize_fact_text(text: str) -> str:
    """Normalize visually equivalent fact characters without changing length."""
    return text.translate(_TRANSLATION_TABLE)
