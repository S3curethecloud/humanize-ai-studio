from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
)

from app.v2.api.dependencies import services
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.models import VoiceProfileStatus
from app.v2.services.candidate_control_enforcement import (
    CandidateClaimLockViolationError,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockViolationError,
)
from app.v2.services.multi_candidate_rewrite_service import (
    MultiCandidateVoiceUnavailableError,
    NoEligibleCandidateError,
)
from app.v2.services.voice_profile_service import (
    VoiceProfileLifecycleError,
)
from app.v2.services.voice_rewrite_guidance import (
    VoiceProfileAnalysisRequiredError,
    VoiceProfileInactiveError,
)

__all__ = [
    "router",
    "services",
]


from app.v2.api.models import (
    AnalyzeVoiceProfileRequest,
    ArchiveVoiceProfileRequest,
    CandidateControlRewriteEvidence,
    ClaimLockRewriteEvidence,
    CreateUserRequest,
    CreateUserResponse,
    CreateVoiceProfileRequest,
    CreateWorkspaceRequest,
    CreateWorkspaceResponse,
    MultiCandidateRewriteEvidence,
    UpdateVoiceProfileRequest,
    VoiceProfileAnalysisResponse,
    VoiceProfileListResponse,
    VoiceProfileResponse,
    VoiceRewriteEvidence,
    WorkspaceHistoryResponse,
    WorkspaceRewriteRequest,
    WorkspaceRewriteResponse,
)

router = APIRouter(
    prefix="/api/v2",
    tags=["v2"],
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
        workspace = services.workspace.create_workspace(
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
        claim_lock_enforcement_mode = (
            request.claim_lock_enforcement_mode or ClaimLockEnforcementMode.STRICT
        )

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
                claim_lock_enforcement_mode=(claim_lock_enforcement_mode),
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
                    )
                    if request.claim_lock_requested
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
                claim_lock_enforcement_mode=(claim_lock_enforcement_mode),
            )

            return WorkspaceRewriteResponse(
                rewrite=result.response,
                history=result.history,
                claim_lock=(
                    ClaimLockRewriteEvidence(
                        preparation=(result.claim_lock_preparation),
                        validation=(result.claim_lock_validation),
                    )
                    if request.claim_lock_requested
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
            claim_lock_enforcement_mode=(claim_lock_enforcement_mode),
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
                )
                if request.claim_lock_requested
                else None
            ),
        )

    except (
        CandidateClaimLockViolationError,
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
