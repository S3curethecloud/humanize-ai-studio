from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
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
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationResult,
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
    voice_profile_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    protected_terms: tuple[
        ExplicitProtectedTerm,
        ...,
    ] = ()
    claim_lock_enforcement_mode: ClaimLockEnforcementMode | None = None

    @property
    def claim_lock_requested(
        self,
    ) -> bool:
        return bool(self.protected_terms) or "claim_lock_enforcement_mode" in self.model_fields_set


class VoiceRewriteEvidence(BaseModel):
    applied: bool
    profile_id: str
    guidance_version: str


class ClaimLockRewriteEvidence(BaseModel):
    preparation: ClaimLockPreparationResult
    validation: ClaimLockValidationResult


class WorkspaceRewriteResponse(BaseModel):
    rewrite: RewriteResponse
    history: RewriteHistoryRecord
    voice: VoiceRewriteEvidence | None = None
    claim_lock: ClaimLockRewriteEvidence | None = None


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

    @model_validator(mode="after")
    def reject_null_required_profile_fields(
        self,
    ) -> UpdateVoiceProfileRequest:
        protected_fields = (
            "name",
            "source_samples",
            "style_attributes",
        )

        for field_name in protected_fields:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        return self


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
