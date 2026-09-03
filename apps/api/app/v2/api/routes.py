from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    status,
)

from app.v2.api.dependencies import services
from app.v2.api.evidence_access import (
    EvidenceAccessDeniedError,
    EvidenceExposureDisabledError,
    require_evidence_access,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
)
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
    permissions_for_role,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseMembershipStatus,
)
from app.v2.domain.eval_ops import (
    EvaluationRunOutcome,
)
from app.v2.domain.models import VoiceProfileStatus
from app.v2.domain.observability import (
    WorkspaceAnalyticsSnapshot,
)
from app.v2.domain.provider_routing import (
    RoutingDecisionStatus,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceExecutionOutcome,
)
from app.v2.services.candidate_control_enforcement import (
    CandidateClaimLockViolationError,
)
from app.v2.services.candidate_rewrite_orchestrator import (
    CandidateGenerationError,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockViolationError,
)
from app.v2.services.document_reconstructor import (
    DocumentReconstructionIntegrityError,
)
from app.v2.services.enterprise_authorization_resolver import (
    AuthorizationResolutionFailureReason,
    AuthorizationResolutionStatus,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
)
from app.v2.services.enterprise_claim_lock_admin_service import (
    ClaimLockAdministrationFailureReason,
    EnterpriseClaimLockAdministrationError,
)
from app.v2.services.enterprise_claim_lock_runtime_service import (
    EnterpriseClaimLockRuntimeIntegrityError,
)
from app.v2.services.enterprise_membership_admin_service import (
    EnterpriseMembershipAdministrationError,
    MembershipAdministrationFailureReason,
)
from app.v2.services.enterprise_quota_admin_service import (
    EnterpriseQuotaAdministrationError,
    QuotaAdministrationFailureReason,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseQuotaAdmissionDeniedError,
)
from app.v2.services.long_document_audit_service import (
    LongDocumentAuditIntegrityError,
)
from app.v2.services.long_document_control_evaluator import (
    CrossSectionConsistencyViolationError,
    LongDocumentControlEvaluationError,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateVoiceUnavailableError,
    NoEligibleCandidateError,
)
from app.v2.services.routing_eval_evidence_query_service import (
    EvaluationEvidenceNotFoundError,
    RoutingEvidenceNotFoundError,
)
from app.v2.services.section_rewrite_orchestrator import (
    SectionRewriteExecutionError,
)
from app.v2.services.voice_profile_service import (
    VoiceProfileLifecycleError,
)
from app.v2.services.voice_rewrite_guidance import (
    VoiceProfileAnalysisRequiredError,
    VoiceProfileInactiveError,
)
from app.v2.services.workspace_provider_routing_execution_evidence_query_service import (
    WorkspaceProviderRoutingExecutionEvidence,
    WorkspaceProviderRoutingExecutionEvidenceIntegrityError,
)
from app.v2.services.workspace_analytics_query_service import (
    WorkspaceAnalyticsQueryLimitError,
)

__all__ = [
    "router",
    "services",
]


from app.v2.api.models import (
    AddEnterpriseMemberRequest,
    AnalyzeVoiceProfileRequest,
    ArchiveVoiceProfileRequest,
    CandidateControlRewriteEvidence,
    ChangeEnterpriseMemberRoleRequest,
    ClaimLockRewriteEvidence,
    CreateEnterpriseClaimLockPolicyRequest,
    CreateEnterpriseQuotaLimitRequest,
    EnterpriseClaimLockPolicyLifecycleRequest,
    EnterpriseClaimLockPolicyResponse,
    EnterpriseClaimLockProtectedTermInput,
    CreateUserRequest,
    CreateUserResponse,
    CreateVoiceProfileRequest,
    CreateWorkspaceRequest,
    CreateWorkspaceResponse,
    EnterpriseMemberLifecycleRequest,
    EnterpriseMemberListResponse,
    EnterpriseMemberResponse,
    EnterpriseQuotaLimitListResponse,
    EnterpriseQuotaLimitResponse,
    EnterpriseWorkspaceAccessContextResponse,
    EnterpriseWorkspaceOwnershipTransferResponse,
    EvaluationEvidenceListResponse,
    EvaluationEvidenceResponse,
    MultiCandidateRewriteEvidence,
    ProviderCatalogTargetVisibility,
    RoutingEvidenceListResponse,
    RoutingEvidenceResponse,
    TransferEnterpriseWorkspaceOwnershipRequest,
    UpdateEnterpriseClaimLockPolicyRequest,
    UpdateVoiceProfileRequest,
    VoiceProfileAnalysisResponse,
    VoiceProfileListResponse,
    VoiceProfileResponse,
    VoiceRewriteEvidence,
    WorkspaceHistoryResponse,
    WorkspaceProviderCatalogVisibilityResponse,
    WorkspaceProviderRoutingEvidenceBindingResponse,
    WorkspaceProviderRoutingExecutionEvidenceListResponse,
    WorkspaceProviderRoutingExecutionEvidenceResponse,
    WorkspaceLongDocumentRewriteRequest,
    WorkspaceLongDocumentRewriteResponse,
    WorkspaceRewriteRequest,
    WorkspaceRewriteResponse,
)

router = APIRouter(
    prefix="/api/v2",
    tags=["v2"],
)


def _claim_lock_admin_http_exception(
    exc: EnterpriseClaimLockAdministrationError,
) -> HTTPException:
    reason = exc.reason

    if reason in {
        ClaimLockAdministrationFailureReason
        .AUTHORIZATION_RESOLUTION_FAILED,
        ClaimLockAdministrationFailureReason
        .AUTHORIZATION_DENIED,
    }:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason.value,
        )

    if reason in {
        ClaimLockAdministrationFailureReason.POLICY_NOT_FOUND,
        ClaimLockAdministrationFailureReason.POLICY_SCOPE_MISMATCH,
    }:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                ClaimLockAdministrationFailureReason
                .POLICY_NOT_FOUND.value
            ),
        )

    if reason in {
        ClaimLockAdministrationFailureReason.POLICY_ALREADY_EXISTS,
        ClaimLockAdministrationFailureReason.POLICY_ARCHIVED,
        ClaimLockAdministrationFailureReason.POLICY_NOT_ACTIVE,
        ClaimLockAdministrationFailureReason.POLICY_ALREADY_ACTIVE,
        ClaimLockAdministrationFailureReason
        .POLICY_ALREADY_DISABLED,
        ClaimLockAdministrationFailureReason.REVISION_CONFLICT,
    }:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=reason.value,
        )

    if (
        reason
        is ClaimLockAdministrationFailureReason
        .INVALID_WORKSPACE_TERM
    ):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=reason.value,
        )

    if reason in {
        ClaimLockAdministrationFailureReason.PERSISTENCE_REJECTED,
        ClaimLockAdministrationFailureReason.TRANSACTION_REQUIRED,
    }:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=reason.value,
        )

    raise RuntimeError(
        "unsupported enterprise claim lock "
        "administration failure reason"
    )


def _claim_lock_admin_term_payloads(
    terms: tuple[
        EnterpriseClaimLockProtectedTermInput,
        ...,
    ],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "term_id": term.term_id,
            "text": term.text,
            "case_sensitive": term.case_sensitive,
        }
        for term in terms
    )


def _quota_admin_http_exception(
    exc: EnterpriseQuotaAdministrationError,
) -> HTTPException:
    if exc.reason in {
        QuotaAdministrationFailureReason.AUTHORIZATION_RESOLUTION_FAILED,
        QuotaAdministrationFailureReason.AUTHORIZATION_DENIED,
    }:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.reason.value,
        )

    if (
        exc.reason
        is QuotaAdministrationFailureReason.LIMIT_NOT_FOUND
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.reason.value,
        )

    if (
        exc.reason
        is QuotaAdministrationFailureReason.LIMIT_SCOPE_MISMATCH
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.reason.value,
        )

    raise RuntimeError(
        "unsupported enterprise quota administration failure reason"
    )


def _membership_admin_http_exception(
    exc: EnterpriseMembershipAdministrationError,
) -> HTTPException:
    if exc.reason in {
        MembershipAdministrationFailureReason.AUTHORIZATION_RESOLUTION_FAILED,
        MembershipAdministrationFailureReason.AUTHORIZATION_DENIED,
    }:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.reason.value,
        )

    if exc.reason in {
        MembershipAdministrationFailureReason.TARGET_NOT_FOUND,
        MembershipAdministrationFailureReason.TARGET_SCOPE_MISMATCH,
    }:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.reason.value,
        )

    if exc.reason in {
        MembershipAdministrationFailureReason.DUPLICATE_CURRENT_MEMBERSHIP,
        MembershipAdministrationFailureReason.NEW_MEMBERSHIP_ID_REQUIRED,
        MembershipAdministrationFailureReason.OWNER_ROLE_REQUIRES_TRANSFER,
        MembershipAdministrationFailureReason.OWNER_LIFECYCLE_PROTECTED,
        MembershipAdministrationFailureReason.MEMBERSHIP_REMOVED,
        MembershipAdministrationFailureReason.MEMBERSHIP_NOT_ACTIVE,
        MembershipAdministrationFailureReason.MEMBERSHIP_NOT_SUSPENDED,
    }:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.reason.value,
        )

    if (
        exc.reason
        is MembershipAdministrationFailureReason.TRANSACTION_REQUIRED
    ):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.reason.value,
        )

    raise RuntimeError(
        "unsupported enterprise membership administration failure reason"
    )


def _enterprise_member_response(
    membership,
) -> EnterpriseMemberResponse:
    return EnterpriseMemberResponse(
        membership=membership,
        effective_permissions=tuple(
            sorted(
                permissions_for_role(membership.role),
                key=lambda permission: permission.value,
            )
        ),
    )


@router.post(
    "/users",
    response_model=CreateUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    request: CreateUserRequest,
) -> CreateUserResponse:
    user = services.workspace.create_user(
        email=request.email,
        display_name=request.display_name,
    )

    return CreateUserResponse(
        user=user,
    )


@router.post(
    "/workspaces",
    response_model=CreateWorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    request: CreateWorkspaceRequest,
) -> CreateWorkspaceResponse:
    try:
        workspace = services.workspace_provisioning.create_workspace(
            user_id=request.user_id,
            name=request.name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return CreateWorkspaceResponse(
        workspace=workspace,
    )


@router.get(
    "/workspaces/{workspace_id}/claim-lock-policy",
    response_model=EnterpriseClaimLockPolicyResponse,
)
def get_enterprise_claim_lock_policy(
    workspace_id: str,
    actor_user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
) -> EnterpriseClaimLockPolicyResponse:
    try:
        policy = services.claim_lock_admin.get_policy(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
        )
    except EnterpriseClaimLockAdministrationError as exc:
        raise _claim_lock_admin_http_exception(exc) from exc

    return EnterpriseClaimLockPolicyResponse(
        policy=policy,
    )


@router.post(
    "/workspaces/{workspace_id}/claim-lock-policy",
    response_model=EnterpriseClaimLockPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_enterprise_claim_lock_policy(
    workspace_id: str,
    request: CreateEnterpriseClaimLockPolicyRequest,
) -> EnterpriseClaimLockPolicyResponse:
    protected_terms = _claim_lock_admin_term_payloads(
        request.protected_terms
    )

    try:
        policy = services.claim_lock_admin.create_policy(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            policy_id=request.policy_id,
            enforcement_mode=request.enforcement_mode,
            protected_terms=protected_terms,
            status=EnterpriseClaimLockPolicyStatus.ACTIVE,
        )
    except EnterpriseClaimLockAdministrationError as exc:
        raise _claim_lock_admin_http_exception(exc) from exc

    return EnterpriseClaimLockPolicyResponse(
        policy=policy,
    )


@router.patch(
    "/workspaces/{workspace_id}/claim-lock-policy",
    response_model=EnterpriseClaimLockPolicyResponse,
)
def update_enterprise_claim_lock_policy(
    workspace_id: str,
    request: UpdateEnterpriseClaimLockPolicyRequest,
) -> EnterpriseClaimLockPolicyResponse:
    protected_terms = _claim_lock_admin_term_payloads(
        request.protected_terms
    )

    try:
        policy = services.claim_lock_admin.update_policy(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            policy_id=request.policy_id,
            expected_revision=request.expected_revision,
            enforcement_mode=request.enforcement_mode,
            protected_terms=protected_terms,
        )
    except EnterpriseClaimLockAdministrationError as exc:
        raise _claim_lock_admin_http_exception(exc) from exc

    return EnterpriseClaimLockPolicyResponse(
        policy=policy,
    )


@router.post(
    "/workspaces/{workspace_id}/claim-lock-policy/enable",
    response_model=EnterpriseClaimLockPolicyResponse,
)
def enable_enterprise_claim_lock_policy(
    workspace_id: str,
    request: EnterpriseClaimLockPolicyLifecycleRequest,
) -> EnterpriseClaimLockPolicyResponse:
    try:
        policy = services.claim_lock_admin.enable_policy(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            policy_id=request.policy_id,
            expected_revision=request.expected_revision,
        )
    except EnterpriseClaimLockAdministrationError as exc:
        raise _claim_lock_admin_http_exception(exc) from exc

    return EnterpriseClaimLockPolicyResponse(
        policy=policy,
    )


@router.post(
    "/workspaces/{workspace_id}/claim-lock-policy/disable",
    response_model=EnterpriseClaimLockPolicyResponse,
)
def disable_enterprise_claim_lock_policy(
    workspace_id: str,
    request: EnterpriseClaimLockPolicyLifecycleRequest,
) -> EnterpriseClaimLockPolicyResponse:
    try:
        policy = services.claim_lock_admin.disable_policy(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            policy_id=request.policy_id,
            expected_revision=request.expected_revision,
        )
    except EnterpriseClaimLockAdministrationError as exc:
        raise _claim_lock_admin_http_exception(exc) from exc

    return EnterpriseClaimLockPolicyResponse(
        policy=policy,
    )


@router.post(
    "/workspaces/{workspace_id}/claim-lock-policy/archive",
    response_model=EnterpriseClaimLockPolicyResponse,
)
def archive_enterprise_claim_lock_policy(
    workspace_id: str,
    request: EnterpriseClaimLockPolicyLifecycleRequest,
) -> EnterpriseClaimLockPolicyResponse:
    try:
        policy = services.claim_lock_admin.archive_policy(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            policy_id=request.policy_id,
            expected_revision=request.expected_revision,
        )
    except EnterpriseClaimLockAdministrationError as exc:
        raise _claim_lock_admin_http_exception(exc) from exc

    return EnterpriseClaimLockPolicyResponse(
        policy=policy,
    )


@router.post(
    "/workspaces/{workspace_id}/quota-limits",
    response_model=EnterpriseQuotaLimitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_enterprise_quota_limit(
    workspace_id: str,
    request: CreateEnterpriseQuotaLimitRequest,
) -> EnterpriseQuotaLimitResponse:
    quota_limit = EnterpriseWorkspaceQuotaLimit(
        quota_limit_id=request.quota_limit_id,
        workspace_id=workspace_id,
        dimension=request.dimension,
        window=request.window,
        limit=request.limit,
    )

    try:
        created = services.quota_admin.create_limit(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            quota_limit=quota_limit,
        )
    except EnterpriseQuotaAdministrationError as exc:
        raise _quota_admin_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return EnterpriseQuotaLimitResponse(
        quota_limit=created,
    )


@router.get(
    "/workspaces/{workspace_id}/quota-limits",
    response_model=EnterpriseQuotaLimitListResponse,
)
def list_enterprise_quota_limits(
    workspace_id: str,
    dimension: EnterpriseQuotaDimension,
    actor_user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
    limit: int = Query(
        default=1000,
        ge=1,
        le=10000,
    ),
) -> EnterpriseQuotaLimitListResponse:
    try:
        quota_limits = services.quota_admin.list_limits(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            dimension=dimension,
            limit=limit,
        )
    except EnterpriseQuotaAdministrationError as exc:
        raise _quota_admin_http_exception(exc) from exc

    return EnterpriseQuotaLimitListResponse(
        workspace_id=workspace_id,
        dimension=dimension,
        quota_limits=quota_limits,
    )


@router.get(
    "/workspaces/{workspace_id}/quota-limits/{quota_limit_id}",
    response_model=EnterpriseQuotaLimitResponse,
)
def get_enterprise_quota_limit(
    workspace_id: str,
    quota_limit_id: str,
    actor_user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
) -> EnterpriseQuotaLimitResponse:
    try:
        quota_limit = services.quota_admin.get_limit(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            quota_limit_id=quota_limit_id,
        )
    except EnterpriseQuotaAdministrationError as exc:
        raise _quota_admin_http_exception(exc) from exc

    return EnterpriseQuotaLimitResponse(
        quota_limit=quota_limit,
    )


@router.get(
    "/workspaces/{workspace_id}/access-context",
    response_model=EnterpriseWorkspaceAccessContextResponse,
)
def get_enterprise_workspace_access_context(
    workspace_id: str,
    user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
) -> EnterpriseWorkspaceAccessContextResponse:
    runtime = services.enterprise_authorization

    resolution = runtime.authorization_resolver.resolve(
        workspace_id=workspace_id,
        user_id=user_id,
        permission=EnterprisePermission.WORKSPACE_READ,
    )

    if (
        resolution.status
        is AuthorizationResolutionStatus.RESOLUTION_FAILED
    ):
        if (
            resolution.failure_reason
            is AuthorizationResolutionFailureReason.WORKSPACE_NOT_FOUND
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="workspace_not_found",
            )

        if (
            resolution.failure_reason
            is AuthorizationResolutionFailureReason.MEMBERSHIP_NOT_FOUND
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="membership_not_found",
            )

        raise RuntimeError(
            "unsupported enterprise authorization resolution failure"
        )

    authorization = resolution.authorization

    if authorization is None:
        raise RuntimeError(
            "resolved enterprise authorization requires a result"
        )

    if authorization.decision is not AuthorizationDecision.ALLOW:
        denial_reason = authorization.denial_reason

        if denial_reason is None:
            raise RuntimeError(
                "denied enterprise authorization requires a reason"
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=denial_reason.value,
        )

    workspace = runtime.workspaces.get(
        workspace_id
    )
    membership = runtime.memberships.get_current(
        workspace_id=workspace_id,
        user_id=user_id,
    )

    if workspace is None or membership is None:
        raise RuntimeError(
            "enterprise authorization resolved without canonical context"
        )

    permissions = tuple(
        sorted(
            permissions_for_role(membership.role),
            key=lambda permission: permission.value,
        )
    )

    return EnterpriseWorkspaceAccessContextResponse(
        workspace=workspace,
        membership=membership,
        permissions=permissions,
    )


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=EnterpriseMemberListResponse,
)
def list_enterprise_members(
    workspace_id: str,
    actor_user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
    membership_status: EnterpriseMembershipStatus | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(
        default=200,
        ge=1,
        le=1000,
    ),
) -> EnterpriseMemberListResponse:
    try:
        memberships = services.membership_admin.list_members(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            status=membership_status,
            limit=limit,
        )
    except EnterpriseMembershipAdministrationError as exc:
        raise _membership_admin_http_exception(exc) from exc

    return EnterpriseMemberListResponse(
        workspace_id=workspace_id,
        members=tuple(
            _enterprise_member_response(membership)
            for membership in memberships
        ),
    )


@router.get(
    "/workspaces/{workspace_id}/members/{user_id}",
    response_model=EnterpriseMemberResponse,
)
def get_enterprise_member(
    workspace_id: str,
    user_id: str,
    actor_user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
) -> EnterpriseMemberResponse:
    try:
        membership = services.membership_admin.get_member(
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
    except EnterpriseMembershipAdministrationError as exc:
        raise _membership_admin_http_exception(exc) from exc

    return _enterprise_member_response(membership)


@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=EnterpriseMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_enterprise_member(
    workspace_id: str,
    request: AddEnterpriseMemberRequest,
) -> EnterpriseMemberResponse:
    runtime = services.enterprise_authorization
    workspace = runtime.workspaces.get(workspace_id)

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace_not_found",
        )

    try:
        membership = services.membership_admin.add_member(
            actor_user_id=request.actor_user_id,
            organization_id=workspace.organization_id,
            workspace_id=workspace_id,
            membership_id=request.membership_id,
            user_id=request.user_id,
            role=request.role,
        )
    except EnterpriseMembershipAdministrationError as exc:
        raise _membership_admin_http_exception(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _enterprise_member_response(membership)


@router.patch(
    "/workspaces/{workspace_id}/members/{user_id}/role",
    response_model=EnterpriseMemberResponse,
)
def change_enterprise_member_role(
    workspace_id: str,
    user_id: str,
    request: ChangeEnterpriseMemberRoleRequest,
) -> EnterpriseMemberResponse:
    try:
        membership = services.membership_admin.change_role(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            target_user_id=user_id,
            role=request.role,
        )
    except EnterpriseMembershipAdministrationError as exc:
        raise _membership_admin_http_exception(exc) from exc

    return _enterprise_member_response(membership)


@router.post(
    "/workspaces/{workspace_id}/members/{user_id}/suspend",
    response_model=EnterpriseMemberResponse,
)
def suspend_enterprise_member(
    workspace_id: str,
    user_id: str,
    request: EnterpriseMemberLifecycleRequest,
) -> EnterpriseMemberResponse:
    try:
        membership = services.membership_admin.suspend_member(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            target_user_id=user_id,
        )
    except EnterpriseMembershipAdministrationError as exc:
        raise _membership_admin_http_exception(exc) from exc

    return _enterprise_member_response(membership)


@router.post(
    "/workspaces/{workspace_id}/members/{user_id}/reactivate",
    response_model=EnterpriseMemberResponse,
)
def reactivate_enterprise_member(
    workspace_id: str,
    user_id: str,
    request: EnterpriseMemberLifecycleRequest,
) -> EnterpriseMemberResponse:
    try:
        membership = services.membership_admin.reactivate_member(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            target_user_id=user_id,
        )
    except EnterpriseMembershipAdministrationError as exc:
        raise _membership_admin_http_exception(exc) from exc

    return _enterprise_member_response(membership)


@router.delete(
    "/workspaces/{workspace_id}/members/{user_id}",
    response_model=EnterpriseMemberResponse,
)
def remove_enterprise_member(
    workspace_id: str,
    user_id: str,
    request: EnterpriseMemberLifecycleRequest,
) -> EnterpriseMemberResponse:
    try:
        membership = services.membership_admin.remove_member(
            actor_user_id=request.actor_user_id,
            workspace_id=workspace_id,
            target_user_id=user_id,
        )
    except EnterpriseMembershipAdministrationError as exc:
        raise _membership_admin_http_exception(exc) from exc

    return _enterprise_member_response(membership)


@router.post(
    "/workspaces/{workspace_id}/ownership-transfer",
    response_model=EnterpriseWorkspaceOwnershipTransferResponse,
)
def transfer_enterprise_workspace_ownership(
    workspace_id: str,
    request: TransferEnterpriseWorkspaceOwnershipRequest,
) -> EnterpriseWorkspaceOwnershipTransferResponse:
    try:
        previous_owner, new_owner = (
            services.membership_admin.transfer_ownership(
                actor_user_id=request.actor_user_id,
                workspace_id=workspace_id,
                target_user_id=request.target_user_id,
            )
        )
    except EnterpriseMembershipAdministrationError as exc:
        raise _membership_admin_http_exception(exc) from exc

    return EnterpriseWorkspaceOwnershipTransferResponse(
        previous_owner=previous_owner,
        new_owner=new_owner,
    )


@router.get(
    "/workspaces/{workspace_id}/history",
    response_model=WorkspaceHistoryResponse,
    response_model_exclude_none=True,
)
def list_workspace_history(
    workspace_id: str,
    user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
) -> WorkspaceHistoryResponse:
    try:
        records = services.history.list_workspace_history(
            workspace_id=workspace_id,
            user_id=user_id,
            limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return WorkspaceHistoryResponse(
        workspace_id=workspace_id,
        records=records,
    )


@router.get(
    "/workspaces/{workspace_id}/providers",
    response_model=WorkspaceProviderCatalogVisibilityResponse,
)
def list_workspace_provider_catalog(
    workspace_id: str,
    user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
    enabled_only: bool = Query(
        default=False,
    ),
    limit: int = Query(
        default=1000,
        ge=1,
        le=1000,
    ),
) -> WorkspaceProviderCatalogVisibilityResponse:
    try:
        targets = (
            services.workspace_provider_catalog.list_targets(
                workspace_id=workspace_id,
                user_id=user_id,
                enabled_only=enabled_only,
                limit=limit,
            )
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    visible_targets = tuple(
        ProviderCatalogTargetVisibility(
            target_id=target.target_id,
            provider_id=target.provider.provider_id,
            provider_display_name=(
                target.provider.display_name
            ),
            model_id=target.model.model_id,
            capabilities=tuple(
                sorted(
                    target.capabilities.capabilities,
                    key=lambda capability: capability.value,
                )
            ),
            enabled=target.enabled,
        )
        for target in targets
    )

    return WorkspaceProviderCatalogVisibilityResponse(
        workspace_id=workspace_id,
        catalog_scope="platform",
        targets=visible_targets,
    )


def _workspace_provider_routing_execution_evidence_response(
    record: WorkspaceProviderRoutingExecutionEvidence,
) -> WorkspaceProviderRoutingExecutionEvidenceResponse:
    return WorkspaceProviderRoutingExecutionEvidenceResponse(
        operation=record.operation,
        bindings=tuple(
            WorkspaceProviderRoutingEvidenceBindingResponse(
                binding=binding_view.binding,
                routing_evidence=(
                    binding_view.routing_evidence
                ),
            )
            for binding_view in record.bindings
        ),
    )


def _workspace_provider_routing_execution_evidence_query():
    query = (
        services
        .workspace_provider_routing_execution_evidence
    )

    if query is None:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "workspace_routing_execution_"
                "evidence_integrity_error"
            ),
        )

    return query


@router.get(
    "/workspaces/{workspace_id}/routing-executions",
    response_model=(
        WorkspaceProviderRoutingExecutionEvidenceListResponse
    ),
)
def list_workspace_provider_routing_executions(
    workspace_id: str,
    user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
) -> WorkspaceProviderRoutingExecutionEvidenceListResponse:
    query = (
        _workspace_provider_routing_execution_evidence_query()
    )

    try:
        records = query.list_workspace(
            workspace_id=workspace_id,
            user_id=user_id,
            limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (
        WorkspaceProviderRoutingExecutionEvidenceIntegrityError
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "workspace_routing_execution_"
                "evidence_integrity_error"
            ),
        ) from exc

    return (
        WorkspaceProviderRoutingExecutionEvidenceListResponse(
            workspace_id=workspace_id,
            records=tuple(
                _workspace_provider_routing_execution_evidence_response(
                    record
                )
                for record in records
            ),
        )
    )


@router.get(
    "/workspaces/{workspace_id}/routing-executions/{operation_id}",
    response_model=(
        WorkspaceProviderRoutingExecutionEvidenceResponse
    ),
)
def get_workspace_provider_routing_execution(
    workspace_id: str,
    operation_id: str,
    user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
) -> WorkspaceProviderRoutingExecutionEvidenceResponse:
    query = (
        _workspace_provider_routing_execution_evidence_query()
    )

    try:
        record = query.get(
            workspace_id=workspace_id,
            user_id=user_id,
            operation_id=operation_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (
        WorkspaceProviderRoutingExecutionEvidenceIntegrityError
    ) as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "workspace_routing_execution_"
                "evidence_integrity_error"
            ),
        ) from exc

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="routing_execution_not_found",
        )

    return (
        _workspace_provider_routing_execution_evidence_response(
            record
        )
    )


@router.get(
    "/workspaces/{workspace_id}/analytics",
    response_model=WorkspaceAnalyticsSnapshot,
)
def get_workspace_analytics(
    workspace_id: str,
    period_start: datetime,
    period_end: datetime,
    user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
) -> WorkspaceAnalyticsSnapshot:
    try:
        return services.workspace_analytics.query(
            workspace_id=workspace_id,
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except WorkspaceAnalyticsQueryLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/workspaces/{workspace_id}/rewrites",
    response_model=WorkspaceRewriteResponse,
    response_model_exclude_none=True,
)
def create_workspace_rewrite(
    workspace_id: str,
    request: WorkspaceRewriteRequest,
) -> WorkspaceRewriteResponse:
    try:
        if request.multi_candidate_requested:
            candidate_count = request.candidate_count

            if candidate_count is None:
                raise RuntimeError("multi-candidate request is missing candidate_count")

            multi_result = services.multi_candidate.execute(
                workspace_id=workspace_id,
                user_id=request.user_id,
                request=request.rewrite,
                candidate_count=candidate_count,
                voice_profile_id=request.voice_profile_id,
                explicit_protected_terms=(request.protected_terms),
                claim_lock_enforcement_mode=(
                    request.claim_lock_enforcement_mode
                ),
            )

            return WorkspaceRewriteResponse(
                rewrite=multi_result.selected_response,
                history=multi_result.history,
                voice=(
                    VoiceRewriteEvidence(
                        applied=True,
                        profile_id=(multi_result.voice_guidance.profile_id),
                        guidance_version=(multi_result.voice_guidance.guidance_version),
                    )
                    if multi_result.voice_guidance is not None
                    else None
                ),
                claim_lock=(
                    ClaimLockRewriteEvidence(
                        preparation=(multi_result.claim_lock_preparation),
                        validation=(multi_result.selected_claim_lock_validation),
                        workspace_policy=(
                            multi_result.history
                            .claim_lock_workspace_policy
                        ),
                    )
                    if (
                        request.claim_lock_requested
                        or multi_result.history
                        .claim_lock_workspace_policy
                        is not None
                    )
                    else None
                ),
                multi_candidate=(
                    MultiCandidateRewriteEvidence(
                        candidate_set=(multi_result.candidate_set),
                        diffs=multi_result.diff_set,
                        controls=tuple(
                            CandidateControlRewriteEvidence(
                                candidate_id=(control.candidate_id),
                                ordinal=control.ordinal,
                                v1_release_decision=(control.v1_release_decision),
                                claim_lock_validation=(control.claim_lock_validation),
                            )
                            for control in multi_result.controls
                        ),
                        selection=(multi_result.selection),
                        audit=(multi_result.audit_snapshot),
                    )
                ),
            )

        if request.voice_profile_id is None:
            result = services.rewrite.execute(
                workspace_id=workspace_id,
                user_id=request.user_id,
                request=request.rewrite,
                explicit_protected_terms=(request.protected_terms),
                claim_lock_enforcement_mode=(
                    request.claim_lock_enforcement_mode
                ),
            )

            return WorkspaceRewriteResponse(
                rewrite=result.response,
                history=result.history,
                claim_lock=(
                    ClaimLockRewriteEvidence(
                        preparation=(result.claim_lock_preparation),
                        validation=(result.claim_lock_validation),
                        workspace_policy=(
                            result.history
                            .claim_lock_workspace_policy
                        ),
                    )
                    if (
                        request.claim_lock_requested
                        or result.history
                        .claim_lock_workspace_policy
                        is not None
                    )
                    else None
                ),
            )

        voice_rewrite = services.voice_rewrite

        if voice_rewrite is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=("Voice-aware rewrite orchestration is unavailable."),
            )

        voice_result = voice_rewrite.execute(
            workspace_id=workspace_id,
            user_id=request.user_id,
            profile_id=request.voice_profile_id,
            request=request.rewrite,
            explicit_protected_terms=(request.protected_terms),
            claim_lock_enforcement_mode=(
                    request.claim_lock_enforcement_mode
                ),
        )

        return WorkspaceRewriteResponse(
            rewrite=voice_result.response,
            history=voice_result.history,
            voice=VoiceRewriteEvidence(
                applied=True,
                profile_id=(voice_result.guidance.profile_id),
                guidance_version=(voice_result.guidance.guidance_version),
            ),
            claim_lock=(
                ClaimLockRewriteEvidence(
                    preparation=(voice_result.claim_lock_preparation),
                    validation=(voice_result.claim_lock_validation),
                    workspace_policy=(
                        voice_result.history
                        .claim_lock_workspace_policy
                    ),
                )
                if (
                    request.claim_lock_requested
                    or voice_result.history
                    .claim_lock_workspace_policy
                    is not None
                )
                else None
            ),
        )

    except EnterpriseClaimLockRuntimeIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.reason,
        ) from exc
    except EnterpriseQuotaAdmissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except (
        CandidateClaimLockViolationError,
        CandidateGenerationError,
        ClaimLockViolationError,
        NoEligibleCandidateError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except MultiCandidateVoiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (
        VoiceProfileAnalysisRequiredError,
        VoiceProfileInactiveError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/workspaces/{workspace_id}/long-document-rewrites",
    response_model=WorkspaceLongDocumentRewriteResponse,
    response_model_exclude_none=True,
)
def create_workspace_long_document_rewrite(
    workspace_id: str,
    request: WorkspaceLongDocumentRewriteRequest,
) -> WorkspaceLongDocumentRewriteResponse:
    try:
        result = services.long_document.execute(
            workspace_id=workspace_id,
            user_id=request.user_id,
            request=request.rewrite,
            explicit_protected_terms=(request.protected_terms),
            claim_lock_enforcement_mode=(
                    request.claim_lock_enforcement_mode
                ),
        )

        return WorkspaceLongDocumentRewriteResponse(
            reconstruction=result.reconstruction,
            audit=result.audit,
            claim_lock=(
                ClaimLockRewriteEvidence(
                    preparation=(result.claim_lock_preparation),
                    validation=(result.evaluation.claim_lock_validation),
                    workspace_policy=(
                        result.audit
                        .claim_lock_workspace_policy
                    ),
                )
                if (
                    request.claim_lock_requested
                    or result.audit
                    .claim_lock_workspace_policy
                    is not None
                )
                else None
            ),
        )

    except EnterpriseClaimLockRuntimeIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.reason,
        ) from exc
    except EnterpriseQuotaAdmissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except (
        ClaimLockViolationError,
        CrossSectionConsistencyViolationError,
        DocumentReconstructionIntegrityError,
        LongDocumentAuditIntegrityError,
        LongDocumentControlEvaluationError,
        SectionRewriteExecutionError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/workspaces/{workspace_id}/voice-profiles",
    response_model=VoiceProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_voice_profile(
    workspace_id: str,
    request: CreateVoiceProfileRequest,
) -> VoiceProfileResponse:
    try:
        profile = services.voice_profiles.create_profile(
            workspace_id=workspace_id,
            user_id=request.user_id,
            name=request.name,
            description=request.description,
            source_samples=(request.source_samples),
            style_attributes=(request.style_attributes),
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return VoiceProfileResponse(
        profile=profile,
    )


@router.get(
    "/workspaces/{workspace_id}/voice-profiles",
    response_model=VoiceProfileListResponse,
)
def list_voice_profiles(
    workspace_id: str,
    user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
    profile_status: VoiceProfileStatus | None = None,
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
) -> VoiceProfileListResponse:
    try:
        profiles = services.voice_profiles.list_profiles(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_status=profile_status,
            limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return VoiceProfileListResponse(
        workspace_id=workspace_id,
        profiles=profiles,
    )


@router.get(
    ("/workspaces/{workspace_id}/voice-profiles/{profile_id}"),
    response_model=VoiceProfileResponse,
)
def get_voice_profile(
    workspace_id: str,
    profile_id: str,
    user_id: str = Query(
        min_length=1,
        max_length=200,
    ),
) -> VoiceProfileResponse:
    try:
        profile = services.voice_profiles.get_profile(
            workspace_id=workspace_id,
            user_id=user_id,
            profile_id=profile_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return VoiceProfileResponse(
        profile=profile,
    )


@router.patch(
    ("/workspaces/{workspace_id}/voice-profiles/{profile_id}"),
    response_model=VoiceProfileResponse,
)
def update_voice_profile(
    workspace_id: str,
    profile_id: str,
    request: UpdateVoiceProfileRequest,
) -> VoiceProfileResponse:
    try:
        existing = services.voice_profiles.get_profile(
            workspace_id=workspace_id,
            user_id=request.user_id,
            profile_id=profile_id,
        )

        updates: dict[str, object] = {}

        if "name" in request.model_fields_set:
            updates["name"] = request.name

        if "description" in request.model_fields_set:
            updates["description"] = request.description

        if "source_samples" in request.model_fields_set:
            updates["source_samples"] = request.source_samples

        if "style_attributes" in request.model_fields_set:
            updates["style_attributes"] = request.style_attributes

        candidate = existing.model_copy(update=updates)

        profile = services.voice_profiles.update_profile(
            workspace_id=workspace_id,
            user_id=request.user_id,
            profile=candidate,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except VoiceProfileLifecycleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return VoiceProfileResponse(
        profile=profile,
    )


@router.post(
    ("/workspaces/{workspace_id}/voice-profiles/{profile_id}/archive"),
    response_model=VoiceProfileResponse,
)
def archive_voice_profile(
    workspace_id: str,
    profile_id: str,
    request: ArchiveVoiceProfileRequest,
) -> VoiceProfileResponse:
    try:
        profile = services.voice_profiles.archive_profile(
            workspace_id=workspace_id,
            user_id=request.user_id,
            profile_id=profile_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return VoiceProfileResponse(
        profile=profile,
    )


@router.post(
    ("/workspaces/{workspace_id}/voice-profiles/{profile_id}/analyze"),
    response_model=VoiceProfileAnalysisResponse,
)
def analyze_voice_profile(
    workspace_id: str,
    profile_id: str,
    request: AnalyzeVoiceProfileRequest,
) -> VoiceProfileAnalysisResponse:
    try:
        services.voice_profiles.get_profile(
            workspace_id=workspace_id,
            user_id=request.user_id,
            profile_id=profile_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    try:
        result = services.voice_profiles.analyze_profile(
            workspace_id=workspace_id,
            user_id=request.user_id,
            profile_id=profile_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except VoiceProfileLifecycleError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=(status.HTTP_422_UNPROCESSABLE_CONTENT),
            detail=str(exc),
        ) from exc

    return VoiceProfileAnalysisResponse(
        profile=result.profile,
        evidence=result.evidence,
    )

def _require_platform_evidence_access(
    authorization: str | None,
) -> None:
    try:
        require_evidence_access(
            authorization=authorization,
        )
    except EvidenceExposureDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        ) from exc
    except EvidenceAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.get(
    "/evidence/routing/{evidence_id}",
    response_model=RoutingEvidenceResponse,
)
def get_routing_evidence(
    evidence_id: str,
    authorization: str | None = Header(
        default=None,
    ),
) -> RoutingEvidenceResponse:
    _require_platform_evidence_access(
        authorization
    )

    try:
        evidence = services.routing_evidence_query.get(
            evidence_id=evidence_id,
        )
    except RoutingEvidenceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RoutingEvidenceResponse(
        evidence=evidence,
    )


@router.get(
    "/evidence/routing",
    response_model=RoutingEvidenceListResponse,
)
def list_routing_evidence(
    authorization: str | None = Header(
        default=None,
    ),
    policy_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    decision_status: RoutingDecisionStatus | None = None,
    execution_outcome: (
        RoutingEvidenceExecutionOutcome | None
    ) = None,
    executed_target_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    limit: int = Query(
        default=1000,
        ge=1,
        le=10000,
    ),
) -> RoutingEvidenceListResponse:
    _require_platform_evidence_access(
        authorization
    )

    records = services.routing_evidence_query.list_records(
        policy_id=policy_id,
        decision_status=decision_status,
        execution_outcome=execution_outcome,
        executed_target_id=executed_target_id,
        limit=limit,
    )

    return RoutingEvidenceListResponse(
        records=records,
    )


@router.get(
    "/evidence/evaluation/{evidence_id}",
    response_model=EvaluationEvidenceResponse,
)
def get_evaluation_evidence(
    evidence_id: str,
    authorization: str | None = Header(
        default=None,
    ),
) -> EvaluationEvidenceResponse:
    _require_platform_evidence_access(
        authorization
    )

    try:
        evidence = services.evaluation_evidence_query.get(
            evidence_id=evidence_id,
        )
    except EvaluationEvidenceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return EvaluationEvidenceResponse(
        evidence=evidence,
    )


@router.get(
    "/evidence/evaluation",
    response_model=EvaluationEvidenceListResponse,
)
def list_evaluation_evidence(
    authorization: str | None = Header(
        default=None,
    ),
    run_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    dataset_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    dataset_version: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    target_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    run_outcome: EvaluationRunOutcome | None = None,
    gate_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    limit: int = Query(
        default=1000,
        ge=1,
        le=10000,
    ),
) -> EvaluationEvidenceListResponse:
    _require_platform_evidence_access(
        authorization
    )

    records = (
        services.evaluation_evidence_query.list_records(
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            target_id=target_id,
            run_outcome=run_outcome,
            gate_id=gate_id,
            limit=limit,
        )
    )

    return EvaluationEvidenceListResponse(
        records=records,
    )
