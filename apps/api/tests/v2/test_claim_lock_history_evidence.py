from __future__ import annotations

from unittest.mock import MagicMock

from tests.v2.test_support_authorization_gate import allow_all_workspace_authorization_gate
import pytest
from pydantic import ValidationError

from app.domain.models import (
    RewriteRequest,
)
from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedClaim,
)
from app.v2.domain.claim_lock_audit import (
    ClaimLockValidationAuditCheck,
    ClaimLockValidationAuditSnapshot,
)
from app.v2.domain.enterprise_claim_lock_runtime import (
    EnterpriseClaimLockWorkspacePolicyExecutionEvidence,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.services.enterprise_claim_lock_runtime_service import (
    EnterpriseClaimLockRuntimeService,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.workspace_rewrite_service import (
    WorkspaceRewriteService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)
from app.workflows.rewrite_workflow import (
    RewriteWorkflow,
)


def _lock(
    *,
    mode: ClaimLockEnforcementMode = (ClaimLockEnforcementMode.STRICT),
) -> ClaimLock:
    return ClaimLock(
        lock_id="lock_history_test",
        enforcement_mode=mode,
        claims=(
            ProtectedClaim(
                claim_id="claim_history_1",
                text=("Deployment completed successfully."),
                provenance=ClaimLockProvenance(
                    origin=ClaimLockOrigin.REQUEST,
                    source_reference=("rewrite-request"),
                ),
            ),
        ),
    )


def _validation(
    *,
    mode: ClaimLockEnforcementMode = (ClaimLockEnforcementMode.STRICT),
) -> ClaimLockValidationAuditSnapshot:
    return ClaimLockValidationAuditSnapshot(
        validator_version=("claim-lock-validator-v1"),
        lock_id="lock_history_test",
        enforcement_mode=mode,
        decision="pass",
        checks=(
            ClaimLockValidationAuditCheck(
                item_id="claim_history_1",
                item_type="claim",
                expected_text=("Deployment completed successfully."),
                status="not_evaluated",
                reason=("semantic claim preservation is not deterministically evaluated"),
            ),
        ),
    )


def _base_history_kwargs() -> dict[str, object]:
    return {
        "rewrite_id": "history-claim-lock-1",
        "workspace_id": "workspace-1",
        "user_id": "user-1",
        "trace_id": "trace-1",
        "source_text": ("Deployment completed successfully."),
        "rewritten_text": ("The deployment completed successfully."),
        "document_type": "general",
        "audience": "general audience",
        "tone": "natural",
        "intensity": "natural_rewrite",
        "provider_name": ("cloudflare-workers-ai"),
        "model_name": "test-model",
        "prompt_version": "test-v1",
        "fallback_used": False,
        "verification_decision": "pass",
        "editorial_quality_decision": "pass",
    }


def test_history_accepts_complete_claim_lock_audit_tuple() -> None:
    record = RewriteHistoryRecord(
        **_base_history_kwargs(),
        claim_lock_snapshot=_lock(),
        claim_lock_validation=_validation(),
        claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
    )

    assert record.claim_lock_snapshot is not None
    assert record.claim_lock_validation is not None
    assert record.claim_lock_enforcement_mode is ClaimLockEnforcementMode.STRICT


@pytest.mark.parametrize(
    (
        "snapshot",
        "validation",
        "mode",
    ),
    (
        (
            _lock(),
            None,
            ClaimLockEnforcementMode.STRICT,
        ),
        (
            None,
            _validation(),
            ClaimLockEnforcementMode.STRICT,
        ),
        (
            _lock(),
            _validation(),
            None,
        ),
    ),
)
def test_history_rejects_partial_claim_lock_audit_tuple(
    snapshot: ClaimLock | None,
    validation: (ClaimLockValidationAuditSnapshot | None),
    mode: ClaimLockEnforcementMode | None,
) -> None:
    with pytest.raises(
        ValidationError,
        match=("claim lock audit fields must be all present or all absent"),
    ):
        RewriteHistoryRecord(
            **_base_history_kwargs(),
            claim_lock_snapshot=snapshot,
            claim_lock_validation=validation,
            claim_lock_enforcement_mode=mode,
        )


def test_history_rejects_claim_lock_id_mismatch() -> None:
    mismatched = _validation().model_copy(
        update={
            "lock_id": "lock_other",
        }
    )

    with pytest.raises(
        ValidationError,
        match=("claim lock validation lock_id must match snapshot"),
    ):
        RewriteHistoryRecord(
            **_base_history_kwargs(),
            claim_lock_snapshot=_lock(),
            claim_lock_validation=mismatched,
            claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
        )


def test_history_rejects_enforcement_mode_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=("claim lock validation enforcement mode mismatch"),
    ):
        RewriteHistoryRecord(
            **_base_history_kwargs(),
            claim_lock_snapshot=_lock(),
            claim_lock_validation=_validation(
                mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
            ),
            claim_lock_enforcement_mode=(ClaimLockEnforcementMode.STRICT),
        )


def test_historical_record_without_claim_lock_evidence_is_valid() -> None:
    record = RewriteHistoryRecord(
        **_base_history_kwargs(),
    )

    assert record.claim_lock_snapshot is None
    assert record.claim_lock_validation is None
    assert record.claim_lock_enforcement_mode is None


def test_workspace_rewrite_records_claim_lock_audit_evidence() -> None:
    users = InMemoryUserRepository()
    workspaces = InMemoryWorkspaceRepository()
    memberships = InMemoryMembershipRepository()
    history_repository = InMemoryRewriteHistoryRepository()

    workspace_service = WorkspaceService(
        users=users,
        workspaces=workspaces,
        memberships=memberships,
    )

    history_service = RewriteHistoryService(
        history=history_repository,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    rewrite_service = WorkspaceRewriteService(
        history_service=history_service,
        workflow=RewriteWorkflow(),
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Claim Lock History",
    )

    result = rewrite_service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=RewriteRequest(
            text=("Deployment completed successfully."),
        ),
    )

    record = result.history

    assert record.claim_lock_snapshot == result.claim_lock_preparation.claim_lock

    assert record.claim_lock_validation is not None

    assert record.claim_lock_validation.lock_id == (
        record.claim_lock_snapshot.lock_id if record.claim_lock_snapshot is not None else ""
    )

    assert record.claim_lock_validation.decision == result.claim_lock_validation.decision.value

    assert record.claim_lock_enforcement_mode is ClaimLockEnforcementMode.STRICT


def test_empty_claim_lock_preparation_keeps_history_audit_absent() -> None:
    users = InMemoryUserRepository()
    workspaces = InMemoryWorkspaceRepository()
    memberships = InMemoryMembershipRepository()
    history_repository = InMemoryRewriteHistoryRepository()

    workspace_service = WorkspaceService(
        users=users,
        workspaces=workspaces,
        memberships=memberships,
    )

    history_service = RewriteHistoryService(
        history=history_repository,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    rewrite_service = WorkspaceRewriteService(
        history_service=history_service,
        workflow=RewriteWorkflow(),
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Empty Claim Lock History",
    )

    result = rewrite_service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=RewriteRequest(
            text="Approved.",
        ),
    )

    assert result.claim_lock_preparation.claim_lock is None
    assert result.history.claim_lock_snapshot is None
    assert result.history.claim_lock_validation is None
    assert result.history.claim_lock_enforcement_mode is None

def _workspace_policy_execution_evidence(
) -> EnterpriseClaimLockWorkspacePolicyExecutionEvidence:
    return EnterpriseClaimLockWorkspacePolicyExecutionEvidence(
        policy_id="policy_history_test",
        policy_revision=7,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        applicable_term_ids=(),
    )


def test_history_workspace_policy_evidence_is_independent_of_v23_tuple(
) -> None:
    evidence = _workspace_policy_execution_evidence()

    record = RewriteHistoryRecord(
        **_base_history_kwargs(),
        claim_lock_workspace_policy=evidence,
    )

    assert record.claim_lock_snapshot is None
    assert record.claim_lock_validation is None
    assert record.claim_lock_enforcement_mode is None
    assert record.claim_lock_workspace_policy == evidence


def test_history_service_persists_workspace_policy_evidence_without_claim_lock_tuple(
) -> None:
    repository = InMemoryRewriteHistoryRepository()

    service = RewriteHistoryService(
        history=repository,
        authorization_gate=(
            allow_all_workspace_authorization_gate()
        ),
    )

    request = RewriteRequest(
        text="Approved.",
    )
    response = RewriteWorkflow().execute(
        request
    )
    evidence = _workspace_policy_execution_evidence()

    record = service.record_rewrite(
        workspace_id="workspace-policy-history",
        user_id="user-policy-history",
        request=request,
        response=response,
        claim_lock_workspace_policy=evidence,
    )

    assert record.claim_lock_snapshot is None
    assert record.claim_lock_validation is None
    assert record.claim_lock_enforcement_mode is None
    assert record.claim_lock_workspace_policy == evidence


def test_workspace_rewrite_forwards_runtime_workspace_policy_evidence(
) -> None:
    repository = InMemoryRewriteHistoryRepository()

    history_service = RewriteHistoryService(
        history=repository,
        authorization_gate=(
            allow_all_workspace_authorization_gate()
        ),
    )

    evidence = _workspace_policy_execution_evidence()

    runtime_context = MagicMock()
    runtime_context.request_preparation = MagicMock()
    runtime_context.effective_claim_lock = _lock()
    runtime_context.effective_enforcement_mode = (
        ClaimLockEnforcementMode.STRICT
    )
    runtime_context.workspace_policy_evidence = evidence

    runtime = MagicMock(
        spec=EnterpriseClaimLockRuntimeService,
    )
    runtime.resolve.return_value = runtime_context

    service = WorkspaceRewriteService(
        history_service=history_service,
        workflow=RewriteWorkflow(),
        enterprise_claim_lock_runtime_service=runtime,
        authorization_gate=(
            allow_all_workspace_authorization_gate()
        ),
    )

    request = RewriteRequest(
        text="Deployment completed successfully.",
    )

    result = service.execute(
        workspace_id="workspace-runtime-history",
        user_id="user-runtime-history",
        request=request,
        claim_lock_enforcement_mode=None,
    )

    assert result.history.claim_lock_workspace_policy == evidence

    runtime.resolve.assert_called_once_with(
        workspace_id="workspace-runtime-history",
        user_id="user-runtime-history",
        text=request.text,
        explicit_protected_terms=(),
        claim_lock_enforcement_mode=None,
    )
