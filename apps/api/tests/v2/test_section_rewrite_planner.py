from __future__ import annotations

from app.v2.domain.long_documents import (
    DocumentSection,
    DocumentStructure,
    SectionRewriteDisposition,
)
from app.v2.services.document_structure_detector import (
    DocumentStructureDetector,
)
from app.v2.services.section_rewrite_planner import (
    SECTION_REWRITE_PLAN_VERSION,
    SectionRewritePlanner,
)


def _source() -> str:
    return (
        "# Overview\n"
        "Project Atlas completed the review.\n"
        "\n"
        "## Financials\n"
        "Revenue was 42 million in 2025.\n"
    )


def _structure() -> DocumentStructure:
    return DocumentStructureDetector().detect(
        source_text=_source(),
    )


def _mixed_eligibility_structure() -> DocumentStructure:
    structure = _structure()

    first = structure.sections[0]

    second = structure.sections[1].model_copy(
        update={
            "eligible_for_rewrite": False,
        }
    )

    return structure.model_copy(
        update={
            "sections": (
                first,
                second,
            ),
        }
    )


def test_plan_version_is_frozen_v1_contract() -> None:
    assert SECTION_REWRITE_PLAN_VERSION == "section-rewrite-plan-v1"


def test_planner_is_deterministic_for_same_structure() -> None:
    planner = SectionRewritePlanner()
    structure = _structure()

    first = planner.plan(
        structure=structure,
    )

    second = planner.plan(
        structure=structure,
    )

    assert first == second


def test_plan_preserves_structure_identity() -> None:
    structure = _structure()

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert plan.structure_id == structure.structure_id


def test_plan_has_exactly_one_entry_per_section() -> None:
    structure = _structure()

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert len(plan.entries) == len(structure.sections)


def test_plan_preserves_exact_section_ids_and_order() -> None:
    structure = _structure()

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert tuple(entry.section_id for entry in plan.entries) == tuple(
        section.section_id for section in structure.sections
    )


def test_plan_preserves_exact_section_ordinals() -> None:
    structure = _structure()

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert tuple(entry.ordinal for entry in plan.entries) == tuple(
        section.ordinal for section in structure.sections
    )


def test_eligible_sections_are_planned_for_rewrite() -> None:
    structure = _structure()

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert all(entry.disposition is SectionRewriteDisposition.REWRITE for entry in plan.entries)


def test_ineligible_section_is_forced_to_preserve() -> None:
    structure = _mixed_eligibility_structure()

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert plan.entries[0].disposition is SectionRewriteDisposition.REWRITE

    assert plan.entries[1].disposition is SectionRewriteDisposition.PRESERVE


def test_rationales_are_deterministic_and_policy_bound() -> None:
    structure = _mixed_eligibility_structure()

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert plan.entries[0].rationale == ("Section is eligible for deterministic rewrite planning.")

    assert plan.entries[1].rationale == (
        "Section is not eligible for rewrite and must be preserved."
    )


def test_plan_id_is_deterministic() -> None:
    structure = _structure()

    first = SectionRewritePlanner().plan(
        structure=structure,
    )

    second = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert first.plan_id == second.plan_id


def test_plan_id_changes_when_eligibility_changes() -> None:
    eligible = _structure()

    mixed = _mixed_eligibility_structure()

    eligible_plan = SectionRewritePlanner().plan(
        structure=eligible,
    )

    mixed_plan = SectionRewritePlanner().plan(
        structure=mixed,
    )

    assert eligible.structure_id == mixed.structure_id

    assert eligible_plan.plan_id != mixed_plan.plan_id


def test_plan_id_changes_for_different_document() -> None:
    first = DocumentStructureDetector().detect(
        source_text=("# Overview\nVersion one.\n"),
    )

    second = DocumentStructureDetector().detect(
        source_text=("# Overview\nVersion two.\n"),
    )

    first_plan = SectionRewritePlanner().plan(
        structure=first,
    )

    second_plan = SectionRewritePlanner().plan(
        structure=second,
    )

    assert first_plan.plan_id != second_plan.plan_id


def test_single_section_fallback_receives_complete_plan() -> None:
    structure = DocumentStructureDetector().detect(
        source_text=("Plain document without headings.\n"),
    )

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert len(plan.entries) == 1

    assert plan.entries[0].section_id == structure.sections[0].section_id

    assert plan.entries[0].ordinal == structure.sections[0].ordinal

    assert plan.entries[0].disposition is SectionRewriteDisposition.REWRITE


def test_all_ineligible_sections_are_preserved() -> None:
    source = "Alpha.Beta."

    first = DocumentSection(
        section_id="section-1",
        ordinal=1,
        start_offset=0,
        end_offset=6,
        source_text="Alpha.",
        heading=None,
        eligible_for_rewrite=False,
    )

    second = DocumentSection(
        section_id="section-2",
        ordinal=2,
        start_offset=6,
        end_offset=len(source),
        source_text="Beta.",
        heading=None,
        eligible_for_rewrite=False,
    )

    structure = DocumentStructure(
        structure_id="structure-controlled",
        source_text=source,
        sections=(
            first,
            second,
        ),
    )

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    assert all(entry.disposition is SectionRewriteDisposition.PRESERVE for entry in plan.entries)


def test_planning_does_not_mutate_document_structure() -> None:
    structure = _mixed_eligibility_structure()

    before = structure.model_dump(
        mode="json",
    )

    SectionRewritePlanner().plan(
        structure=structure,
    )

    after = structure.model_dump(
        mode="json",
    )

    assert after == before
