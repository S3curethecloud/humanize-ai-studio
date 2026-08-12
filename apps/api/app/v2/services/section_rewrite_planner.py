from __future__ import annotations

import hashlib
import json

from app.v2.domain.long_documents import (
    DocumentStructure,
    SectionRewriteDisposition,
    SectionRewritePlan,
    SectionRewritePlanEntry,
)

SECTION_REWRITE_PLAN_VERSION = "section-rewrite-plan-v1"

_REWRITE_RATIONALE = "Section is eligible for deterministic rewrite planning."

_PRESERVE_RATIONALE = "Section is not eligible for rewrite and must be preserved."


class SectionRewritePlanner:
    version = SECTION_REWRITE_PLAN_VERSION

    def plan(
        self,
        *,
        structure: DocumentStructure,
    ) -> SectionRewritePlan:
        entries = tuple(
            self._entry_for_section(
                section_id=section.section_id,
                ordinal=section.ordinal,
                eligible_for_rewrite=(section.eligible_for_rewrite),
            )
            for section in structure.sections
        )

        plan = SectionRewritePlan(
            plan_id=self._plan_id(
                structure=structure,
            ),
            structure_id=structure.structure_id,
            entries=entries,
        )

        self._require_structural_authority(
            structure=structure,
            plan=plan,
        )

        return plan

    def _entry_for_section(
        self,
        *,
        section_id: str,
        ordinal: int,
        eligible_for_rewrite: bool,
    ) -> SectionRewritePlanEntry:
        if eligible_for_rewrite:
            return SectionRewritePlanEntry(
                section_id=section_id,
                ordinal=ordinal,
                disposition=(SectionRewriteDisposition.REWRITE),
                rationale=_REWRITE_RATIONALE,
            )

        return SectionRewritePlanEntry(
            section_id=section_id,
            ordinal=ordinal,
            disposition=(SectionRewriteDisposition.PRESERVE),
            rationale=_PRESERVE_RATIONALE,
        )

    def _require_structural_authority(
        self,
        *,
        structure: DocumentStructure,
        plan: SectionRewritePlan,
    ) -> None:
        if plan.structure_id != structure.structure_id:
            raise ValueError("section rewrite plan structure ID must match document structure")

        if len(plan.entries) != len(structure.sections):
            raise ValueError(
                "section rewrite plan must contain exactly one entry for every document section"
            )

        expected_ids = tuple(section.section_id for section in structure.sections)

        actual_ids = tuple(entry.section_id for entry in plan.entries)

        if actual_ids != expected_ids:
            raise ValueError("section rewrite plan section IDs must match document structure order")

        expected_ordinals = tuple(section.ordinal for section in structure.sections)

        actual_ordinals = tuple(entry.ordinal for entry in plan.entries)

        if actual_ordinals != expected_ordinals:
            raise ValueError("section rewrite plan ordinals must match document structure order")

        for section, entry in zip(
            structure.sections,
            plan.entries,
            strict=True,
        ):
            if (
                not section.eligible_for_rewrite
                and entry.disposition is not SectionRewriteDisposition.PRESERVE
            ):
                raise ValueError("ineligible document sections must be preserved")

    def _plan_id(
        self,
        *,
        structure: DocumentStructure,
    ) -> str:
        payload = {
            "plan_version": self.version,
            "document_structure": (
                structure.model_dump(
                    mode="json",
                )
            ),
        }

        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()

        digest = hashlib.sha256(canonical).hexdigest()[:24]

        return f"section-rewrite-plan-{digest}"
