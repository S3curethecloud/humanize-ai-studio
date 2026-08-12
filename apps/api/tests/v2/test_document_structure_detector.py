from __future__ import annotations

import pytest

from app.v2.services.document_structure_detector import (
    DOCUMENT_STRUCTURE_DETECTOR_VERSION,
    DocumentStructureDetector,
)


def _detector() -> DocumentStructureDetector:
    return DocumentStructureDetector()


def test_detector_version_is_frozen_v1_contract() -> None:
    assert DOCUMENT_STRUCTURE_DETECTOR_VERSION == "document-structure-v1"


def test_plain_document_falls_back_to_single_section() -> None:
    source = "Project Atlas completed the review.\nRevenue was 42 million in 2025.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert len(structure.sections) == 1

    section = structure.sections[0]

    assert section.ordinal == 1
    assert section.start_offset == 0
    assert section.end_offset == len(source)
    assert section.source_text == source
    assert section.heading is None


def test_markdown_headings_create_ordered_sections() -> None:
    source = (
        "# Overview\n"
        "Project Atlas completed the review.\n"
        "\n"
        "## Financials\n"
        "Revenue was 42 million in 2025.\n"
    )

    structure = _detector().detect(
        source_text=source,
    )

    assert tuple(section.heading for section in structure.sections) == (
        "Overview",
        "Financials",
    )

    assert tuple(section.ordinal for section in structure.sections) == (
        1,
        2,
    )


def test_preamble_before_first_heading_is_preserved() -> None:
    source = "Executive summary.\n\n# Overview\nProject Atlas completed the review.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert len(structure.sections) == 2

    preamble = structure.sections[0]
    overview = structure.sections[1]

    assert preamble.heading is None
    assert preamble.source_text == ("Executive summary.\n\n")

    assert overview.heading == "Overview"
    assert overview.source_text == ("# Overview\nProject Atlas completed the review.\n")


def test_detector_preserves_exact_document_character_coverage() -> None:
    source = "Preface\r\n\r\n# First\r\nAlpha.\r\n\r\n## Second\r\nBeta.\r\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert "".join(section.source_text for section in structure.sections) == source

    assert structure.sections[0].start_offset == 0
    assert structure.sections[-1].end_offset == len(source)

    for previous, current in zip(
        structure.sections,
        structure.sections[1:],
        strict=False,
    ):
        assert previous.end_offset == current.start_offset


def test_heading_line_remains_inside_its_section() -> None:
    source = "# Overview\nBody one.\n## Details\nBody two.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert structure.sections[0].source_text == ("# Overview\nBody one.\n")

    assert structure.sections[1].source_text == ("## Details\nBody two.\n")


def test_heading_levels_one_through_six_are_supported() -> None:
    source = "# One\nA\n## Two\nB\n### Three\nC\n#### Four\nD\n##### Five\nE\n###### Six\nF\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert tuple(section.heading for section in structure.sections) == (
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
    )


def test_seven_hashes_are_not_treated_as_heading() -> None:
    source = "####### Not a supported heading\nBody text.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert len(structure.sections) == 1
    assert structure.sections[0].heading is None
    assert structure.sections[0].source_text == source


def test_hash_without_required_separator_is_not_heading() -> None:
    source = "#NotAHeading\nBody text.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert len(structure.sections) == 1
    assert structure.sections[0].heading is None


def test_empty_heading_marker_is_not_heading() -> None:
    source = "###   \nBody text.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert len(structure.sections) == 1
    assert structure.sections[0].heading is None


def test_tab_after_marker_is_supported() -> None:
    source = "##\tFinancials\nRevenue was 42 million.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert len(structure.sections) == 1
    assert structure.sections[0].heading == ("Financials")


def test_structure_id_is_deterministic_for_same_document() -> None:
    source = "# Overview\nProject Atlas completed the review.\n"

    first = _detector().detect(
        source_text=source,
    )
    second = _detector().detect(
        source_text=source,
    )

    assert first.structure_id == second.structure_id

    assert tuple(section.section_id for section in first.sections) == tuple(
        section.section_id for section in second.sections
    )


def test_structure_id_changes_when_document_changes() -> None:
    first = _detector().detect(
        source_text=("# Overview\nVersion one.\n"),
    )

    second = _detector().detect(
        source_text=("# Overview\nVersion two.\n"),
    )

    assert first.structure_id != second.structure_id


def test_section_ids_are_stable_and_ordered() -> None:
    source = "# One\nAlpha.\n# Two\nBeta.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert tuple(section.section_id for section in structure.sections) == (
        f"{structure.structure_id}-section-1",
        f"{structure.structure_id}-section-2",
    )


def test_heading_detection_is_column_zero_only() -> None:
    source = "  # Indented text\nStill the same section.\n"

    structure = _detector().detect(
        source_text=source,
    )

    assert len(structure.sections) == 1
    assert structure.sections[0].heading is None


def test_empty_document_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="source_text must not be empty",
    ):
        _detector().detect(
            source_text="",
        )
