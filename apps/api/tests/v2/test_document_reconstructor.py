from __future__ import annotations

import pytest

from app.v2.domain.long_documents import (
    DocumentReconstruction,
    SectionRewriteDisposition,
    SectionRewriteResult,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
)
from app.v2.services.document_reconstructor import (
    DocumentReconstructionIntegrityError,
    DocumentReconstructor,
)
from app.v2.services.document_structure_detector import (
    DocumentStructureDetector,
)
from app.v2.services.long_document_control_evaluator import (
    CrossSectionConsistencyResult,
    LongDocumentControlEvaluation,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteExecution,
)
from app.v2.services.section_rewrite_planner import (
    SectionRewritePlanner,
)

SOURCE = "# Overview\r\nAlpha remains unchanged.\r\n\r\n## Summary\r\nBeta remains unchanged.\r\n"


def _pass_claim_lock_validation() -> ClaimLockValidationResult:
    return ClaimLockValidationResult(
        decision=ClaimLockValidationDecision.PASS,
    )


def _pass_cross_section_consistency() -> CrossSectionConsistencyResult:
    return CrossSectionConsistencyResult(
        decision=ClaimLockValidationDecision.PASS,
        checks=(),
    )


def _preserve_execution() -> SectionRewriteExecution:
    structure = DocumentStructureDetector().detect(
        source_text=SOURCE,
    )

    generated_plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    preserve_entries = tuple(
        entry.model_copy(
            update={
                "disposition": (SectionRewriteDisposition.PRESERVE),
                "rationale": ("Preserved for reconstruction test."),
            }
        )
        for entry in generated_plan.entries
    )

    plan = generated_plan.model_copy(
        update={
            "entries": preserve_entries,
        }
    )

    results = tuple(
        SectionRewriteResult(
            section_id=section.section_id,
            ordinal=section.ordinal,
            disposition=(SectionRewriteDisposition.PRESERVE),
            source_text=section.source_text,
            rewritten_text=section.source_text,
        )
        for section in structure.sections
    )

    return SectionRewriteExecution(
        structure=structure,
        plan=plan,
        results=results,
        rewrite_responses=(),
    )


def _evaluation(
    *,
    execution: SectionRewriteExecution | None = None,
    v1_failed_section_ids: tuple[
        str,
        ...,
    ] = (),
) -> LongDocumentControlEvaluation:
    resolved_execution = execution or _preserve_execution()

    return LongDocumentControlEvaluation(
        execution=resolved_execution,
        claim_lock_validation=(_pass_claim_lock_validation()),
        cross_section_consistency=(_pass_cross_section_consistency()),
        v1_failed_section_ids=(v1_failed_section_ids),
    )


def _mixed_execution() -> SectionRewriteExecution:
    execution = _preserve_execution()

    second_entry = execution.plan.entries[1].model_copy(
        update={
            "disposition": (SectionRewriteDisposition.REWRITE),
            "rationale": ("Rewrite second section."),
        }
    )

    plan = execution.plan.model_copy(
        update={
            "entries": (
                execution.plan.entries[0],
                second_entry,
            ),
        }
    )

    second_result = SectionRewriteResult(
        section_id=(execution.structure.sections[1].section_id),
        ordinal=2,
        disposition=(SectionRewriteDisposition.REWRITE),
        source_text=(execution.structure.sections[1].source_text),
        rewritten_text=("## Summary\r\nBeta was rewritten safely.\r\n"),
    )

    return SectionRewriteExecution(
        structure=execution.structure,
        plan=plan,
        results=(
            execution.results[0],
            second_result,
        ),
        rewrite_responses=(),
    )


def test_reconstruct_returns_canonical_domain_model() -> None:
    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=_evaluation(),
    )

    assert isinstance(
        reconstruction,
        DocumentReconstruction,
    )


def test_reconstruction_preserves_exact_structure() -> None:
    evaluation = _evaluation()

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    assert reconstruction.structure == evaluation.execution.structure


def test_reconstruction_preserves_exact_result_tuple() -> None:
    evaluation = _evaluation()

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    assert reconstruction.section_results == evaluation.execution.results


def test_preserved_document_reconstructs_exact_source_bytes() -> None:
    evaluation = _evaluation()

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    assert reconstruction.reconstructed_text == SOURCE


def test_preserved_crlf_bytes_are_not_normalized() -> None:
    evaluation = _evaluation()

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    assert "\r\n" in (reconstruction.reconstructed_text)

    assert reconstruction.reconstructed_text == evaluation.execution.structure.source_text


def test_mixed_results_concatenate_in_exact_section_order() -> None:
    execution = _mixed_execution()

    reconstruction = DocumentReconstructor().reconstruct(
        evaluation=_evaluation(
            execution=execution,
        ),
    )

    expected = "".join(result.rewritten_text for result in execution.results)

    assert reconstruction.reconstructed_text == expected


def test_reconstruction_is_deterministic() -> None:
    evaluation = _evaluation(
        execution=_mixed_execution(),
    )

    first = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    second = DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    assert first == second


def test_missing_section_result_fails_closed() -> None:
    execution = _preserve_execution()

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=(execution.results[0],),
        rewrite_responses=(),
    )

    with pytest.raises(
        DocumentReconstructionIntegrityError,
        match="exactly one result",
    ):
        DocumentReconstructor().reconstruct(
            evaluation=_evaluation(
                execution=tampered,
            ),
        )


def test_reordered_section_results_fail_closed() -> None:
    execution = _preserve_execution()

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=(
            execution.results[1],
            execution.results[0],
        ),
        rewrite_responses=(),
    )

    with pytest.raises(
        DocumentReconstructionIntegrityError,
        match="result IDs must match",
    ):
        DocumentReconstructor().reconstruct(
            evaluation=_evaluation(
                execution=tampered,
            ),
        )


def test_tampered_section_id_fails_closed() -> None:
    execution = _preserve_execution()

    bad_first = execution.results[0].model_copy(
        update={
            "section_id": "wrong-section",
        }
    )

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=(
            bad_first,
            execution.results[1],
        ),
        rewrite_responses=(),
    )

    with pytest.raises(
        DocumentReconstructionIntegrityError,
        match="result IDs must match",
    ):
        DocumentReconstructor().reconstruct(
            evaluation=_evaluation(
                execution=tampered,
            ),
        )


def test_tampered_ordinal_fails_closed() -> None:
    execution = _preserve_execution()

    bad_first = execution.results[0].model_copy(
        update={
            "ordinal": 2,
        }
    )

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=(
            bad_first,
            execution.results[1],
        ),
        rewrite_responses=(),
    )

    with pytest.raises(
        DocumentReconstructionIntegrityError,
        match="result ordinals must match",
    ):
        DocumentReconstructor().reconstruct(
            evaluation=_evaluation(
                execution=tampered,
            ),
        )


def test_tampered_source_text_fails_closed() -> None:
    execution = _preserve_execution()

    bad_first = execution.results[0].model_copy(
        update={
            "source_text": ("Unexpected source text."),
            "rewritten_text": ("Unexpected source text."),
        }
    )

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=(
            bad_first,
            execution.results[1],
        ),
        rewrite_responses=(),
    )

    with pytest.raises(
        DocumentReconstructionIntegrityError,
        match="exact source section",
    ):
        DocumentReconstructor().reconstruct(
            evaluation=_evaluation(
                execution=tampered,
            ),
        )


def test_plan_result_disposition_mismatch_fails_closed() -> None:
    execution = _preserve_execution()

    rewritten_first = execution.results[0].model_copy(
        update={
            "disposition": (SectionRewriteDisposition.REWRITE),
            "rewritten_text": ("# Overview\r\nAlpha was rewritten.\r\n\r\n"),
        }
    )

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=(
            rewritten_first,
            execution.results[1],
        ),
        rewrite_responses=(),
    )

    with pytest.raises(
        DocumentReconstructionIntegrityError,
        match="disposition must match",
    ):
        DocumentReconstructor().reconstruct(
            evaluation=_evaluation(
                execution=tampered,
            ),
        )


def test_tampered_preserve_output_fails_closed() -> None:
    execution = _preserve_execution()

    bad_first = execution.results[0].model_copy(
        update={
            "rewritten_text": ("# Overview\r\nAlpha was changed.\r\n\r\n"),
        }
    )

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=(
            bad_first,
            execution.results[1],
        ),
        rewrite_responses=(),
    )

    with pytest.raises(
        DocumentReconstructionIntegrityError,
        match="byte-for-byte source-identical",
    ):
        DocumentReconstructor().reconstruct(
            evaluation=_evaluation(
                execution=tampered,
            ),
        )


def test_authoritative_v1_failure_blocks_reconstruction() -> None:
    execution = _preserve_execution()

    with pytest.raises(
        DocumentReconstructionIntegrityError,
        match="authoritative V1 section failures",
    ):
        DocumentReconstructor().reconstruct(
            evaluation=_evaluation(
                execution=execution,
                v1_failed_section_ids=(execution.results[0].section_id,),
            ),
        )


def test_reconstruction_does_not_mutate_evaluation() -> None:
    evaluation = _evaluation(
        execution=_mixed_execution(),
    )

    structure_before = evaluation.execution.structure.model_dump(
        mode="json",
    )

    plan_before = evaluation.execution.plan.model_dump(
        mode="json",
    )

    results_before = tuple(
        result.model_dump(
            mode="json",
        )
        for result in (evaluation.execution.results)
    )

    DocumentReconstructor().reconstruct(
        evaluation=evaluation,
    )

    assert (
        evaluation.execution.structure.model_dump(
            mode="json",
        )
        == structure_before
    )

    assert (
        evaluation.execution.plan.model_dump(
            mode="json",
        )
        == plan_before
    )

    assert (
        tuple(
            result.model_dump(
                mode="json",
            )
            for result in (evaluation.execution.results)
        )
        == results_before
    )
