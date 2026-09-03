from __future__ import annotations

from collections.abc import Callable
from contextlib import nullcontext
from time import perf_counter

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.claim_lock_audit import (
    ClaimLockValidationAuditSnapshot,
)
from app.v2.domain.enterprise_claim_lock_runtime import (
    EnterpriseClaimLockRuntimeContext,
)
from app.v2.domain.enterprise_provider_routing_operation import (
    EnterpriseProviderRoutingOperationKind,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
    VoiceRewriteAnalysisSnapshot,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
    ClaimLockPreparationService,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
    ClaimLockValidator,
    ClaimLockViolationError,
)
from app.v2.services.enterprise_claim_lock_runtime_service import (
    EnterpriseClaimLockRuntimeService,
)
from app.v2.services.enterprise_provider_routing_operation_coordinator import (
    EnterpriseProviderRoutingOperationCoordinator,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseSingleRewriteQuotaAdmissionService,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.single_rewrite_observability import (
    SingleRewriteObservability,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


class WorkspaceRewriteResult:
    def __init__(
        self,
        *,
        response: RewriteResponse,
        history: RewriteHistoryRecord,
        claim_lock_preparation: ClaimLockPreparationResult,
        claim_lock_validation: ClaimLockValidationResult,
        claim_lock_runtime_context: (
            EnterpriseClaimLockRuntimeContext | None
        ) = None,
    ) -> None:
        self.response = response
        self.history = history
        self.claim_lock_preparation = claim_lock_preparation
        self.claim_lock_validation = claim_lock_validation
        self.claim_lock_runtime_context = (
            claim_lock_runtime_context
        )


class WorkspaceRewriteService:
    def __init__(
        self,
        *,
        history_service: RewriteHistoryService,
        workflow: RewriteWorkflow,
        quota_admission: (EnterpriseSingleRewriteQuotaAdmissionService | None) = None,
        enterprise_claim_lock_runtime_service: (
            EnterpriseClaimLockRuntimeService | None
        ) = None,
        claim_lock_preparation_service: (ClaimLockPreparationService | None) = None,
        claim_lock_validator: (ClaimLockValidator | None) = None,
        routing_operation_coordinator: (
            EnterpriseProviderRoutingOperationCoordinator | None
        ) = None,
        observability: SingleRewriteObservability | None = None,
        authorization_gate: WorkspaceAuthorizationGate,
        duration_clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._history_service = history_service
        self._workflow = workflow
        self._quota_admission = quota_admission
        self._routing_operation_coordinator = (
            routing_operation_coordinator
        )
        self._observability = observability
        self._authorization_gate = authorization_gate
        self._duration_clock = duration_clock

        if (
            enterprise_claim_lock_runtime_service is not None
            and claim_lock_preparation_service is not None
        ):
            raise ValueError(
                "single rewrite must not receive both enterprise "
                "claim lock runtime and direct preparation authority"
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
        self._claim_lock_validator = claim_lock_validator or ClaimLockValidator()

    def execute(
        self,
        *,
        workspace_id: str,
        user_id: str,
        request: RewriteRequest,
        voice_profile_id: str | None = None,
        voice_guidance_version: str | None = None,
        voice_analysis_snapshot: VoiceRewriteAnalysisSnapshot | None = None,
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        claim_lock_enforcement_mode: (
            ClaimLockEnforcementMode | None
        ) = None,
    ) -> WorkspaceRewriteResult:
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
                )
            )
            claim_lock_preparation = (
                claim_lock_runtime_context.request_preparation
            )
            effective_claim_lock = (
                claim_lock_runtime_context.effective_claim_lock
            )
            effective_enforcement_mode = (
                claim_lock_runtime_context.effective_enforcement_mode
            )
        else:
            preparation_service = (
                self._claim_lock_preparation_service
            )

            if preparation_service is None:
                raise RuntimeError(
                    "single rewrite claim lock preparation "
                    "authority is unavailable"
                )

            legacy_enforcement_mode = (
                claim_lock_enforcement_mode
                or ClaimLockEnforcementMode.STRICT
            )

            claim_lock_preparation = preparation_service.prepare(
                text=request.text,
                explicit_terms=explicit_protected_terms,
                enforcement_mode=legacy_enforcement_mode,
            )
            effective_claim_lock = (
                claim_lock_preparation.claim_lock
            )
            effective_enforcement_mode = (
                effective_claim_lock.enforcement_mode
                if effective_claim_lock is not None
                else legacy_enforcement_mode
            )

        if self._quota_admission is not None:
            self._quota_admission.admit(
                workspace_id=workspace_id,
                request=request,
            )

        routing_capabilities = {
            ProviderCapability.REWRITE,
        }

        if effective_claim_lock is not None:
            routing_capabilities.add(
                ProviderCapability.CLAIM_LOCK
            )

        if voice_profile_id is not None:
            routing_capabilities.add(
                ProviderCapability.VOICE_PROFILE
            )

        routing_operation = (
            self._routing_operation_coordinator.use_routing_operation(
                workspace_id=workspace_id,
                user_id=user_id,
                operation_kind=(
                    EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
                ),
                required_capabilities=frozenset(
                    routing_capabilities
                ),
            )
            if self._routing_operation_coordinator is not None
            else nullcontext(None)
        )

        with routing_operation as routing_scope:
            response = self._workflow.execute(request)

            claim_lock_validation = self._claim_lock_validator.validate(
                claim_lock=effective_claim_lock,
                rewritten_text=(response.rewritten_text),
            )

            if (
                response.verification.decision is not ReleaseDecision.FAIL
                and effective_enforcement_mode
                is ClaimLockEnforcementMode.STRICT
                and claim_lock_validation.decision is ClaimLockValidationDecision.VIOLATION
            ):
                raise ClaimLockViolationError(claim_lock_validation)

            claim_lock_validation_audit = (
                ClaimLockValidationAuditSnapshot.model_validate(
                    claim_lock_validation.model_dump(mode="json")
                )
                if effective_claim_lock is not None
                else None
            )

            history = self._history_service.record_rewrite(
                workspace_id=workspace_id,
                user_id=user_id,
                request=request,
                response=response,
                voice_profile_id=voice_profile_id,
                voice_guidance_version=voice_guidance_version,
                voice_analysis_snapshot=voice_analysis_snapshot,
                claim_lock_snapshot=effective_claim_lock,
                claim_lock_validation=(claim_lock_validation_audit),
                claim_lock_enforcement_mode=(
                    effective_enforcement_mode
                    if effective_claim_lock is not None
                    else None
                ),
                claim_lock_workspace_policy=(
                    claim_lock_runtime_context
                    .workspace_policy_evidence
                    if claim_lock_runtime_context is not None
                    else None
                ),
            )


            if routing_scope is not None:
                coordinator = (
                    self._routing_operation_coordinator
                )

                if coordinator is None:
                    raise RuntimeError(
                        "single rewrite routing scope exists "
                        "without coordinator authority"
                    )

                coordinator.complete_success(
                    scope=routing_scope,
                    rewrite_history_id=history.rewrite_id,
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
                response=response,
                history=history,
                claim_lock_validation=(claim_lock_validation),
                duration_ms=duration_ms,
            )

        return WorkspaceRewriteResult(
            response=response,
            history=history,
            claim_lock_preparation=(claim_lock_preparation),
            claim_lock_validation=(claim_lock_validation),
            claim_lock_runtime_context=(
                claim_lock_runtime_context
            ),
        )
