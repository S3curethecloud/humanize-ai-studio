from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.domain.models import (
    DocumentType,
    RewriteIntensity,
    RewriteRequest,
)
from app.v2.api import routes as v2_routes
from app.v2.api.models import WorkspaceRewriteRequest
from app.v2.domain.candidate_generation import CandidateGenerationPlan
from app.v2.domain.claim_lock import ClaimLockEnforcementMode
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
)
from app.v2.services.candidate_control_enforcement import (
    ControlledCandidateRewriteOrchestrator,
)
from app.v2.services.candidate_rewrite_orchestrator import (
    CandidateGenerationError,
    CandidateRewriteOrchestrator,
    RewriteWorkflowExecutor,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
    ClaimLockPreparationService,
)
from app.v2.services.complex_rewrite_observability import (
    MultiCandidateObservability,
)
from app.v2.services.enterprise_multi_candidate_quota_admission_service import (
    EnterpriseMultiCandidateQuotaAdmissionService,
)
from app.v2.services.enterprise_quota_enforcement_service import (
    EnterpriseQuotaEnforcementResult,
    EnterpriseQuotaEnforcementService,
)
from app.v2.services.enterprise_quota_runtime_context_service import (
    EnterpriseQuotaRuntimeContext,
    EnterpriseQuotaRuntimeContextResolutionError,
    EnterpriseQuotaRuntimeContextService,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseQuotaAdmissionDeniedError,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateWorkspaceRewriteService,
)
from app.v2.services.rewrite_history_service import RewriteHistoryService
from app.v2.services.voice_aware_provider import VoiceAwareRewriteProvider
from app.v2.services.voice_rewrite_guidance import (
    VoiceRewriteGuidanceService,
)
from app.v2.services.workspace_service import WorkspaceService

OCCURRED_AT = datetime(
    2026,
    8,
    14,
    6,
    30,
    tzinfo=UTC,
)

WINDOW = EnterpriseQuotaWindow(
    window_start=OCCURRED_AT - timedelta(hours=1),
    window_end=OCCURRED_AT + timedelta(hours=1),
)

CONTEXT = EnterpriseQuotaRuntimeContext(
    workspace_id="workspace_test",
    operation=EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
    occurred_at=OCCURRED_AT,
    window=WINDOW,
    accounting_group_id="quota_group_multi_test",
)


def _request(
    text: str = "Original multi-candidate text.",
) -> RewriteRequest:
    return RewriteRequest(
        text=text,
        document_type=DocumentType.GENERAL,
        audience="general audience",
        tone="natural",
        intensity=RewriteIntensity.NATURAL_REWRITE,
        preserve_numbers=True,
        preserve_dates=True,
    )


def _enforcement_result(
    *,
    consumed: bool,
) -> EnterpriseQuotaEnforcementResult:
    return EnterpriseQuotaEnforcementResult(
        consumed=consumed,
        workspace_id=CONTEXT.workspace_id,
        operation=CONTEXT.operation,
        accounting_group_id=CONTEXT.accounting_group_id,
        window=CONTEXT.window,
        decisions=(),
    )


def _admission_service(
    *,
    consumed: bool = True,
) -> tuple[
    EnterpriseMultiCandidateQuotaAdmissionService,
    MagicMock,
    MagicMock,
]:
    runtime_context = MagicMock(
        spec=EnterpriseQuotaRuntimeContextService,
    )
    runtime_context.resolve.return_value = CONTEXT

    enforcement = MagicMock(
        spec=EnterpriseQuotaEnforcementService,
    )
    enforcement.enforce.return_value = _enforcement_result(
        consumed=consumed,
    )

    service = EnterpriseMultiCandidateQuotaAdmissionService(
        runtime_context=runtime_context,
        enforcement=enforcement,
    )

    return service, runtime_context, enforcement


def _multi_service(
    *,
    quota_admission: (
        EnterpriseMultiCandidateQuotaAdmissionService | MagicMock | None
    ),
    workspace_service: MagicMock | None = None,
    history_service: MagicMock | None = None,
    workflow: MagicMock | None = None,
    observability: MagicMock | None = None,
    claim_lock_preparation_service: MagicMock | None = None,
    voice_guidance_service: MagicMock | None = None,
    voice_provider: MagicMock | None = None,
) -> tuple[
    MultiCandidateWorkspaceRewriteService,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    workspace = workspace_service or MagicMock(
        spec=WorkspaceService,
    )
    history = history_service or MagicMock(
        spec=RewriteHistoryService,
    )
    resolved_workflow = workflow or MagicMock(
        spec=RewriteWorkflowExecutor,
    )

    service = MultiCandidateWorkspaceRewriteService(
        workspace_service=workspace,
        history_service=history,
        workflow=resolved_workflow,
        multi_candidate_quota_admission=quota_admission,
        observability=observability,
        claim_lock_preparation_service=(
            claim_lock_preparation_service
        ),
        voice_guidance_service=voice_guidance_service,
        voice_provider=voice_provider,
    )

    return service, workspace, history, resolved_workflow


def test_multi_candidate_operation_is_sent_to_runtime_context() -> None:
    service, runtime_context, _enforcement = _admission_service()

    service.admit(
        workspace_id="workspace_test",
        request=_request(),
        candidate_count=3,
    )

    runtime_context.resolve.assert_called_once_with(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
    )


def test_multi_candidate_exact_quantities_are_sent_to_enforcement() -> None:
    service, _runtime_context, enforcement = _admission_service()
    request = _request("123456789")

    service.admit(
        workspace_id="workspace_test",
        request=request,
        candidate_count=3,
    )

    call = enforcement.enforce.call_args

    assert call.kwargs["requested_quantities"] == {
        EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
        EnterpriseQuotaDimension.INPUT_CHARACTERS: len(request.text),
        EnterpriseQuotaDimension.CANDIDATES_GENERATED: 3,
    }


def test_multi_candidate_context_is_forwarded_unchanged() -> None:
    service, _runtime_context, enforcement = _admission_service()
    request = _request()

    service.admit(
        workspace_id=CONTEXT.workspace_id,
        request=request,
        candidate_count=2,
    )

    enforcement.enforce.assert_called_once_with(
        workspace_id=CONTEXT.workspace_id,
        operation=EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
        window=CONTEXT.window,
        accounting_group_id=CONTEXT.accounting_group_id,
        requested_quantities={
            EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
            EnterpriseQuotaDimension.INPUT_CHARACTERS: len(
                request.text
            ),
            EnterpriseQuotaDimension.CANDIDATES_GENERATED: 2,
        },
        occurred_at=CONTEXT.occurred_at,
    )


def test_denied_enforcement_raises_existing_admission_error() -> None:
    service, _runtime_context, _enforcement = _admission_service(
        consumed=False,
    )

    with pytest.raises(
        EnterpriseQuotaAdmissionDeniedError,
        match="enterprise quota admission denied",
    ):
        service.admit(
            workspace_id="workspace_test",
            request=_request(),
            candidate_count=3,
        )


def test_invalid_candidate_count_fails_before_quota_admission() -> None:
    admission = MagicMock(
        spec=EnterpriseMultiCandidateQuotaAdmissionService,
    )

    service, _workspace, _history, workflow = _multi_service(
        quota_admission=admission,
    )

    with pytest.raises(
        ValueError,
        match="candidate_count must be between 2 and 5",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=1,
        )

    admission.admit.assert_not_called()
    workflow.execute.assert_not_called()


def test_non_member_fails_before_quota_admission() -> None:
    admission = MagicMock(
        spec=EnterpriseMultiCandidateQuotaAdmissionService,
    )

    workspace = MagicMock(
        spec=WorkspaceService,
    )
    workspace.require_membership.side_effect = PermissionError(
        "not a member"
    )

    service, _workspace, _history, workflow = _multi_service(
        quota_admission=admission,
        workspace_service=workspace,
    )

    with pytest.raises(
        PermissionError,
        match="not a member",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=2,
        )

    admission.admit.assert_not_called()
    workflow.execute.assert_not_called()


def test_claim_lock_preparation_occurs_before_quota_admission() -> None:
    preparation = MagicMock(
        spec=ClaimLockPreparationService,
    )
    preparation_result = MagicMock(
        spec=ClaimLockPreparationResult,
    )
    preparation.prepare.return_value = preparation_result

    admission = MagicMock(
        spec=EnterpriseMultiCandidateQuotaAdmissionService,
    )

    def deny_after_preparation(**_kwargs: object) -> None:
        preparation.prepare.assert_called_once()
        raise EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )

    admission.admit.side_effect = deny_after_preparation

    service, _workspace, history, workflow = _multi_service(
        quota_admission=admission,
        claim_lock_preparation_service=preparation,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=2,
        )

    preparation.prepare.assert_called_once()
    workflow.execute.assert_not_called()
    history.record_rewrite.assert_not_called()


def test_allowed_admission_proceeds_to_first_candidate_workflow() -> None:
    admission = MagicMock(
        spec=EnterpriseMultiCandidateQuotaAdmissionService,
    )
    admission.admit.return_value = _enforcement_result(
        consumed=True,
    )

    workflow = MagicMock(
        spec=RewriteWorkflowExecutor,
    )
    workflow.execute.side_effect = CandidateGenerationError(
        "candidate workflow reached"
    )

    service, _workspace, _history, _workflow = _multi_service(
        quota_admission=admission,
        workflow=workflow,
    )

    with pytest.raises(
        CandidateGenerationError,
        match="candidate workflow reached",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=2,
        )

    admission.admit.assert_called_once()
    workflow.execute.assert_called_once()


def test_validated_plan_candidate_count_is_quota_authority() -> None:
    admission = MagicMock(
        spec=EnterpriseMultiCandidateQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    service, _workspace, _history, workflow = _multi_service(
        quota_admission=admission,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=4,
        )

    admission.admit.assert_called_once()

    assert admission.admit.call_args.kwargs["candidate_count"] == 4

    workflow.execute.assert_not_called()


def test_denied_admission_executes_zero_candidate_workflows() -> None:
    admission = MagicMock(
        spec=EnterpriseMultiCandidateQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    service, _workspace, _history, workflow = _multi_service(
        quota_admission=admission,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=3,
        )

    workflow.execute.assert_not_called()


def test_denied_admission_writes_zero_history_and_observability() -> None:
    admission = MagicMock(
        spec=EnterpriseMultiCandidateQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    history = MagicMock(
        spec=RewriteHistoryService,
    )
    observability = MagicMock(
        spec=MultiCandidateObservability,
    )

    service, _workspace, _history, workflow = _multi_service(
        quota_admission=admission,
        history_service=history,
        observability=observability,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=3,
        )

    workflow.execute.assert_not_called()
    history.record_rewrite.assert_not_called()
    observability.record_success.assert_not_called()


def test_runtime_context_failure_prevents_candidate_execution() -> None:
    runtime_context = MagicMock(
        spec=EnterpriseQuotaRuntimeContextService,
    )
    runtime_context.resolve.side_effect = (
        EnterpriseQuotaRuntimeContextResolutionError(
            "no active limit"
        )
    )

    enforcement = MagicMock(
        spec=EnterpriseQuotaEnforcementService,
    )

    admission = EnterpriseMultiCandidateQuotaAdmissionService(
        runtime_context=runtime_context,
        enforcement=enforcement,
    )

    history = MagicMock(
        spec=RewriteHistoryService,
    )
    workflow = MagicMock(
        spec=RewriteWorkflowExecutor,
    )

    service, _workspace, _history, _workflow = _multi_service(
        quota_admission=admission,
        history_service=history,
        workflow=workflow,
    )

    with pytest.raises(
        EnterpriseQuotaRuntimeContextResolutionError,
        match="no active limit",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=2,
        )

    enforcement.enforce.assert_not_called()
    workflow.execute.assert_not_called()
    history.record_rewrite.assert_not_called()


def test_voice_guidance_resolves_before_same_quota_admission_hook() -> None:
    guidance_service = MagicMock(
        spec=VoiceRewriteGuidanceService,
    )

    guidance = MagicMock()
    guidance.profile_id = "voice_profile_test"
    guidance.guidance_version = "guidance_v1"
    guidance.analysis_snapshot = None

    guidance_service.build_guidance.return_value = guidance

    voice_provider = MagicMock(
        spec=VoiceAwareRewriteProvider,
    )
    voice_provider.use_guidance.return_value = nullcontext()

    admission = MagicMock(
        spec=EnterpriseMultiCandidateQuotaAdmissionService,
    )

    def deny_after_guidance(**_kwargs: object) -> None:
        guidance_service.build_guidance.assert_called_once()
        raise EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )

    admission.admit.side_effect = deny_after_guidance

    service, _workspace, _history, workflow = _multi_service(
        quota_admission=admission,
        voice_guidance_service=guidance_service,
        voice_provider=voice_provider,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
            candidate_count=2,
            voice_profile_id="voice_profile_test",
        )

    guidance_service.build_guidance.assert_called_once()
    voice_provider.use_guidance.assert_called_once_with(guidance)
    admission.admit.assert_called_once()
    workflow.execute.assert_not_called()


def test_controlled_orchestrator_hook_is_before_candidate_generation() -> None:
    preparation = MagicMock(
        spec=ClaimLockPreparationService,
    )
    preparation_result = MagicMock(
        spec=ClaimLockPreparationResult,
    )
    preparation.prepare.return_value = preparation_result

    candidate_orchestrator = MagicMock(
        spec=CandidateRewriteOrchestrator,
    )

    controlled = ControlledCandidateRewriteOrchestrator(
        candidate_orchestrator=candidate_orchestrator,
        claim_lock_preparation_service=preparation,
    )

    plan = MagicMock(
        spec=CandidateGenerationPlan,
    )

    def stop_before_generation(
        received_preparation: ClaimLockPreparationResult,
    ) -> None:
        assert received_preparation is preparation_result
        preparation.prepare.assert_called_once()
        candidate_orchestrator.execute.assert_not_called()

        raise EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        controlled.execute(
            request=_request(),
            plan=plan,
            claim_lock_enforcement_mode=(
                ClaimLockEnforcementMode.STRICT
            ),
            pre_generation_hook=stop_before_generation,
        )

    candidate_orchestrator.execute.assert_not_called()


def test_multi_candidate_route_reuses_existing_quota_429_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    multi_candidate = MagicMock()
    multi_candidate.execute.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        SimpleNamespace(
            multi_candidate=multi_candidate,
        ),
    )

    request = WorkspaceRewriteRequest.model_validate(
        {
            "user_id": "user_test",
            "candidate_count": 2,
            "rewrite": {
                "text": "Original text.",
                "document_type": "general",
                "audience": "general audience",
                "tone": "natural",
                "intensity": "natural_rewrite",
                "preserve_numbers": True,
                "preserve_dates": True,
            },
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        v2_routes.create_workspace_rewrite(
            workspace_id="workspace_test",
            request=request,
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == (
        "enterprise quota admission denied"
    )
