from __future__ import annotations

from tests.v2.test_support_authorization_gate import (
    allow_all_workspace_authorization_gate,
    deny_all_workspace_authorization_gate,
)
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
from app.v2.api.models import WorkspaceLongDocumentRewriteRequest
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
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
    EnterpriseClaimLockRuntimeIntegrityError,
    EnterpriseClaimLockRuntimeService,
)
from app.v2.services.enterprise_long_document_quota_admission_service import (
    EnterpriseLongDocumentQuotaAdmissionService,
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
from app.v2.services.long_document_audit_service import (
    LongDocumentAuditService,
)
from app.v2.services.long_document_control_evaluator import (
    LongDocumentControlEvaluator,
)
from app.v2.services.long_document_rewrite_service import (
    LongDocumentWorkspaceRewriteService,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateWorkspaceRewriteService,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteOrchestrator,
)
from app.v2.services.section_rewrite_planner import (
    SectionRewritePlanner,
)
from app.v2.services.workspace_rewrite_service import (
    WorkspaceRewriteService,
)
from app.v2.services.workspace_service import WorkspaceService

OCCURRED_AT = datetime(
    2026,
    8,
    14,
    7,
    0,
    tzinfo=UTC,
)

WINDOW = EnterpriseQuotaWindow(
    window_start=OCCURRED_AT - timedelta(hours=1),
    window_end=OCCURRED_AT + timedelta(hours=1),
)

CONTEXT = EnterpriseQuotaRuntimeContext(
    workspace_id="workspace_test",
    operation=EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
    occurred_at=OCCURRED_AT,
    window=WINDOW,
    accounting_group_id="quota_group_long_document_test",
)


def _request(
    text: str = "First section.\n\nSecond section.",
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
    EnterpriseLongDocumentQuotaAdmissionService,
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

    service = EnterpriseLongDocumentQuotaAdmissionService(
        runtime_context=runtime_context,
        enforcement=enforcement,
    )

    return service, runtime_context, enforcement


def _long_service(
    *,
    quota_admission: (
        EnterpriseLongDocumentQuotaAdmissionService | MagicMock | None
    ),
    workspace_service: MagicMock | None = None,
    authorization_gate=None,
    preparation: MagicMock | None = None,
    structure_detector: MagicMock | None = None,
    planner: MagicMock | None = None,
    orchestrator: MagicMock | None = None,
    control_evaluator: MagicMock | None = None,
    reconstructor: MagicMock | None = None,
    audit_service: MagicMock | None = None,
    observability: MagicMock | None = None,
    section_count: int = 3,
) -> tuple[
    LongDocumentWorkspaceRewriteService,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    workspace = workspace_service or MagicMock(
        spec=WorkspaceService,
    )
    claim_lock_preparation = preparation or MagicMock(
        spec=ClaimLockPreparationService,
    )
    detector = structure_detector or MagicMock(
        spec=DocumentStructureDetector,
    )
    section_planner = planner or MagicMock(
        spec=SectionRewritePlanner,
    )
    section_orchestrator = orchestrator or MagicMock(
        spec=SectionRewriteOrchestrator,
    )
    evaluator = control_evaluator or MagicMock(
        spec=LongDocumentControlEvaluator,
    )
    document_reconstructor = reconstructor or MagicMock(
        spec=DocumentReconstructor,
    )
    long_document_audit = audit_service or MagicMock(
        spec=LongDocumentAuditService,
    )

    claim_lock_preparation.prepare.return_value = MagicMock(
        spec=ClaimLockPreparationResult,
    )

    structure = MagicMock()
    detector.detect.return_value = structure

    plan = MagicMock()
    plan.entries = tuple(
        MagicMock()
        for _ in range(section_count)
    )
    section_planner.plan.return_value = plan

    service = LongDocumentWorkspaceRewriteService(
        claim_lock_preparation_service=claim_lock_preparation,
        structure_detector=detector,
        planner=section_planner,
        orchestrator=section_orchestrator,
        control_evaluator=evaluator,
        reconstructor=document_reconstructor,
        audit_service=long_document_audit,
        long_document_quota_admission=quota_admission,
        observability=observability,
        authorization_gate=(
            authorization_gate
            or allow_all_workspace_authorization_gate()
        ),
    )

    return (
        service,
        workspace,
        claim_lock_preparation,
        detector,
        section_planner,
        section_orchestrator,
        evaluator,
        document_reconstructor,
    )


def test_long_document_operation_is_sent_to_runtime_context() -> None:
    service, runtime_context, _enforcement = _admission_service()

    service.admit(
        workspace_id="workspace_test",
        request=_request(),
        section_count=3,
    )

    runtime_context.resolve.assert_called_once_with(
        workspace_id="workspace_test",
        operation=EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
    )


def test_long_document_exact_quantities_are_sent_to_enforcement() -> None:
    service, _runtime_context, enforcement = _admission_service()
    request = _request("123456789")

    service.admit(
        workspace_id="workspace_test",
        request=request,
        section_count=4,
    )

    assert enforcement.enforce.call_args.kwargs[
        "requested_quantities"
    ] == {
        EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
        EnterpriseQuotaDimension.INPUT_CHARACTERS: len(request.text),
        EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS: 4,
    }


def test_long_document_context_is_forwarded_unchanged() -> None:
    service, _runtime_context, enforcement = _admission_service()
    request = _request()

    service.admit(
        workspace_id=CONTEXT.workspace_id,
        request=request,
        section_count=2,
    )

    enforcement.enforce.assert_called_once_with(
        workspace_id=CONTEXT.workspace_id,
        operation=EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
        window=CONTEXT.window,
        accounting_group_id=CONTEXT.accounting_group_id,
        requested_quantities={
            EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
            EnterpriseQuotaDimension.INPUT_CHARACTERS: len(
                request.text
            ),
            EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS: 2,
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
            section_count=3,
        )


def test_non_member_fails_before_long_document_quota() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )

    workspace = MagicMock(
        spec=WorkspaceService,
    )

    (
        service,
        _workspace,
        _preparation,
        detector,
        planner,
        orchestrator,
        _evaluator,
        _reconstructor,
    ) = _long_service(
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
    detector.detect.assert_not_called()
    planner.plan.assert_not_called()
    orchestrator.execute.assert_not_called()


def test_preparation_structure_and_plan_occur_before_quota() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )

    (
        service,
        _workspace,
        preparation,
        detector,
        planner,
        orchestrator,
        _evaluator,
        _reconstructor,
    ) = _long_service(
        quota_admission=admission,
        section_count=4,
    )

    def deny_after_plan(**_kwargs: object) -> None:
        preparation.prepare.assert_called_once()
        detector.detect.assert_called_once()
        planner.plan.assert_called_once()

        raise EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )

    admission.admit.side_effect = deny_after_plan

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    orchestrator.execute.assert_not_called()


def test_validated_plan_entry_count_is_quota_authority() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    (
        service,
        _workspace,
        _preparation,
        _detector,
        _planner,
        orchestrator,
        _evaluator,
        _reconstructor,
    ) = _long_service(
        quota_admission=admission,
        section_count=5,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    assert admission.admit.call_args.kwargs["section_count"] == 5
    orchestrator.execute.assert_not_called()


def test_allowed_admission_proceeds_to_section_orchestrator() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )
    admission.admit.return_value = _enforcement_result(
        consumed=True,
    )

    orchestrator = MagicMock(
        spec=SectionRewriteOrchestrator,
    )
    orchestrator.execute.side_effect = RuntimeError(
        "section execution reached"
    )

    (
        service,
        _workspace,
        _preparation,
        _detector,
        _planner,
        _orchestrator,
        _evaluator,
        _reconstructor,
    ) = _long_service(
        quota_admission=admission,
        orchestrator=orchestrator,
    )

    with pytest.raises(
        RuntimeError,
        match="section execution reached",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    admission.admit.assert_called_once()
    orchestrator.execute.assert_called_once()


def test_denied_admission_executes_zero_section_orchestration() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    (
        service,
        _workspace,
        _preparation,
        _detector,
        _planner,
        orchestrator,
        _evaluator,
        _reconstructor,
    ) = _long_service(
        quota_admission=admission,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    orchestrator.execute.assert_not_called()


def test_denied_admission_writes_zero_downstream_evidence() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )
    admission.admit.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    evaluator = MagicMock(
        spec=LongDocumentControlEvaluator,
    )
    reconstructor = MagicMock(
        spec=DocumentReconstructor,
    )
    audit_service = MagicMock(
        spec=LongDocumentAuditService,
    )
    observability = MagicMock(
        spec=LongDocumentObservability,
    )

    service, *_ = _long_service(
        quota_admission=admission,
        control_evaluator=evaluator,
        reconstructor=reconstructor,
        audit_service=audit_service,
        observability=observability,
    )

    with pytest.raises(EnterpriseQuotaAdmissionDeniedError):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    evaluator.evaluate.assert_not_called()
    reconstructor.reconstruct.assert_not_called()
    audit_service.record.assert_not_called()
    observability.record_success.assert_not_called()


def test_runtime_context_failure_prevents_section_execution() -> None:
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

    admission = EnterpriseLongDocumentQuotaAdmissionService(
        runtime_context=runtime_context,
        enforcement=enforcement,
    )

    (
        service,
        _workspace,
        _preparation,
        _detector,
        _planner,
        orchestrator,
        _evaluator,
        _reconstructor,
    ) = _long_service(
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
    orchestrator.execute.assert_not_called()


def test_long_document_route_maps_actual_quota_denial_to_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_document = MagicMock()
    long_document.execute.side_effect = (
        EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(consumed=False)
        )
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        SimpleNamespace(
            long_document=long_document,
        ),
    )

    request = WorkspaceLongDocumentRewriteRequest.model_validate(
        {
            "user_id": "user_test",
            "rewrite": {
                "text": "First paragraph.\n\nSecond paragraph.",
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
        v2_routes.create_workspace_long_document_rewrite(
            workspace_id="workspace_test",
            request=request,
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == (
        "enterprise quota admission denied"
    )


def test_single_and_multi_services_do_not_receive_long_document_hook() -> None:
    single_parameters = signature(
        WorkspaceRewriteService.__init__
    ).parameters

    multi_parameters = signature(
        MultiCandidateWorkspaceRewriteService.__init__
    ).parameters

    assert "long_document_quota_admission" not in single_parameters
    assert "long_document_quota_admission" not in multi_parameters


def _enterprise_runtime_long_service(
    *,
    quota_admission: MagicMock | None,
    section_count: int = 4,
) -> tuple[
    LongDocumentWorkspaceRewriteService,
    MagicMock,
    SimpleNamespace,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    runtime = MagicMock(
        spec=EnterpriseClaimLockRuntimeService,
    )

    request_preparation = MagicMock(
        spec=ClaimLockPreparationResult,
    )

    effective_claim_lock = MagicMock(
        name="effective_claim_lock",
    )

    runtime_context = SimpleNamespace(
        request_preparation=request_preparation,
        effective_claim_lock=effective_claim_lock,
    )

    runtime.resolve.return_value = runtime_context

    detector = MagicMock(
        spec=DocumentStructureDetector,
    )
    structure = MagicMock(
        name="document_structure",
    )
    detector.detect.return_value = structure

    planner = MagicMock(
        spec=SectionRewritePlanner,
    )
    plan = MagicMock(
        name="section_plan",
    )
    plan.entries = tuple(
        MagicMock()
        for _ in range(section_count)
    )
    planner.plan.return_value = plan

    orchestrator = MagicMock(
        spec=SectionRewriteOrchestrator,
    )
    execution = MagicMock(
        name="section_execution",
    )
    orchestrator.execute.return_value = execution

    evaluator = MagicMock(
        spec=LongDocumentControlEvaluator,
    )
    evaluation = MagicMock(
        name="control_evaluation",
    )
    evaluator.evaluate.return_value = evaluation

    reconstructor = MagicMock(
        spec=DocumentReconstructor,
    )
    reconstruction = MagicMock(
        name="document_reconstruction",
    )
    reconstructor.reconstruct.return_value = reconstruction

    audit_service = MagicMock(
        spec=LongDocumentAuditService,
    )
    audit_record = MagicMock(
        name="long_document_audit",
    )
    audit_service.record.return_value = audit_record

    service = LongDocumentWorkspaceRewriteService(
        enterprise_claim_lock_runtime_service=runtime,
        structure_detector=detector,
        planner=planner,
        orchestrator=orchestrator,
        control_evaluator=evaluator,
        reconstructor=reconstructor,
        audit_service=audit_service,
        long_document_quota_admission=quota_admission,
        authorization_gate=(
            allow_all_workspace_authorization_gate()
        ),
    )

    return (
        service,
        runtime,
        runtime_context,
        effective_claim_lock,
        detector,
        planner,
        orchestrator,
        evaluator,
        reconstructor,
        audit_service,
    )


def test_long_document_rejects_dual_claim_lock_authority() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "must not receive both enterprise Claim Lock "
            "runtime and direct preparation authority"
        ),
    ):
        LongDocumentWorkspaceRewriteService(
            enterprise_claim_lock_runtime_service=MagicMock(
                spec=EnterpriseClaimLockRuntimeService,
            ),
            claim_lock_preparation_service=MagicMock(
                spec=ClaimLockPreparationService,
            ),
            structure_detector=MagicMock(
                spec=DocumentStructureDetector,
            ),
            planner=MagicMock(
                spec=SectionRewritePlanner,
            ),
            orchestrator=MagicMock(
                spec=SectionRewriteOrchestrator,
            ),
            control_evaluator=MagicMock(
                spec=LongDocumentControlEvaluator,
            ),
            reconstructor=MagicMock(
                spec=DocumentReconstructor,
            ),
            audit_service=MagicMock(
                spec=LongDocumentAuditService,
            ),
            authorization_gate=(
                allow_all_workspace_authorization_gate()
            ),
        )


def test_enterprise_runtime_resolves_once_for_complete_document() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )

    (
        service,
        runtime,
        runtime_context,
        effective_claim_lock,
        _detector,
        _planner,
        _orchestrator,
        evaluator,
        _reconstructor,
        audit_service,
    ) = _enterprise_runtime_long_service(
        quota_admission=admission,
        section_count=5,
    )

    request = _request(
        "One.\n\nTwo.\n\nThree.\n\nFour.\n\nFive."
    )

    result = service.execute(
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
        source_reference=(
            "long-document-rewrite-request"
        ),
    )

    assert admission.admit.call_args.kwargs[
        "section_count"
    ] == 5

    assert (
        evaluator.evaluate.call_args.kwargs[
            "claim_lock"
        ]
        is effective_claim_lock
    )

    assert (
        audit_service.record.call_args.kwargs[
            "claim_lock_runtime_context"
        ]
        is runtime_context
    )

    assert (
        result.claim_lock_runtime_context
        is runtime_context
    )

    assert (
        result.claim_lock_preparation
        is runtime_context.request_preparation
    )


def test_enterprise_runtime_resolves_before_quota_denial() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )

    (
        service,
        runtime,
        runtime_context,
        _effective_claim_lock,
        _detector,
        _planner,
        orchestrator,
        evaluator,
        reconstructor,
        audit_service,
    ) = _enterprise_runtime_long_service(
        quota_admission=admission,
        section_count=4,
    )

    call_order: list[str] = []

    def resolve_runtime(
        **_kwargs: object,
    ) -> SimpleNamespace:
        call_order.append("runtime")
        return runtime_context

    def deny_quota(
        **_kwargs: object,
    ) -> None:
        call_order.append("quota")

        assert runtime.resolve.call_count == 1

        raise EnterpriseQuotaAdmissionDeniedError(
            _enforcement_result(
                consumed=False,
            )
        )

    runtime.resolve.side_effect = resolve_runtime
    admission.admit.side_effect = deny_quota

    with pytest.raises(
        EnterpriseQuotaAdmissionDeniedError,
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    assert call_order == [
        "runtime",
        "quota",
    ]

    runtime.resolve.assert_called_once()

    orchestrator.execute.assert_not_called()
    evaluator.evaluate.assert_not_called()
    reconstructor.reconstruct.assert_not_called()
    audit_service.record.assert_not_called()


def test_enterprise_runtime_is_not_resolved_per_section() -> None:
    admission = MagicMock(
        spec=EnterpriseLongDocumentQuotaAdmissionService,
    )

    (
        service,
        runtime,
        _runtime_context,
        _effective_claim_lock,
        _detector,
        _planner,
        orchestrator,
        _evaluator,
        _reconstructor,
        _audit_service,
    ) = _enterprise_runtime_long_service(
        quota_admission=admission,
        section_count=6,
    )

    orchestrator.execute.side_effect = RuntimeError(
        "section generation reached",
    )

    with pytest.raises(
        RuntimeError,
        match="section generation reached",
    ):
        service.execute(
            workspace_id="workspace_test",
            user_id="user_test",
            request=_request(),
        )

    runtime.resolve.assert_called_once()

    assert admission.admit.call_args.kwargs[
        "section_count"
    ] == 6

    orchestrator.execute.assert_called_once()

def test_long_document_route_preserves_omitted_claim_lock_mode_and_maps_runtime_integrity_to_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_document = MagicMock()
    long_document.execute.side_effect = (
        EnterpriseClaimLockRuntimeIntegrityError(
            "claim_lock_composition_conflict"
        )
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        SimpleNamespace(
            long_document=long_document,
        ),
    )

    request = WorkspaceLongDocumentRewriteRequest.model_validate(
        {
            "user_id": "user_test",
            "rewrite": {
                "text": (
                    "First paragraph.\n\n"
                    "Second paragraph."
                ),
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
        v2_routes.create_workspace_long_document_rewrite(
            workspace_id="workspace_test",
            request=request,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == (
        "claim_lock_composition_conflict"
    )

    long_document.execute.assert_called_once()

    assert (
        long_document.execute.call_args.kwargs[
            "claim_lock_enforcement_mode"
        ]
        is None
    )
