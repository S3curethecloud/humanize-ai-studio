from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    WorkspaceRecord,
)


class CreateUserRequest(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=320,
    )
    display_name: str = Field(
        min_length=1,
        max_length=200,
    )


class CreateWorkspaceRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        max_length=200,
    )
    name: str = Field(
        min_length=1,
        max_length=200,
    )


class WorkspaceHistoryResponse(BaseModel):
    workspace_id: str
    records: tuple[
        RewriteHistoryRecord,
        ...,
    ]


class CreateUserResponse(BaseModel):
    user: UserRecord


class CreateWorkspaceResponse(BaseModel):
    workspace: WorkspaceRecord


class WorkspaceRewriteRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        max_length=200,
    )
    rewrite: RewriteRequest


class WorkspaceRewriteResponse(BaseModel):
    rewrite: RewriteResponse
    history: RewriteHistoryRecord
