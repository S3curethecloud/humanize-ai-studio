from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

MAX_LONG_DOCUMENT_CHARS = 1_000_000


class SectionRewriteDisposition(StrEnum):
    REWRITE = "rewrite"
    PRESERVE = "preserve"


class DocumentSection(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(
        ge=1,
    )
    start_offset: int = Field(
        ge=0,
    )
    end_offset: int = Field(
        ge=1,
    )
    source_text: str = Field(
        min_length=1,
        max_length=MAX_LONG_DOCUMENT_CHARS,
    )
    heading: str | None = Field(
        default=None,
        max_length=500,
    )
    eligible_for_rewrite: bool = True

    @model_validator(mode="after")
    def require_valid_source_span(
        self,
    ) -> DocumentSection:
        if self.end_offset <= self.start_offset:
            raise ValueError("section end offset must be greater than start offset")

        expected_length = self.end_offset - self.start_offset

        if len(self.source_text) != expected_length:
            raise ValueError("section source text length must match source span")

        return self


class DocumentStructure(BaseModel):
    model_config = ConfigDict(frozen=True)

    structure_id: str = Field(
        min_length=1,
        max_length=200,
    )
    source_text: str = Field(
        min_length=1,
        max_length=MAX_LONG_DOCUMENT_CHARS,
    )
    sections: tuple[
        DocumentSection,
        ...,
    ] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def require_lossless_ordered_structure(
        self,
    ) -> DocumentStructure:
        section_ids = tuple(section.section_id for section in self.sections)

        if len(set(section_ids)) != len(section_ids):
            raise ValueError("document section IDs must be unique")

        ordinals = tuple(section.ordinal for section in self.sections)

        expected_ordinals = tuple(
            range(
                1,
                len(self.sections) + 1,
            )
        )

        if ordinals != expected_ordinals:
            raise ValueError("document section ordinals must be contiguous and ordered from 1")

        if self.sections[0].start_offset != 0:
            raise ValueError("first document section must start at offset 0")

        previous_end = 0

        for section in self.sections:
            if section.start_offset != previous_end:
                raise ValueError(
                    "document sections must provide contiguous non-overlapping source coverage"
                )

            expected_source_text = self.source_text[section.start_offset : section.end_offset]

            if section.source_text != expected_source_text:
                raise ValueError(
                    "document section source text must match the original document span"
                )

            previous_end = section.end_offset

        if previous_end != len(self.source_text):
            raise ValueError("document sections must cover the complete original document")

        reconstructed_source = "".join(section.source_text for section in self.sections)

        if reconstructed_source != self.source_text:
            raise ValueError("document sections must reconstruct the exact original document")

        return self


class SectionRewritePlanEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(
        ge=1,
    )
    disposition: SectionRewriteDisposition
    rationale: str = Field(
        min_length=1,
        max_length=2_000,
    )


class SectionRewritePlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(
        min_length=1,
        max_length=200,
    )
    structure_id: str = Field(
        min_length=1,
        max_length=200,
    )
    entries: tuple[
        SectionRewritePlanEntry,
        ...,
    ] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def require_ordered_unique_entries(
        self,
    ) -> SectionRewritePlan:
        section_ids = tuple(entry.section_id for entry in self.entries)

        if len(set(section_ids)) != len(section_ids):
            raise ValueError("section rewrite plan IDs must be unique")

        ordinals = tuple(entry.ordinal for entry in self.entries)

        expected_ordinals = tuple(
            range(
                1,
                len(self.entries) + 1,
            )
        )

        if ordinals != expected_ordinals:
            raise ValueError("section rewrite plan ordinals must be contiguous and ordered from 1")

        return self


class SectionRewriteResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(
        ge=1,
    )
    disposition: SectionRewriteDisposition
    source_text: str = Field(
        min_length=1,
        max_length=MAX_LONG_DOCUMENT_CHARS,
    )
    rewritten_text: str = Field(
        min_length=1,
        max_length=MAX_LONG_DOCUMENT_CHARS,
    )

    @model_validator(mode="after")
    def require_preserved_section_integrity(
        self,
    ) -> SectionRewriteResult:
        if (
            self.disposition is SectionRewriteDisposition.PRESERVE
            and self.rewritten_text != self.source_text
        ):
            raise ValueError("preserved section rewritten text must match source text exactly")

        return self


class DocumentReconstruction(BaseModel):
    model_config = ConfigDict(frozen=True)

    structure: DocumentStructure
    section_results: tuple[
        SectionRewriteResult,
        ...,
    ] = Field(
        min_length=1,
    )
    reconstructed_text: str = Field(
        min_length=1,
        max_length=MAX_LONG_DOCUMENT_CHARS,
    )

    @model_validator(mode="after")
    def require_reconstruction_integrity(
        self,
    ) -> DocumentReconstruction:
        if len(self.section_results) != len(self.structure.sections):
            raise ValueError(
                "document reconstruction must contain exactly one result for every source section"
            )

        expected_ids = tuple(section.section_id for section in self.structure.sections)

        actual_ids = tuple(result.section_id for result in self.section_results)

        if actual_ids != expected_ids:
            raise ValueError(
                "document reconstruction section IDs must match source structure order"
            )

        expected_ordinals = tuple(section.ordinal for section in self.structure.sections)

        actual_ordinals = tuple(result.ordinal for result in self.section_results)

        if actual_ordinals != expected_ordinals:
            raise ValueError("document reconstruction ordinals must match source structure order")

        for source_section, result in zip(
            self.structure.sections,
            self.section_results,
            strict=True,
        ):
            if result.source_text != source_section.source_text:
                raise ValueError(
                    "document reconstruction result source text must match its source section"
                )

        expected_reconstruction = "".join(result.rewritten_text for result in self.section_results)

        if self.reconstructed_text != expected_reconstruction:
            raise ValueError(
                "reconstructed document text must equal the ordered rewritten section results"
            )

        return self
