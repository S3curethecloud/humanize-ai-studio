from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.domain.models import (
    ReleaseDecision,
    RewriteRequest,
    RewriteResponse,
)
from app.v2.domain.candidate_audit import (
    CandidateAuditSnapshot,
)
from app.v2.domain.candidate_ranking import (
    CandidateSelectionEvidence,
)
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
)
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.domain.long_document_audit import (
    LongDocumentAuditRecord,
)
from app.v2.domain.long_documents import (
    MAX_LONG_DOCUMENT_CHARS,
    DocumentReconstruction,
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
from app.v2.domain.rewrite_candidates import (
    RewriteCandidateDiffSet,
    RewriteCandidateSet,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceRecord,
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


class CreateEnterpriseQuotaLimitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_user_id: str = Field(
        min_length=1,
        max_length=200,
    )
    quota_limit_id: str = Field(
        min_length=1,
        max_length=200,
    )
    dimension: EnterpriseQuotaDimension
    window: EnterpriseQuotaWindow
    limit: int = Field(
        ge=0,
    )


class EnterpriseQuotaLimitResponse(BaseModel):
    quota_limit: EnterpriseWorkspaceQuotaLimit


class EnterpriseQuotaLimitListResponse(BaseModel):
    workspace_id: str
    dimension: EnterpriseQuotaDimension
    quota_limits: tuple[
        EnterpriseWorkspaceQuotaLimit,
        ...,
    ]


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
    candidate_count: int | None = Field(
        default=None,
        ge=2,
        le=5,
    )

    @property
    def multi_candidate_requested(
        self,
    ) -> bool:
        return self.candidate_count is not None

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


class CandidateControlRewriteEvidence(BaseModel):
    candidate_id: str
    ordinal: int
    v1_release_decision: ReleaseDecision
    claim_lock_validation: ClaimLockValidationResult


class MultiCandidateRewriteEvidence(BaseModel):
    candidate_set: RewriteCandidateSet
    diffs: RewriteCandidateDiffSet
    controls: tuple[
        CandidateControlRewriteEvidence,
        ...,
    ]
    selection: CandidateSelectionEvidence
    audit: CandidateAuditSnapshot


class WorkspaceRewriteResponse(BaseModel):
    rewrite: RewriteResponse
    history: RewriteHistoryRecord
    voice: VoiceRewriteEvidence | None = None
    claim_lock: ClaimLockRewriteEvidence | None = None
    multi_candidate: MultiCandidateRewriteEvidence | None = None


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


class LongDocumentRewritePayload(RewriteRequest):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        min_length=1,
        max_length=MAX_LONG_DOCUMENT_CHARS,
    )


class WorkspaceLongDocumentRewriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(
        min_length=1,
        max_length=200,
    )
    rewrite: LongDocumentRewritePayload
    protected_terms: tuple[
        ExplicitProtectedTerm,
        ...,
    ] = ()
    claim_lock_enforcement_mode: ClaimLockEnforcementMode | None = None

    @property
    def claim_lock_requested(
        self,
    ) -> bool:
        return bool(self.protected_terms) or (
            "claim_lock_enforcement_mode" in self.model_fields_set
        )


class WorkspaceLongDocumentRewriteResponse(BaseModel):
    reconstruction: DocumentReconstruction
    audit: LongDocumentAuditRecord
    claim_lock: ClaimLockRewriteEvidence | None = None

class RoutingEvidenceResponse(BaseModel):
    evidence: RoutingEvidenceRecord


class RoutingEvidenceListResponse(BaseModel):
    records: tuple[
        RoutingEvidenceRecord,
        ...,
    ]


class EvaluationEvidenceResponse(BaseModel):
    evidence: EvaluationEvidenceRecord


class EvaluationEvidenceListResponse(BaseModel):
    records: tuple[
        EvaluationEvidenceRecord,
        ...,
    ]
