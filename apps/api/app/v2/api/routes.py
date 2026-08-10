from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
)

from app.v2.api.dependencies import services

__all__ = [
    "router",
    "services",
]


from app.v2.api.models import (
    CreateUserRequest,
    CreateUserResponse,
    CreateWorkspaceRequest,
    CreateWorkspaceResponse,
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
)
def create_workspace_rewrite(
    workspace_id: str,
    request: WorkspaceRewriteRequest,
) -> WorkspaceRewriteResponse:
    try:
        result = services.rewrite.execute(
            workspace_id=workspace_id,
            user_id=request.user_id,
            request=request.rewrite,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return WorkspaceRewriteResponse(
        rewrite=result.response,
        history=result.history,
    )
