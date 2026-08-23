from app.v2.domain.enterprise_rbac import EnterprisePermission
from tests.v2.test_support_authorization_gate import (
    allow_all_workspace_authorization_gate,
    deny_all_workspace_authorization_gate,
    deny_permission_workspace_authorization_gate,
)
from app.domain.models import (
    DocumentType,
    EditorialQualityDecision,
    EditorialQualityResult,
    ProviderExecutionEvidence,
    ProviderUsageEvidence,
    ReleaseDecision,
    RewriteIntensity,
    RewriteNecessityEvidence,
    RewriteRequest,
    RewriteResponse,
    VerificationResult,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.services.rewrite_history_service import (
    RewriteHistoryService,
)
from app.v2.services.workspace_service import (
    WorkspaceService,
)


def _build_services(
    *,
    authorization_gate=None,
) -> tuple[
    WorkspaceService,
    RewriteHistoryService,
]:
    users = InMemoryUserRepository()
    workspaces = InMemoryWorkspaceRepository()
    memberships = InMemoryMembershipRepository()
    history = InMemoryRewriteHistoryRepository()

    workspace_service = WorkspaceService(
        users=users,
        workspaces=workspaces,
        memberships=memberships,
    )

    history_service = RewriteHistoryService(
        history=history,
        authorization_gate=(
            authorization_gate
            or allow_all_workspace_authorization_gate()
        ),
    )

    return (
        workspace_service,
        history_service,
    )


def _rewrite_request() -> RewriteRequest:
    return RewriteRequest(
        text="Original text.",
        document_type=DocumentType.GENERAL,
        audience="general audience",
        tone="natural",
        intensity=(RewriteIntensity.NATURAL_REWRITE),
        preserve_numbers=True,
        preserve_dates=True,
    )


def _rewrite_response() -> RewriteResponse:
    return RewriteResponse(
        trace_id="trace-1",
        workflow_states=[
            "received",
            "ready_for_review",
        ],
        source_text="Original text.",
        rewritten_text="Improved text.",
        provider_name="cloudflare-workers-ai",
        model_name="test-model",
        prompt_version="test-v1",
        provider_execution=(
            ProviderExecutionEvidence(
                latency_ms=100.0,
                primary_provider_name=("cloudflare-workers-ai"),
                actual_provider_name=("cloudflare-workers-ai"),
                fallback_used=False,
                provider_error_category=None,
                usage=ProviderUsageEvidence(
                    input_tokens=None,
                    output_tokens=None,
                    total_tokens=None,
                ),
            )
        ),
        rewrite_necessity=(
            RewriteNecessityEvidence(
                decision="full_rewrite",
                score=60,
                provider_required=True,
                signals=[],
                rationale="Test rewrite.",
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
            decision=ReleaseDecision.PASS,
            preserved_facts=[],
            missing_facts=[],
            unexpected_facts=[],
            warnings=[],
        ),
    )


def test_workspace_creation_adds_owner_membership() -> None:
    workspace_service, _ = _build_services()

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Example Workspace",
    )

    membership = workspace_service.require_membership(
        workspace_id=(workspace.workspace_id),
        user_id=user.user_id,
    )

    assert membership.role.value == "owner"


def test_rewrite_history_requires_membership() -> None:
    workspace_service, history_service = _build_services(
        authorization_gate=deny_permission_workspace_authorization_gate(
            EnterprisePermission.HISTORY_READ
        ),
    )

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Example Workspace",
    )

    record = history_service.record_rewrite(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=_rewrite_request(),
        response=_rewrite_response(),
    )

    assert record.trace_id == "trace-1"
    assert record.workspace_id == (workspace.workspace_id)
    assert record.user_id == user.user_id


def test_workspace_history_is_returned() -> None:
    workspace_service, history_service = _build_services()

    user = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    workspace = workspace_service.create_workspace(
        user_id=user.user_id,
        name="Example Workspace",
    )

    created = history_service.record_rewrite(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=_rewrite_request(),
        response=_rewrite_response(),
    )

    records = history_service.list_workspace_history(
        workspace_id=(workspace.workspace_id),
        user_id=user.user_id,
    )

    assert records == (created,)


def test_non_member_cannot_read_history() -> None:
    workspace_service, history_service = _build_services(
        authorization_gate=deny_all_workspace_authorization_gate(),
    )

    owner = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    outsider = workspace_service.create_user(
        email="outsider@example.com",
        display_name="Outsider",
    )

    workspace = workspace_service.create_workspace(
        user_id=owner.user_id,
        name="Example Workspace",
    )

    try:
        history_service.list_workspace_history(
            workspace_id=(workspace.workspace_id),
            user_id=outsider.user_id,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected PermissionError.")


def test_workspace_rewrite_executes_and_records_history() -> None:
    from app.v2.services.workspace_rewrite_service import (
        WorkspaceRewriteService,
    )
    from app.workflows.rewrite_workflow import (
        RewriteWorkflow,
    )

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
        name="Example Workspace",
    )

    result = rewrite_service.execute(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
        request=_rewrite_request(),
    )

    assert result.history.trace_id == (result.response.trace_id)
    assert result.history.source_text == (result.response.source_text)
    assert result.history.rewritten_text == (result.response.rewritten_text)

    records = history_service.list_workspace_history(
        workspace_id=workspace.workspace_id,
        user_id=user.user_id,
    )

    assert records == (result.history,)


def test_workspace_rewrite_rejects_non_member() -> None:
    from app.v2.services.workspace_rewrite_service import (
        WorkspaceRewriteService,
    )
    from app.workflows.rewrite_workflow import (
        RewriteWorkflow,
    )

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
        authorization_gate=deny_all_workspace_authorization_gate(),
    )

    rewrite_service = WorkspaceRewriteService(
        history_service=history_service,
        workflow=RewriteWorkflow(),
        authorization_gate=deny_all_workspace_authorization_gate(),
    )

    owner = workspace_service.create_user(
        email="owner@example.com",
        display_name="Owner",
    )

    outsider = workspace_service.create_user(
        email="outsider@example.com",
        display_name="Outsider",
    )

    workspace = workspace_service.create_workspace(
        user_id=owner.user_id,
        name="Example Workspace",
    )

    try:
        rewrite_service.execute(
            workspace_id=workspace.workspace_id,
            user_id=outsider.user_id,
            request=_rewrite_request(),
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected PermissionError.")
