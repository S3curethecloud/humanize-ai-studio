from __future__ import annotations

from pydantic import ValidationError

from app.v2.domain.long_documents import (
    DocumentReconstruction,
    SectionRewriteDisposition,
)
from app.v2.services.long_document_control_evaluator import (
    LongDocumentControlEvaluation,
)


class DocumentReconstructionIntegrityError(RuntimeError):
    pass


class DocumentReconstructor:
    def reconstruct(
        self,
        *,
        evaluation: LongDocumentControlEvaluation,
    ) -> DocumentReconstruction:
        self._require_reconstruction_integrity(
            evaluation=evaluation,
        )

        execution = evaluation.execution

        reconstructed_text = "".join(result.rewritten_text for result in execution.results)

        try:
            return DocumentReconstruction(
                structure=execution.structure,
                section_results=execution.results,
                reconstructed_text=reconstructed_text,
            )
        except ValidationError as exc:
            raise DocumentReconstructionIntegrityError(
                "document reconstruction failed canonical domain integrity validation"
            ) from exc

    def _require_reconstruction_integrity(
        self,
        *,
        evaluation: LongDocumentControlEvaluation,
    ) -> None:
        if evaluation.v1_failed_section_ids:
            raise DocumentReconstructionIntegrityError(
                "document reconstruction cannot proceed "
                "when authoritative V1 section failures exist"
            )

        execution = evaluation.execution
        structure = execution.structure
        plan = execution.plan
        results = execution.results

        if plan.structure_id != structure.structure_id:
            raise DocumentReconstructionIntegrityError(
                "section rewrite plan structure ID must match document structure"
            )

        if len(plan.entries) != len(structure.sections):
            raise DocumentReconstructionIntegrityError(
                "section rewrite plan must contain exactly one entry for every document section"
            )

        if len(results) != len(structure.sections):
            raise DocumentReconstructionIntegrityError(
                "section rewrite execution must contain "
                "exactly one result for every document section"
            )

        for section, entry, result in zip(
            structure.sections,
            plan.entries,
            results,
            strict=True,
        ):
            if entry.section_id != section.section_id:
                raise DocumentReconstructionIntegrityError(
                    "section rewrite plan IDs must match document structure order"
                )

            if entry.ordinal != section.ordinal:
                raise DocumentReconstructionIntegrityError(
                    "section rewrite plan ordinals must match document structure order"
                )

            if result.section_id != section.section_id:
                raise DocumentReconstructionIntegrityError(
                    "section result IDs must match document structure order"
                )

            if result.ordinal != section.ordinal:
                raise DocumentReconstructionIntegrityError(
                    "section result ordinals must match document structure order"
                )

            if result.section_id != entry.section_id:
                raise DocumentReconstructionIntegrityError(
                    "section result IDs must match rewrite plan entries"
                )

            if result.ordinal != entry.ordinal:
                raise DocumentReconstructionIntegrityError(
                    "section result ordinals must match rewrite plan entries"
                )

            if result.disposition is not entry.disposition:
                raise DocumentReconstructionIntegrityError(
                    "section result disposition must match rewrite plan"
                )

            if result.source_text != section.source_text:
                raise DocumentReconstructionIntegrityError(
                    "section result source text must match its exact source section"
                )

            if (
                result.disposition is SectionRewriteDisposition.PRESERVE
                and result.rewritten_text != result.source_text
            ):
                raise DocumentReconstructionIntegrityError(
                    "preserved section must remain byte-for-byte source-identical"
                )
