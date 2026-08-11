from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class RewriteRecordStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class UserRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    email: str
    display_name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkspaceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace_id: str
    name: str
    created_by_user_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkspaceMembership(BaseModel):
    model_config = ConfigDict(frozen=True)

    workspace_id: str
    user_id: str
    role: WorkspaceRole
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RewriteHistoryRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    rewrite_id: str
    workspace_id: str
    user_id: str
    trace_id: str

    source_text: str
    rewritten_text: str

    document_type: str
    audience: str
    tone: str
    intensity: str

    provider_name: str
    model_name: str
    prompt_version: str

    voice_profile_id: str | None = None
    voice_guidance_version: str | None = None

    fallback_used: bool
    verification_decision: str
    editorial_quality_decision: str

    status: RewriteRecordStatus = RewriteRecordStatus.COMPLETED

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VoiceProfileStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class VoiceFormality(StrEnum):
    CASUAL = "casual"
    BALANCED = "balanced"
    FORMAL = "formal"


class VoiceSentenceLength(StrEnum):
    SHORT = "short"
    MIXED = "mixed"
    LONG = "long"


class VoiceDirectness(StrEnum):
    DIRECT = "direct"
    BALANCED = "balanced"
    INDIRECT = "indirect"


class VoiceWarmth(StrEnum):
    RESERVED = "reserved"
    BALANCED = "balanced"
    WARM = "warm"


class VoiceConcision(StrEnum):
    CONCISE = "concise"
    BALANCED = "balanced"
    EXPANSIVE = "expansive"


class VoiceFirstPersonFrequency(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class VoiceContractionPreference(StrEnum):
    AVOID = "avoid"
    MIXED = "mixed"
    PREFER = "prefer"


class VoiceTransitionStyle(StrEnum):
    MINIMAL = "minimal"
    NATURAL = "natural"
    EXPLICIT = "explicit"


class VoiceStyleAttributes(BaseModel):
    model_config = ConfigDict(frozen=True)

    formality: VoiceFormality = VoiceFormality.BALANCED
    sentence_length: VoiceSentenceLength = VoiceSentenceLength.MIXED
    directness: VoiceDirectness = VoiceDirectness.BALANCED
    warmth: VoiceWarmth = VoiceWarmth.BALANCED
    concision: VoiceConcision = VoiceConcision.BALANCED

    first_person_frequency: VoiceFirstPersonFrequency = VoiceFirstPersonFrequency.MODERATE
    contraction_preference: VoiceContractionPreference = VoiceContractionPreference.MIXED
    transition_style: VoiceTransitionStyle = VoiceTransitionStyle.NATURAL


class VoiceSourceSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_id: str
    text: str
    label: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VoiceProfileRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str
    workspace_id: str
    created_by_user_id: str

    name: str
    description: str | None = None

    status: VoiceProfileStatus = VoiceProfileStatus.ACTIVE

    source_samples: tuple[VoiceSourceSample, ...] = ()
    style_attributes: VoiceStyleAttributes = Field(default_factory=VoiceStyleAttributes)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VoiceAnalysisSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    attribute: str
    inferred_value: str
    metric_name: str
    metric_value: float
    rationale: str


class VoiceAnalysisEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    analyzer_version: str = "voice-dna-v1"
    sample_count: int
    character_count: int
    word_count: int
    sentence_count: int
    signals: tuple[VoiceAnalysisSignal, ...]


class VoiceAnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    style_attributes: VoiceStyleAttributes
    evidence: VoiceAnalysisEvidence


class VoiceProfileAnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile: VoiceProfileRecord
    evidence: VoiceAnalysisEvidence
