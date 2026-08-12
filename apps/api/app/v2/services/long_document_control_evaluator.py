from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.models import (
    ReleaseDecision,
    RewriteResponse,
)
from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ProtectedTerm,
)
from app.v2.domain.long_documents import (
    SectionRewriteDisposition,
    SectionRewriteResult,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockCheckStatus,
    ClaimLockValidationCheck,
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
    ClaimLockValidator,
    ClaimLockViolationError,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteExecution,
)


class LongDocumentControlEvaluationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CrossSectionConsistencyCheck:
    section_id: str
    ordinal: int
    item_id: str
    item_type: Literal[
        "term",
        "value",
    ]
    expected_text: str
    status: ClaimLockCheckStatus


@dataclass(frozen=True)
class CrossSectionConsistencyResult:
    decision: ClaimLockValidationDecision
    checks: tuple[
        CrossSectionConsistencyCheck,
        ...,
    ]

    @property
    def violating_pairs(
        self,
    ) -> tuple[
        tuple[str, str],
        ...,
    ]:
        return tuple(
            (
                check.section_id,
                check.item_id,
            )
            for check in self.checks
            if check.status is ClaimLockCheckStatus.MISSING
        )


class CrossSectionConsistencyViolationError(ValueError):
    def __init__(
        self,
        consistency: CrossSectionConsistencyResult,
    ) -> None:
        self.consistency = consistency

        violations = ", ".join(
            f"{section_id}:{item_id}" for section_id, item_id in (consistency.violating_pairs)
        )

        super().__init__(
            "long-document cross-section consistency "
            "enforcement failed" + (f": {violations}" if violations else "")
        )


@dataclass(frozen=True)
class LongDocumentControlEvaluation:
    execution: SectionRewriteExecution
    claim_lock_validation: ClaimLockValidationResult
    cross_section_consistency: CrossSectionConsistencyResult
    v1_failed_section_ids: tuple[
        str,
        ...,
    ]


class LongDocumentControlEvaluator:
    def __init__(
        self,
        *,
        claim_lock_validator: (ClaimLockValidator | None) = None,
    ) -> None:
        self._claim_lock_validator = claim_lock_validator or ClaimLockValidator()

    def evaluate(
        self,
        *,
        execution: SectionRewriteExecution,
        claim_lock: ClaimLock | None,
    ) -> LongDocumentControlEvaluation:
        self._require_execution_integrity(
            execution=execution,
        )

        v1_failed_section_ids = self._v1_failed_section_ids(
            execution=execution,
        )

        claim_lock_validation = self._validate_document_claim_lock(
            execution=execution,
            claim_lock=claim_lock,
        )

        cross_section_consistency = self._evaluate_cross_section_consistency(
            execution=execution,
            claim_lock=claim_lock,
        )

        evaluation = LongDocumentControlEvaluation(
            execution=execution,
            claim_lock_validation=(claim_lock_validation),
            cross_section_consistency=(cross_section_consistency),
            v1_failed_section_ids=(v1_failed_section_ids),
        )

        if v1_failed_section_ids:
            return evaluation

        if (
            claim_lock is not None
            and claim_lock.enforcement_mode is ClaimLockEnforcementMode.STRICT
        ):
            if claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION:
                raise ClaimLockViolationError(claim_lock_validation)

            if cross_section_consistency.decision is ClaimLockValidationDecision.VIOLATION:
                raise (CrossSectionConsistencyViolationError(cross_section_consistency))

        return evaluation

    def _validate_document_claim_lock(
        self,
        *,
        execution: SectionRewriteExecution,
        claim_lock: ClaimLock | None,
    ) -> ClaimLockValidationResult:
        if claim_lock is None:
            return self._claim_lock_validator.validate(
                claim_lock=None,
                rewritten_text="",
            )

        section_validations = tuple(
            self._claim_lock_validator.validate(
                claim_lock=claim_lock,
                rewritten_text=result.rewritten_text,
            )
            for result in execution.results
        )

        if not section_validations:
            raise LongDocumentControlEvaluationError(
                "long-document execution must contain at least one section result"
            )

        template = section_validations[0]

        checks: list[ClaimLockValidationCheck] = []

        for index, template_check in enumerate(template.checks):
            if template_check.item_type == "claim":
                checks.append(template_check)
                continue

            preserved_check = next(
                (
                    validation.checks[index]
                    for validation in section_validations
                    if (validation.checks[index].status is ClaimLockCheckStatus.PRESERVED)
                ),
                None,
            )

            checks.append(preserved_check or template_check)

        decision = (
            ClaimLockValidationDecision.VIOLATION
            if any(check.status is ClaimLockCheckStatus.MISSING for check in checks)
            else ClaimLockValidationDecision.PASS
        )

        return ClaimLockValidationResult(
            lock_id=claim_lock.lock_id,
            enforcement_mode=(claim_lock.enforcement_mode),
            decision=decision,
            checks=tuple(checks),
        )

    def _evaluate_cross_section_consistency(
        self,
        *,
        execution: SectionRewriteExecution,
        claim_lock: ClaimLock | None,
    ) -> CrossSectionConsistencyResult:
        if claim_lock is None:
            return CrossSectionConsistencyResult(
                decision=(ClaimLockValidationDecision.PASS),
                checks=(),
            )

        checks: list[CrossSectionConsistencyCheck] = []

        for result in execution.results:
            for term in claim_lock.terms:
                if not self._term_present(
                    term=term,
                    text=result.source_text,
                ):
                    continue

                preserved = self._term_present(
                    term=term,
                    text=result.rewritten_text,
                )

                checks.append(
                    CrossSectionConsistencyCheck(
                        section_id=(result.section_id),
                        ordinal=result.ordinal,
                        item_id=term.term_id,
                        item_type="term",
                        expected_text=term.text,
                        status=(
                            ClaimLockCheckStatus.PRESERVED
                            if preserved
                            else ClaimLockCheckStatus.MISSING
                        ),
                    )
                )

            for value in claim_lock.values:
                if value.value not in result.source_text:
                    continue

                preserved = value.value in result.rewritten_text

                checks.append(
                    CrossSectionConsistencyCheck(
                        section_id=(result.section_id),
                        ordinal=result.ordinal,
                        item_id=value.value_id,
                        item_type="value",
                        expected_text=value.value,
                        status=(
                            ClaimLockCheckStatus.PRESERVED
                            if preserved
                            else ClaimLockCheckStatus.MISSING
                        ),
                    )
                )

        decision = (
            ClaimLockValidationDecision.VIOLATION
            if any(check.status is ClaimLockCheckStatus.MISSING for check in checks)
            else ClaimLockValidationDecision.PASS
        )

        return CrossSectionConsistencyResult(
            decision=decision,
            checks=tuple(checks),
        )

    def _require_execution_integrity(
        self,
        *,
        execution: SectionRewriteExecution,
    ) -> None:
        structure = execution.structure
        plan = execution.plan
        results = execution.results

        if plan.structure_id != structure.structure_id:
            raise LongDocumentControlEvaluationError(
                "section rewrite plan structure ID must match document structure"
            )

        if len(results) != len(structure.sections):
            raise LongDocumentControlEvaluationError(
                "section execution must contain exactly one result for every document section"
            )

        if len(plan.entries) != len(structure.sections):
            raise LongDocumentControlEvaluationError(
                "section rewrite plan must contain exactly one entry for every document section"
            )

        rewrite_results: list[SectionRewriteResult] = []

        for section, entry, result in zip(
            structure.sections,
            plan.entries,
            results,
            strict=True,
        ):
            if result.section_id != (section.section_id):
                raise (
                    LongDocumentControlEvaluationError(
                        "section result IDs must match document structure order"
                    )
                )

            if result.ordinal != (section.ordinal):
                raise (
                    LongDocumentControlEvaluationError(
                        "section result ordinals must match document structure order"
                    )
                )

            if result.source_text != (section.source_text):
                raise (
                    LongDocumentControlEvaluationError(
                        "section result source text must match document structure"
                    )
                )

            if result.section_id != (entry.section_id):
                raise (
                    LongDocumentControlEvaluationError(
                        "section result IDs must match rewrite plan entries"
                    )
                )

            if result.ordinal != entry.ordinal:
                raise (
                    LongDocumentControlEvaluationError(
                        "section result ordinals must match rewrite plan entries"
                    )
                )

            if result.disposition is not (entry.disposition):
                raise (
                    LongDocumentControlEvaluationError(
                        "section result disposition must match rewrite plan"
                    )
                )

            if (
                result.disposition is SectionRewriteDisposition.PRESERVE
                and result.rewritten_text != result.source_text
            ):
                raise (
                    LongDocumentControlEvaluationError(
                        "preserved section result must remain source-identical"
                    )
                )

            if result.disposition is SectionRewriteDisposition.REWRITE:
                rewrite_results.append(result)

        if len(execution.rewrite_responses) != len(rewrite_results):
            raise LongDocumentControlEvaluationError(
                "rewrite response count must match rewritten section count"
            )

        for result, response in zip(
            rewrite_results,
            execution.rewrite_responses,
            strict=True,
        ):
            self._require_response_match(
                result=result,
                response=response,
            )

    def _v1_failed_section_ids(
        self,
        *,
        execution: SectionRewriteExecution,
    ) -> tuple[
        str,
        ...,
    ]:
        rewrite_results = tuple(
            result
            for result in execution.results
            if (result.disposition is SectionRewriteDisposition.REWRITE)
        )

        return tuple(
            result.section_id
            for result, response in zip(
                rewrite_results,
                execution.rewrite_responses,
                strict=True,
            )
            if (response.verification.decision is ReleaseDecision.FAIL)
        )

    @staticmethod
    def _require_response_match(
        *,
        result: SectionRewriteResult,
        response: RewriteResponse,
    ) -> None:
        if response.source_text != (result.source_text):
            raise LongDocumentControlEvaluationError(
                "rewrite response source text must match section result source text"
            )

        if response.rewritten_text != (result.rewritten_text):
            raise LongDocumentControlEvaluationError(
                "rewrite response output must match section result rewritten text"
            )

    @staticmethod
    def _term_present(
        *,
        term: ProtectedTerm,
        text: str,
    ) -> bool:
        if term.case_sensitive:
            return term.text in text

        return term.text.casefold() in text.casefold()
