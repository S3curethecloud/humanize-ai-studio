from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from app.domain.models import RewriteRequest
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.enterprise_claim_lock_runtime import (
    EnterpriseClaimLockRuntimeContext,
)
from app.v2.domain.long_document_audit import (
    LongDocumentAuditRecord,
)
from app.v2.domain.long_documents import (
    DocumentReconstruction,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
    ClaimLockPreparationService,
)
from app.v2.services.complex_rewrite_observability import (
    LongDocumentObservability,
)
from app.v2.services.document_reconstructor import (
    DocumentReconstructor,
)
from app.v2.services.document_structure_detector import (
    DocumentStructureDetector,
)
from app.v2.services.enterprise_claim_lock_runtime_service import (
    EnterpriseClaimLockRuntimeService,
)
from app.v2.services.enterprise_long_document_quota_admission_service import (
    EnterpriseLongDocumentQuotaAdmissionService,
)
from app.v2.services.long_document_audit_service import (
    LongDocumentAuditService,
)
from app.v2.services.long_document_control_evaluator import (
    LongDocumentControlEvaluation,
    LongDocumentControlEvaluator,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteOrchestrator,
)
from app.v2.services.section_rewrite_planner import (
    SectionRewritePlanner,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


@dataclass(frozen=True)
class LongDocumentWorkspaceRewriteResult:
    claim_lock_preparation: ClaimLockPreparationResult
    evaluation: LongDocumentControlEvaluation
    reconstruction: DocumentReconstruction
    audit: LongDocumentAuditRecord
    claim_lock_runtime_context: (
        EnterpriseClaimLockRuntimeContext | None
    ) = None


class LongDocumentWorkspaceRewriteService:
    def __init__(
        self,
        *,
        enterprise_claim_lock_runtime_service: (
            EnterpriseClaimLockRuntimeService | None
        ) = None,
        claim_lock_preparation_service: (
            ClaimLockPreparationService | None
        ) = None,
        structure_detector: DocumentStructureDetector,
        long_document_quota_admission: (
            EnterpriseLongDocumentQuotaAdmissionService | None
        ) = None,
        planner: SectionRewritePlanner,
        orchestrator: SectionRewriteOrchestrator,
        control_evaluator: LongDocumentControlEvaluator,
        reconstructor: DocumentReconstructor,
        audit_service: LongDocumentAuditService,
        observability: LongDocumentObservability | None = None,
        authorization_gate: WorkspaceAuthorizationGate,
        duration_clock: Callable[[], float] = perf_counter,
    ) -> None:
        if (
            enterprise_claim_lock_runtime_service is not None
            and claim_lock_preparation_service is not None
        ):
            raise ValueError(
                "long-document rewrite must not receive both "
                "enterprise Claim Lock runtime and direct "
                "preparation authority"
            )

        self._enterprise_claim_lock_runtime_service = (
            enterprise_claim_lock_runtime_service
        )
        self._claim_lock_preparation_service = (
            None
            if enterprise_claim_lock_runtime_service is not None
            else (
                claim_lock_preparation_service
                or ClaimLockPreparationService()
            )
        )
        self._structure_detector = structure_detector
        self._long_document_quota_admission = (
            long_document_quota_admission
        )
        self._planner = planner
        self._orchestrator = orchestrator
        self._control_evaluator = control_evaluator
        self._reconstructor = reconstructor
        self._audit_service = audit_service
        self._observability = observability
        self._authorization_gate = authorization_gate
        self._duration_clock = duration_clock

    def execute(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        claim_lock_enforcement_mode: (
            ClaimLockEnforcementMode | None
        ) = None,
    ) -> LongDocumentWorkspaceRewriteResult:
        started_at = self._duration_clock()

        self._authorization_gate.require(
            workspace_id=workspace_id,
            user_id=user_id,
            permission=EnterprisePermission.REWRITE_EXECUTE,
        )

        claim_lock_runtime_context = None

        if self._enterprise_claim_lock_runtime_service is not None:
            claim_lock_runtime_context = (
                self._enterprise_claim_lock_runtime_service.resolve(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    text=request.text,
                    explicit_protected_terms=(
                        explicit_protected_terms
                    ),
                    claim_lock_enforcement_mode=(
                        claim_lock_enforcement_mode
                    ),
                    source_reference=(
                        "long-document-rewrite-request"
                    ),
                )
            )

            claim_lock_preparation = (
                claim_lock_runtime_context.request_preparation
            )
            effective_claim_lock = (
                claim_lock_runtime_context.effective_claim_lock
            )
        else:
            if self._claim_lock_preparation_service is None:
                raise RuntimeError(
                    "long-document rewrite has no Claim Lock "
                    "preparation authority"
                )

            legacy_enforcement_mode = (
                claim_lock_enforcement_mode
                or ClaimLockEnforcementMode.STRICT
            )

            claim_lock_preparation = (
                self._claim_lock_preparation_service.prepare(
                    text=request.text,
                    explicit_terms=explicit_protected_terms,
                    enforcement_mode=(
                        legacy_enforcement_mode
                    ),
                    source_reference=(
                        "long-document-rewrite-request"
                    ),
                )
            )

            effective_claim_lock = None

        structure = self._structure_detector.detect(
            source_text=request.text,
        )

        plan = self._planner.plan(
            structure=structure,
        )

        if self._long_document_quota_admission is not None:
            self._long_document_quota_admission.admit(
                workspace_id=workspace_id,
                request=request,
                section_count=len(plan.entries),
            )

        execution = self._orchestrator.execute(
            request=request,
            structure=structure,
            plan=plan,
        )

        if claim_lock_runtime_context is None:
            effective_claim_lock = (
                claim_lock_preparation.claim_lock
            )

        evaluation = self._control_evaluator.evaluate(
            execution=execution,
            claim_lock=effective_claim_lock,
        )

        reconstruction = self._reconstructor.reconstruct(
            evaluation=evaluation,
        )

        audit = self._audit_service.record(
            workspace_id=workspace_id,
            user_id=user_id,
            evaluation=evaluation,
            reconstruction=reconstruction,
            claim_lock_runtime_context=(
                claim_lock_runtime_context
            ),
        )

        if self._observability is not None:
            duration_ms = max(
                0.0,
                (self._duration_clock() - started_at) * 1000.0,
            )

            self._observability.record_success(
                workspace_id=workspace_id,
                user_id=user_id,
                request=request,
                evaluation=evaluation,
                reconstruction=reconstruction,
                audit=audit,
                duration_ms=duration_ms,
            )

        return LongDocumentWorkspaceRewriteResult(
            claim_lock_preparation=(claim_lock_preparation),
            evaluation=evaluation,
            reconstruction=reconstruction,
            audit=audit,
            claim_lock_runtime_context=(
                claim_lock_runtime_context
            ),
        )
