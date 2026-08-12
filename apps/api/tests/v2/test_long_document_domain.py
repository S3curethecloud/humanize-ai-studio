from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.v2.domain.long_documents import (
    DocumentReconstruction,
    DocumentSection,
    DocumentStructure,
    SectionRewriteDisposition,
    SectionRewritePlan,
    SectionRewritePlanEntry,
    SectionRewriteResult,
)

SOURCE = (
    "# Overview\n"
    "Project Atlas completed the review.\n"
    "\n"
    "# Financials\n"
    "Revenue was 42 million in 2025.\n"
)

SECTION_ONE = "# Overview\nProject Atlas completed the review.\n\n"

SECTION_TWO = "# Financials\nRevenue was 42 million in 2025.\n"


def _section_one() -> DocumentSection:
    return DocumentSection(
        section_id="section-1",
        ordinal=1,
        start_offset=0,
        end_offset=len(SECTION_ONE),
        source_text=SECTION_ONE,
        heading="Overview",
        eligible_for_rewrite=True,
    )


def _section_two() -> DocumentSection:
    return DocumentSection(
        section_id="section-2",
        ordinal=2,
        start_offset=len(SECTION_ONE),
        end_offset=len(SOURCE),
        source_text=SECTION_TWO,
        heading="Financials",
        eligible_for_rewrite=True,
    )


def _structure() -> DocumentStructure:
    return DocumentStructure(
        structure_id="structure-1",
        source_text=SOURCE,
        sections=(
            _section_one(),
            _section_two(),
        ),
    )


def _rewrite_result_one() -> SectionRewriteResult:
    return SectionRewriteResult(
        section_id="section-1",
        ordinal=1,
        disposition=SectionRewriteDisposition.REWRITE,
        source_text=SECTION_ONE,
        rewritten_text=("# Overview\nThe Project Atlas review is complete.\n\n"),
    )


def _rewrite_result_two() -> SectionRewriteResult:
    return SectionRewriteResult(
        section_id="section-2",
        ordinal=2,
        disposition=SectionRewriteDisposition.REWRITE,
        source_text=SECTION_TWO,
        rewritten_text=("# Financials\nIn 2025, revenue was 42 million.\n"),
    )


def test_document_section_accepts_exact_source_span() -> None:
    section = _section_one()

    assert section.end_offset - section.start_offset == len(section.source_text)


def test_document_section_rejects_invalid_span_order() -> None:
    with pytest.raises(
        ValidationError,
        match="end offset must be greater",
    ):
        DocumentSection(
            section_id="section-1",
            ordinal=1,
            start_offset=10,
            end_offset=5,
            source_text="abcde",
        )


def test_document_section_rejects_span_length_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="source text length must match source span",
    ):
        DocumentSection(
            section_id="section-1",
            ordinal=1,
            start_offset=0,
            end_offset=10,
            source_text="short",
        )


def test_document_structure_accepts_lossless_ordered_sections() -> None:
    structure = _structure()

    assert "".join(section.source_text for section in structure.sections) == SOURCE


def test_document_structure_rejects_duplicate_section_ids() -> None:
    second = _section_two().model_copy(
        update={
            "section_id": "section-1",
        }
    )

    with pytest.raises(
        ValidationError,
        match="document section IDs must be unique",
    ):
        DocumentStructure(
            structure_id="structure-1",
            source_text=SOURCE,
            sections=(
                _section_one(),
                second,
            ),
        )


def test_document_structure_rejects_noncontiguous_ordinals() -> None:
    second = _section_two().model_copy(
        update={
            "ordinal": 3,
        }
    )

    with pytest.raises(
        ValidationError,
        match="ordinals must be contiguous",
    ):
        DocumentStructure(
            structure_id="structure-1",
            source_text=SOURCE,
            sections=(
                _section_one(),
                second,
            ),
        )


def test_document_structure_rejects_source_coverage_gap() -> None:
    second = _section_two().model_copy(
        update={
            "start_offset": len(SECTION_ONE) + 1,
            "end_offset": len(SOURCE) + 1,
        }
    )

    with pytest.raises(
        ValidationError,
        match="contiguous non-overlapping source coverage",
    ):
        DocumentStructure(
            structure_id="structure-1",
            source_text=SOURCE,
            sections=(
                _section_one(),
                second,
            ),
        )


def test_document_structure_rejects_source_span_text_mismatch() -> None:
    replacement = SECTION_TWO.replace(
        "Revenue",
        "Income ",
        1,
    )

    second = _section_two().model_copy(
        update={
            "source_text": replacement,
        }
    )

    with pytest.raises(
        ValidationError,
        match="source text must match the original document span",
    ):
        DocumentStructure(
            structure_id="structure-1",
            source_text=SOURCE,
            sections=(
                _section_one(),
                second,
            ),
        )


def test_section_rewrite_plan_accepts_ordered_unique_entries() -> None:
    plan = SectionRewritePlan(
        plan_id="plan-1",
        structure_id="structure-1",
        entries=(
            SectionRewritePlanEntry(
                section_id="section-1",
                ordinal=1,
                disposition=SectionRewriteDisposition.REWRITE,
                rationale="Narrative section is eligible.",
            ),
            SectionRewritePlanEntry(
                section_id="section-2",
                ordinal=2,
                disposition=SectionRewriteDisposition.PRESERVE,
                rationale="Preserve controlled section.",
            ),
        ),
    )

    assert tuple(entry.section_id for entry in plan.entries) == (
        "section-1",
        "section-2",
    )


def test_section_rewrite_plan_rejects_duplicate_section_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="section rewrite plan IDs must be unique",
    ):
        SectionRewritePlan(
            plan_id="plan-1",
            structure_id="structure-1",
            entries=(
                SectionRewritePlanEntry(
                    section_id="section-1",
                    ordinal=1,
                    disposition=SectionRewriteDisposition.REWRITE,
                    rationale="Rewrite.",
                ),
                SectionRewritePlanEntry(
                    section_id="section-1",
                    ordinal=2,
                    disposition=SectionRewriteDisposition.PRESERVE,
                    rationale="Preserve.",
                ),
            ),
        )


def test_section_rewrite_plan_rejects_noncontiguous_ordinals() -> None:
    with pytest.raises(
        ValidationError,
        match="plan ordinals must be contiguous",
    ):
        SectionRewritePlan(
            plan_id="plan-1",
            structure_id="structure-1",
            entries=(
                SectionRewritePlanEntry(
                    section_id="section-1",
                    ordinal=1,
                    disposition=SectionRewriteDisposition.REWRITE,
                    rationale="Rewrite.",
                ),
                SectionRewritePlanEntry(
                    section_id="section-2",
                    ordinal=3,
                    disposition=SectionRewriteDisposition.REWRITE,
                    rationale="Rewrite.",
                ),
            ),
        )


def test_preserved_section_result_must_remain_byte_for_byte_equal() -> None:
    with pytest.raises(
        ValidationError,
        match="preserved section rewritten text must match",
    ):
        SectionRewriteResult(
            section_id="section-1",
            ordinal=1,
            disposition=SectionRewriteDisposition.PRESERVE,
            source_text=SECTION_ONE,
            rewritten_text="Changed text.",
        )


def test_document_reconstruction_accepts_complete_ordered_results() -> None:
    first = _rewrite_result_one()
    second = _rewrite_result_two()

    reconstructed_text = first.rewritten_text + second.rewritten_text

    reconstruction = DocumentReconstruction(
        structure=_structure(),
        section_results=(
            first,
            second,
        ),
        reconstructed_text=reconstructed_text,
    )

    assert reconstruction.reconstructed_text == (reconstructed_text)


def test_document_reconstruction_rejects_missing_section_result() -> None:
    first = _rewrite_result_one()

    with pytest.raises(
        ValidationError,
        match="exactly one result for every source section",
    ):
        DocumentReconstruction(
            structure=_structure(),
            section_results=(first,),
            reconstructed_text=first.rewritten_text,
        )


def test_document_reconstruction_rejects_reordered_section_ids() -> None:
    first = _rewrite_result_one()
    second = _rewrite_result_two()

    with pytest.raises(
        ValidationError,
        match="section IDs must match source structure order",
    ):
        DocumentReconstruction(
            structure=_structure(),
            section_results=(
                second,
                first,
            ),
            reconstructed_text=(second.rewritten_text + first.rewritten_text),
        )


def test_document_reconstruction_rejects_source_text_mutation() -> None:
    first = _rewrite_result_one().model_copy(
        update={
            "source_text": "Tampered source.",
        }
    )

    second = _rewrite_result_two()

    with pytest.raises(
        ValidationError,
        match="result source text must match its source section",
    ):
        DocumentReconstruction(
            structure=_structure(),
            section_results=(
                first,
                second,
            ),
            reconstructed_text=(first.rewritten_text + second.rewritten_text),
        )


def test_document_reconstruction_rejects_output_text_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="reconstructed document text must equal",
    ):
        DocumentReconstruction(
            structure=_structure(),
            section_results=(
                _rewrite_result_one(),
                _rewrite_result_two(),
            ),
            reconstructed_text="Incomplete reconstruction.",
        )
