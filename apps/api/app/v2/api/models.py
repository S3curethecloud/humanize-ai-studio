from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
    UserRecord,
    VoiceAnalysisEvidence,
    VoiceProfileRecord,
    VoiceSourceSample,
    VoiceStyleAttributes,
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


class CreateVoiceProfileRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        max_length=200,
    )
    name: str = Field(
        min_length=1,
        max_length=200,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )
    source_samples: tuple[
        VoiceSourceSample,
        ...,
    ] = ()
    style_attributes: VoiceStyleAttributes | None = None


class VoiceProfileResponse(BaseModel):
    profile: VoiceProfileRecord


class VoiceProfileListResponse(BaseModel):
    workspace_id: str
    profiles: tuple[
        VoiceProfileRecord,
        ...,
    ]


class UpdateVoiceProfileRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        max_length=200,
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )
    source_samples: (
        tuple[
            VoiceSourceSample,
            ...,
        ]
        | None
    ) = None
    style_attributes: VoiceStyleAttributes | None = None


class ArchiveVoiceProfileRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        max_length=200,
    )


class AnalyzeVoiceProfileRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        max_length=200,
    )


class VoiceProfileAnalysisResponse(BaseModel):
    profile: VoiceProfileRecord
    evidence: VoiceAnalysisEvidence
