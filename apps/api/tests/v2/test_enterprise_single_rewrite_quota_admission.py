from __future__ import annotations

from tests.v2.test_support_authorization_gate import (
    allow_all_workspace_authorization_gate,
    deny_all_workspace_authorization_gate,
)
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from inspect import signature
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
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
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
from app.v2.services.enterprise_claim_lock_runtime_service import (
    EnterpriseClaimLockRuntimeIntegrityError,
    EnterpriseClaimLockRuntimeService,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseQuotaAdmissionDeniedError,
    EnterpriseSingleRewriteQuotaAdmissionService,
)
from app.v2.services.long_document_rewrite_service import (
    LongDocumentWorkspaceRewriteService,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateWorkspaceRewriteService,
)
from app.v2.services.rewrite_history_service import RewriteHistoryService
from app.v2.services.single_rewrite_observability import (
    SingleRewriteObservability,
)
from app.v2.services.voice_aware_provider import VoiceAwareRewriteProvider
from app.v2.services.voice_aware_rewrite_service import (
    VoiceAwareWorkspaceRewriteService,
)
from app.v2.services.voice_rewrite_guidance import (
    VoiceRewriteGuidanceService,
)
from app.v2.services.workspace_rewrite_service import (
    WorkspaceRewriteService,
)
from app.v2.services.workspace_service import WorkspaceService
from app.workflows.rewrite_workflow import RewriteWorkflow

OCCURRED_AT = datetime(
    2026,
    8,
    14,
    6,
    0,
    tzinfo=UTC,
)
WINDOW = EnterpriseQuotaWindow(
    window_start=OCCURRED_AT - timedelta(hours=1),
    window_end=OCCURRED_AT + timedelta(hours=1),
)
CONTEXT = EnterpriseQuotaRuntimeContext(
    workspace_id="workspace_test",
    operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
    occurred_at=OCCURRED_AT,
    window=WINDOW,
    accounting_group_id="quota_group_test",
)


def _request(
    text: str = "Original text.",
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
    EnterpriseSingleRewriteQuotaAdmissionService,
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

    service = EnterpriseSingleRewriteQuotaAdmissionService(
        runtime_context=runtime_context,
        enforcement=enforcement,
    )

    return (
        service,
        runtime_context,
        enforcement,
    )


def _workspace_service(
    *,
    quota_admission: object,
    workflow: MagicMock | None = None,
    history_service: MagicMock | None = None,
    observability: MagicMock | None = None,
    workspace_service: MagicMock | None = None,
    enterprise_claim_lock_runtime_service: (
        EnterpriseClaimLockRuntimeService | None
    ) = None,
    authorization_gate=None,
) -> tuple[
    WorkspaceRewriteService,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    resolved_workspace = workspace_service or MagicMock(
        spec=WorkspaceService,
    )
    resolved_history = history_service or MagicMock(
        spec=RewriteHistoryService,
    )
    resolved_workflow = workflow or MagicMock(
        spec=RewriteWorkflow,
    )

    service = WorkspaceRewriteService(
        history_service=resolved_history,
        workflow=resolved_workflow,
        quota_admission=quota_admission,  # type: ignore[arg-type]
        enterprise_claim_lock_runtime_service=(
            enterprise_claim_lock_runtime_service
        ),
        observability=observability,
        authorization_gate=(
            authorization_gate
            or allow_all_workspace_authorization_gate()
        ),
    )

    return (
        service,
        resolved_workspace,
        resolved_history,
        resolved_workflow,
    )


def test_single_rewrite_operation_is_sent_to_runtime_context() -> None:
    service, runtime_context, _enforcement = _admission_service()

    service.admit(
        workspace_id="workspace_test",
        request=_request(),
    )

    runtime_context.resolve.assert_called_once_with(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
    )


def test_single_rewrite_exact_quantities_are_sent_to_enforcement() -> None:
    service, _runtime_context, enforcement = _admission_service()
    request = _request("123456789")

    service.admit(
        workspace_id="workspace_test",
        request=request,
    )

    call = enforcement.enforce.call_args

    assert call.kwargs["requested_quantities"] == {
        EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
        EnterpriseQuotaDimension.INPUT_CHARACTERS: len(request.text),
    }


def test_runtime_context_fields_are_forwarded_unchanged_to_enforcement() -> None:
    service, _runtime_context, enforcement = _admission_service()

    service.admit(
        workspace_id="workspace_test",
        request=_request(),
    )

    enforcement.enforce.assert_called_once_with(
        workspace_id=CONTEXT.workspace_id,
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        window=CONTEXT.window,
        accounting_group_id=CONTEXT.accounting_group_id,
        requested_quantities={
            EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
            EnterpriseQuotaDimension.INPUT_CHARACTERS: len(
                _request().text
            ),
        },
        occurred_at=CONTEXT.occurred_at,
    )


def test_allowed_admission_proceeds_to_single_rewrite_workflow() -> None:
    admission = MagicMock(
        spec=EnterpriseSingleRewriteQuotaAdmissionService,
    )
    admission.admit.return_value = _enforcement_result(
        consumed=True,
    )

    workflow = MagicMock(spec=RewriteWorkflow)
    workflow.execute.return_value = RewriteWorkflow().execute(
        _request(),
    )

    history = MagicMock(spec=RewriteHistoryService)

    service, _workspace, _history, _workflow = _workspace_service(
        quota_admission=admission,
        workflow=workflow,
        history_service=history,
    )

    service.execute(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
    )

    admission.admit.assert_called_once()
    workflow.execute.assert_called_once_with(_request())


def test_denied_enforcement_raises_dedicated_admission_error() -> None:
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
        )


def test_denied_admission_executes_zero_workflow_calls() -> None:
    admission = MagicMock(
        spec=EnterpriseSingleRewriteQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    service, _workspace, _history, workflow = _workspace_service(
        quota_admission=admission,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    workflow.execute.assert_not_called()


def test_denied_admission_writes_zero_history() -> None:
    admission = MagicMock(
        spec=EnterpriseSingleRewriteQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    history = MagicMock(spec=RewriteHistoryService)

    service, _workspace, _history, _workflow = _workspace_service(
        quota_admission=admission,
        history_service=history,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    history.record_rewrite.assert_not_called()


def test_denied_admission_writes_zero_success_observability() -> None:
    admission = MagicMock(
        spec=EnterpriseSingleRewriteQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    observability = MagicMock(
        spec=SingleRewriteObservability,
    )

    service, _workspace, _history, _workflow = _workspace_service(
        quota_admission=admission,
        observability=observability,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    observability.record_success.assert_not_called()


def test_non_member_fails_before_quota_resolution() -> None:
    admission = MagicMock(
        spec=EnterpriseSingleRewriteQuotaAdmissionService,
    )
    workspace = MagicMock(spec=WorkspaceService)

    service, _workspace, _history, workflow = _workspace_service(
        quota_admission=admission,
        workspace_service=workspace,
            authorization_gate=deny_all_workspace_authorization_gate(),
    )

    with pytest.raises(
        PermissionError,
        match="permission_not_granted",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    admission.admit.assert_not_called()
    workflow.execute.assert_not_called()


def test_runtime_context_resolution_failure_prevents_workflow() -> None:
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

    admission = EnterpriseSingleRewriteQuotaAdmissionService(
        runtime_context=runtime_context,
        enforcement=enforcement,
    )

    service, _workspace, history, workflow = _workspace_service(
        quota_admission=admission,
    )

    with pytest.raises(
        EnterpriseQuotaRuntimeContextResolutionError,
        match="no active limit",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    enforcement.enforce.assert_not_called()
    workflow.execute.assert_not_called()
    history.record_rewrite.assert_not_called()


def test_voice_aware_rewrite_inherits_single_rewrite_admission_hook() -> None:
    admission = MagicMock(
        spec=EnterpriseSingleRewriteQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    rewrite_service, _workspace, _history, workflow = (
        _workspace_service(
            quota_admission=admission,
        )
    )

    guidance_service = MagicMock(
        spec=VoiceRewriteGuidanceService,
    )
    guidance = MagicMock()
    guidance.profile_id = "profile_test"
    guidance.guidance_version = "guidance_test"
    guidance.analysis_snapshot = None
    guidance_service.build_guidance.return_value = guidance

    provider = MagicMock(
        spec=VoiceAwareRewriteProvider,
    )
    provider.use_guidance.return_value = nullcontext()

    voice_service = VoiceAwareWorkspaceRewriteService(
        rewrite_service=rewrite_service,
        guidance_service=guidance_service,
        provider=provider,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        voice_service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            profile_id="profile_test",
            request=_request(),
        )

    admission.admit.assert_called_once()
    workflow.execute.assert_not_called()


def test_single_rewrite_route_maps_actual_quota_denial_to_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rewrite = MagicMock()
    rewrite.execute.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        SimpleNamespace(
            rewrite=rewrite,
        ),
    )

    request = WorkspaceRewriteRequest.model_validate(
        {
            "user_id": "user_test",
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


def test_complex_rewrite_services_do_not_receive_single_rewrite_hook() -> None:
    multi_parameters = signature(
        MultiCandidateWorkspaceRewriteService.__init__
    ).parameters
    long_parameters = signature(
        LongDocumentWorkspaceRewriteService.__init__
    ).parameters

    assert "quota_admission" not in multi_parameters
    assert "quota_admission" not in long_parameters


def test_rewrite_authorization_precedes_claim_lock_runtime_resolution() -> None:
    admission = MagicMock(
        spec=EnterpriseSingleRewriteQuotaAdmissionService,
    )
    runtime = MagicMock(
        spec=EnterpriseClaimLockRuntimeService,
    )

    service, _workspace, _history, workflow = _workspace_service(
        quota_admission=admission,
        enterprise_claim_lock_runtime_service=runtime,
        authorization_gate=deny_all_workspace_authorization_gate(),
    )

    with pytest.raises(
        PermissionError,
        match="permission_not_granted",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    runtime.resolve.assert_not_called()
    admission.admit.assert_not_called()
    workflow.execute.assert_not_called()


def test_claim_lock_runtime_failure_precedes_quota_and_generation() -> None:
    admission = MagicMock(
        spec=EnterpriseSingleRewriteQuotaAdmissionService,
    )
    runtime = MagicMock(
        spec=EnterpriseClaimLockRuntimeService,
    )
    runtime.resolve.side_effect = (
        EnterpriseClaimLockRuntimeIntegrityError(
            "claim_lock_policy_resolution_failed"
        )
    )

    history = MagicMock(
        spec=RewriteHistoryService,
    )
    workflow = MagicMock(
        spec=RewriteWorkflow,
    )

    service, _workspace, _history, _workflow = _workspace_service(
        quota_admission=admission,
        workflow=workflow,
        history_service=history,
        enterprise_claim_lock_runtime_service=runtime,
    )

    request = _request()

    with pytest.raises(
        EnterpriseClaimLockRuntimeIntegrityError,
        match="claim_lock_policy_resolution_failed",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=request,
        )

    runtime.resolve.assert_called_once_with(
        workspace_id="workspace_test",
        user_id="user_test",
        text=request.text,
        explicit_protected_terms=(),
        claim_lock_enforcement_mode=None,
    )

    admission.admit.assert_not_called()
    workflow.execute.assert_not_called()
    history.record_rewrite.assert_not_called()

def test_rewrite_route_preserves_omitted_claim_lock_mode_and_maps_runtime_integrity_to_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rewrite = MagicMock()
    rewrite.execute.side_effect = (
        EnterpriseClaimLockRuntimeIntegrityError(
            "claim_lock_policy_resolution_failed"
        )
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        SimpleNamespace(
            rewrite=rewrite,
        ),
    )

    request = WorkspaceRewriteRequest.model_validate(
        {
            "user_id": "user_test",
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

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == (
        "claim_lock_policy_resolution_failed"
    )

    rewrite.execute.assert_called_once()

    assert (
        rewrite.execute.call_args.kwargs[
            "claim_lock_enforcement_mode"
        ]
        is None
    )
