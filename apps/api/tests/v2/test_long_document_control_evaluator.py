from __future__ import annotations

import pytest

from app.domain.models import (
    EditorialQualityDecision,
    EditorialQualityResult,
    ProviderExecutionEvidence,
    ProviderUsageEvidence,
    ReleaseDecision,
    RewriteNecessityEvidence,
    RewriteResponse,
    VerificationResult,
)
from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedClaim,
    ProtectedTerm,
    ProtectedValue,
    ProtectedValueKind,
)
from app.v2.domain.long_documents import (
    SectionRewriteDisposition,
    SectionRewriteResult,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockCheckStatus,
    ClaimLockValidationDecision,
    ClaimLockViolationError,
)
from app.v2.services.document_structure_detector import (
    DocumentStructureDetector,
)
from app.v2.services.long_document_control_evaluator import (
    CrossSectionConsistencyViolationError,
    LongDocumentControlEvaluationError,
    LongDocumentControlEvaluator,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteExecution,
)
from app.v2.services.section_rewrite_planner import (
    SectionRewritePlanner,
)

SOURCE = (
    "# Overview\n"
    "SecureTheCloud revenue was 42% in 2025.\n"
    "\n"
    "## Summary\n"
    "SecureTheCloud remains the approved platform.\n"
)


def _provenance() -> ClaimLockProvenance:
    return ClaimLockProvenance(
        origin=ClaimLockOrigin.REQUEST,
        source_reference="rewrite-request",
    )


def _term(
    *,
    term_id: str = "term_secure",
    text: str = "SecureTheCloud",
    case_sensitive: bool = True,
) -> ProtectedTerm:
    return ProtectedTerm(
        term_id=term_id,
        text=text,
        case_sensitive=case_sensitive,
        provenance=_provenance(),
    )


def _value(
    *,
    value_id: str = "value_42",
    value: str = "42%",
) -> ProtectedValue:
    return ProtectedValue(
        value_id=value_id,
        value=value,
        kind=ProtectedValueKind.PERCENTAGE,
        provenance=_provenance(),
    )


def _claim(
    *,
    claim_id: str = "claim_revenue",
) -> ProtectedClaim:
    return ProtectedClaim(
        claim_id=claim_id,
        text=("SecureTheCloud revenue was 42% in 2025."),
        provenance=_provenance(),
    )


def _lock(
    *,
    mode: ClaimLockEnforcementMode = (ClaimLockEnforcementMode.STRICT),
    claims: tuple[
        ProtectedClaim,
        ...,
    ] = (),
    terms: tuple[
        ProtectedTerm,
        ...,
    ] = (),
    values: tuple[
        ProtectedValue,
        ...,
    ] = (),
) -> ClaimLock:
    return ClaimLock(
        lock_id="lock_long_document",
        enforcement_mode=mode,
        claims=claims,
        terms=terms,
        values=values,
    )


def _response(
    *,
    source_text: str,
    rewritten_text: str,
    trace_id: str,
    decision: ReleaseDecision = (ReleaseDecision.PASS),
) -> RewriteResponse:
    return RewriteResponse(
        trace_id=trace_id,
        workflow_states=[
            "received",
            "ready_for_review",
        ],
        source_text=source_text,
        rewritten_text=rewritten_text,
        provider_name="test-provider",
        model_name="test-model",
        prompt_version="test-v1",
        provider_execution=(
            ProviderExecutionEvidence(
                latency_ms=0.0,
                primary_provider_name=("test-provider"),
                actual_provider_name=("test-provider"),
                fallback_used=False,
                provider_error_category=None,
                usage=ProviderUsageEvidence(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                ),
            )
        ),
        rewrite_necessity=(
            RewriteNecessityEvidence(
                decision="full_rewrite",
                score=80,
                provider_required=True,
                signals=[],
                rationale=("Long-document control test."),
            )
        ),
        analysis={
            "scores": {
                "generic_language": 0.0,
                "repetition": 0.0,
                "sentence_uniformity": 0.0,
                "transition_overuse": 0.0,
            },
            "flagged_segments": [],
        },
        editorial_quality=(
            EditorialQualityResult(
                decision=(EditorialQualityDecision.PASS),
                naturalness_score=1.0,
                source_flag_count=0,
                remaining_flag_count=0,
                removed_flag_count=0,
                remaining_flagged_segments=[],
                warnings=[],
            )
        ),
        protected_facts=[],
        changes=[],
        verification=VerificationResult(
            decision=decision,
            preserved_facts=[],
            missing_facts=[],
            unexpected_facts=[],
            warnings=[],
        ),
    )


def _execution(
    *,
    outputs: tuple[
        str,
        str,
    ]
    | None = None,
    decisions: tuple[
        ReleaseDecision,
        ReleaseDecision,
    ] = (
        ReleaseDecision.PASS,
        ReleaseDecision.PASS,
    ),
) -> SectionRewriteExecution:
    structure = DocumentStructureDetector().detect(
        source_text=SOURCE,
    )

    plan = SectionRewritePlanner().plan(
        structure=structure,
    )

    resolved_outputs = outputs or (
        ("# Overview\nSecureTheCloud revenue remained 42% in 2025.\n\n"),
        ("## Summary\nSecureTheCloud remains the approved platform.\n"),
    )

    results = tuple(
        SectionRewriteResult(
            section_id=section.section_id,
            ordinal=section.ordinal,
            disposition=(SectionRewriteDisposition.REWRITE),
            source_text=section.source_text,
            rewritten_text=rewritten_text,
        )
        for section, rewritten_text in zip(
            structure.sections,
            resolved_outputs,
            strict=True,
        )
    )

    responses = tuple(
        _response(
            source_text=result.source_text,
            rewritten_text=(result.rewritten_text),
            trace_id=f"trace-{index}",
            decision=decision,
        )
        for index, (
            result,
            decision,
        ) in enumerate(
            zip(
                results,
                decisions,
                strict=True,
            ),
            start=1,
        )
    )

    return SectionRewriteExecution(
        structure=structure,
        plan=plan,
        results=results,
        rewrite_responses=responses,
    )


def test_no_claim_lock_passes() -> None:
    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=_execution(),
        claim_lock=None,
    )

    assert evaluation.claim_lock_validation.decision is ClaimLockValidationDecision.PASS
    assert evaluation.cross_section_consistency.decision is ClaimLockValidationDecision.PASS
    assert evaluation.v1_failed_section_ids == ()


def test_document_wide_term_presence_passes() -> None:
    lock = _lock(
        terms=(
            _term(
                term_id="term_approved",
                text="approved platform",
            ),
        ),
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=_execution(),
        claim_lock=lock,
    )

    assert evaluation.claim_lock_validation.decision is ClaimLockValidationDecision.PASS


def test_document_wide_value_presence_passes() -> None:
    lock = _lock(
        values=(_value(),),
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=_execution(),
        claim_lock=lock,
    )

    assert evaluation.claim_lock_validation.decision is ClaimLockValidationDecision.PASS


def test_semantic_claim_remains_not_evaluated() -> None:
    lock = _lock(
        claims=(_claim(),),
    )

    execution = _execution(
        outputs=(
            ("# Overview\nThe platform reported the same annual result.\n\n"),
            ("## Summary\nThe platform remains approved.\n"),
        )
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=execution,
        claim_lock=lock,
    )

    check = evaluation.claim_lock_validation.checks[0]

    assert check.status is ClaimLockCheckStatus.NOT_EVALUATED
    assert evaluation.claim_lock_validation.decision is ClaimLockValidationDecision.PASS


def test_strict_missing_document_term_fails_closed() -> None:
    lock = _lock(
        terms=(
            _term(
                term_id="term_required",
                text="RequiredTerm",
            ),
        ),
    )

    with pytest.raises(
        ClaimLockViolationError,
        match="strict enforcement failed",
    ):
        LongDocumentControlEvaluator().evaluate(
            execution=_execution(),
            claim_lock=lock,
        )


def test_audit_only_missing_document_term_returns_evidence() -> None:
    lock = _lock(
        mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
        terms=(
            _term(
                term_id="term_required",
                text="RequiredTerm",
            ),
        ),
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=_execution(),
        claim_lock=lock,
    )

    assert evaluation.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION
    assert evaluation.claim_lock_validation.violating_item_ids == ("term_required",)


def test_case_sensitive_term_change_fails() -> None:
    lock = _lock(
        terms=(_term(),),
    )

    execution = _execution(
        outputs=(
            ("# Overview\nsecurethecloud revenue remained 42% in 2025.\n\n"),
            ("## Summary\nsecurethecloud remains the approved platform.\n"),
        )
    )

    with pytest.raises(
        ClaimLockViolationError,
    ):
        LongDocumentControlEvaluator().evaluate(
            execution=execution,
            claim_lock=lock,
        )


def test_case_insensitive_term_change_passes() -> None:
    lock = _lock(
        terms=(
            _term(
                case_sensitive=False,
            ),
        ),
    )

    execution = _execution(
        outputs=(
            ("# Overview\nsecurethecloud revenue remained 42% in 2025.\n\n"),
            ("## Summary\nSECURETHECLOUD remains the approved platform.\n"),
        )
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=execution,
        claim_lock=lock,
    )

    assert evaluation.claim_lock_validation.decision is ClaimLockValidationDecision.PASS
    assert evaluation.cross_section_consistency.decision is ClaimLockValidationDecision.PASS


def test_cross_section_term_loss_is_detected_even_when_document_passes() -> None:
    lock = _lock(
        terms=(_term(),),
    )

    execution = _execution(
        outputs=(
            ("# Overview\nRevenue remained 42% in 2025.\n\n"),
            ("## Summary\nSecureTheCloud remains the approved platform.\n"),
        )
    )

    with pytest.raises(
        CrossSectionConsistencyViolationError,
        match="cross-section consistency",
    ) as exc_info:
        LongDocumentControlEvaluator().evaluate(
            execution=execution,
            claim_lock=lock,
        )

    assert exc_info.value.consistency.decision is ClaimLockValidationDecision.VIOLATION


def test_audit_only_cross_section_term_loss_returns_evidence() -> None:
    lock = _lock(
        mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
        terms=(_term(),),
    )

    execution = _execution(
        outputs=(
            ("# Overview\nRevenue remained 42% in 2025.\n\n"),
            ("## Summary\nSecureTheCloud remains the approved platform.\n"),
        )
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=execution,
        claim_lock=lock,
    )

    assert evaluation.claim_lock_validation.decision is ClaimLockValidationDecision.PASS
    assert evaluation.cross_section_consistency.decision is ClaimLockValidationDecision.VIOLATION

    assert len(evaluation.cross_section_consistency.violating_pairs) == 1


def test_cross_section_value_preservation_passes() -> None:
    lock = _lock(
        values=(_value(),),
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=_execution(),
        claim_lock=lock,
    )

    assert evaluation.cross_section_consistency.decision is ClaimLockValidationDecision.PASS


def test_v1_fail_remains_authoritative_over_strict_claim_lock() -> None:
    lock = _lock(
        terms=(
            _term(
                term_id="term_missing",
                text="MissingTerm",
            ),
        ),
    )

    execution = _execution(
        decisions=(
            ReleaseDecision.FAIL,
            ReleaseDecision.PASS,
        )
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=execution,
        claim_lock=lock,
    )

    assert evaluation.v1_failed_section_ids == (execution.results[0].section_id,)
    assert evaluation.claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION


def test_v1_fail_remains_authoritative_over_cross_section_violation() -> None:
    lock = _lock(
        terms=(_term(),),
    )

    execution = _execution(
        outputs=(
            ("# Overview\nRevenue remained 42% in 2025.\n\n"),
            ("## Summary\nSecureTheCloud remains the approved platform.\n"),
        ),
        decisions=(
            ReleaseDecision.FAIL,
            ReleaseDecision.PASS,
        ),
    )

    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=execution,
        claim_lock=lock,
    )

    assert evaluation.v1_failed_section_ids == (execution.results[0].section_id,)
    assert evaluation.cross_section_consistency.decision is ClaimLockValidationDecision.VIOLATION


def test_tampered_result_section_id_fails_closed() -> None:
    execution = _execution()

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
        rewrite_responses=(execution.rewrite_responses),
    )

    with pytest.raises(
        LongDocumentControlEvaluationError,
        match="result IDs must match",
    ):
        LongDocumentControlEvaluator().evaluate(
            execution=tampered,
            claim_lock=None,
        )


def test_tampered_response_source_fails_closed() -> None:
    execution = _execution()

    bad_response = execution.rewrite_responses[0].model_copy(
        update={
            "source_text": "Wrong source.",
        }
    )

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=execution.results,
        rewrite_responses=(
            bad_response,
            execution.rewrite_responses[1],
        ),
    )

    with pytest.raises(
        LongDocumentControlEvaluationError,
        match="response source text",
    ):
        LongDocumentControlEvaluator().evaluate(
            execution=tampered,
            claim_lock=None,
        )


def test_tampered_response_output_fails_closed() -> None:
    execution = _execution()

    bad_response = execution.rewrite_responses[0].model_copy(
        update={
            "rewritten_text": ("Wrong output."),
        }
    )

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=execution.results,
        rewrite_responses=(
            bad_response,
            execution.rewrite_responses[1],
        ),
    )

    with pytest.raises(
        LongDocumentControlEvaluationError,
        match="response output",
    ):
        LongDocumentControlEvaluator().evaluate(
            execution=tampered,
            claim_lock=None,
        )


def test_rewrite_response_count_mismatch_fails_closed() -> None:
    execution = _execution()

    tampered = SectionRewriteExecution(
        structure=execution.structure,
        plan=execution.plan,
        results=execution.results,
        rewrite_responses=(execution.rewrite_responses[0],),
    )

    with pytest.raises(
        LongDocumentControlEvaluationError,
        match="response count",
    ):
        LongDocumentControlEvaluator().evaluate(
            execution=tampered,
            claim_lock=None,
        )


def test_evaluation_does_not_reconstruct_document() -> None:
    evaluation = LongDocumentControlEvaluator().evaluate(
        execution=_execution(),
        claim_lock=None,
    )

    assert not hasattr(
        evaluation,
        "reconstructed_text",
    )
