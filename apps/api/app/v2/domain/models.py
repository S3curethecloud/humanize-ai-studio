from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


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


class VoiceRewriteAnalysisSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_state: Literal["current"]
    analyzer_version: str = Field(
        min_length=1,
        max_length=200,
    )
    analyzed_at: datetime
    source_sample_ids: tuple[str, ...]
    source_fingerprint: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    sample_count: int = Field(
        ge=1,
    )
    sufficiency: Literal[
        "insufficient",
        "limited",
        "strong",
    ]
    consistency: Literal[
        "not_applicable",
        "coherent",
        "mixed",
        "divergent",
    ]
    style_attributes: VoiceStyleAttributes

    @field_validator("analyzed_at")
    @classmethod
    def require_timezone_aware_analysis_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("analyzed_at must be timezone-aware")

        return value

    @model_validator(mode="after")
    def require_complete_source_provenance(
        self,
    ) -> VoiceRewriteAnalysisSnapshot:
        if len(self.source_sample_ids) != self.sample_count:
            raise ValueError("sample_count must match source_sample_ids length")

        if any(not sample_id.strip() for sample_id in self.source_sample_ids):
            raise ValueError("source_sample_ids must contain only non-empty identifiers")

        return self

    def canonical_bytes(
        self,
    ) -> bytes:
        return json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    def canonical_digest(
        self,
    ) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


class VoiceRewriteAnalysisAuthenticity(BaseModel):
    model_config = ConfigDict(frozen=True)

    algorithm: Literal["hmac-sha256"] = "hmac-sha256"
    authentication_version: Literal["voice-snapshot-authenticity-v1"] = (
        "voice-snapshot-authenticity-v1"
    )
    key_id: str = Field(
        min_length=1,
        max_length=200,
    )
    mac: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )


class VoiceRewriteAnalysisBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    algorithm: Literal["sha256"] = "sha256"
    canonicalization_version: Literal["voice-snapshot-canonical-v1"] = "voice-snapshot-canonical-v1"
    digest: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: VoiceRewriteAnalysisSnapshot,
    ) -> VoiceRewriteAnalysisBinding:
        return cls(
            digest=snapshot.canonical_digest(),
        )

    def matches(
        self,
        snapshot: VoiceRewriteAnalysisSnapshot,
    ) -> bool:
        return self.digest == snapshot.canonical_digest()


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
    voice_analysis_snapshot: VoiceRewriteAnalysisSnapshot | None = None
    voice_analysis_binding: VoiceRewriteAnalysisBinding | None = None
    voice_analysis_authenticity: VoiceRewriteAnalysisAuthenticity | None = None

    fallback_used: bool
    verification_decision: str
    editorial_quality_decision: str

    status: RewriteRecordStatus = RewriteRecordStatus.COMPLETED

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_coherent_voice_audit_tuple(
        self,
    ) -> RewriteHistoryRecord:
        voice_audit_fields = (
            self.voice_profile_id,
            self.voice_guidance_version,
            self.voice_analysis_snapshot,
            self.voice_analysis_binding,
        )

        present = tuple(value is not None for value in voice_audit_fields)

        if any(present) and not all(present):
            raise ValueError("voice audit fields must be all present or all absent")

        if self.voice_profile_id is not None and not self.voice_profile_id.strip():
            raise ValueError("voice_profile_id must be non-empty")

        if self.voice_guidance_version is not None and not self.voice_guidance_version.strip():
            raise ValueError("voice_guidance_version must be non-empty")

        if (
            self.voice_analysis_snapshot is not None
            and self.voice_analysis_binding is not None
            and not self.voice_analysis_binding.matches(self.voice_analysis_snapshot)
        ):
            raise ValueError("voice analysis binding does not match snapshot")

        return self


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


class VoiceAnalysisState(StrEnum):
    NEVER_ANALYZED = "never_analyzed"
    CURRENT = "current"
    STALE = "stale"


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

    analysis_state: VoiceAnalysisState = VoiceAnalysisState.NEVER_ANALYZED
    analysis_provenance: VoiceAnalysisProvenance | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class VoiceAnalysisSufficiency(StrEnum):
    INSUFFICIENT = "insufficient"
    LIMITED = "limited"
    STRONG = "strong"


class VoiceAnalysisConsistency(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    COHERENT = "coherent"
    MIXED = "mixed"
    DIVERGENT = "divergent"


class VoiceAnalysisProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    analyzer_version: str
    analyzed_at: datetime
    source_sample_ids: tuple[str, ...]
    source_fingerprint: str
    sample_count: int
    sufficiency: VoiceAnalysisSufficiency
    consistency: VoiceAnalysisConsistency


VoiceProfileRecord.model_rebuild()
VoiceRewriteAnalysisSnapshot.model_rebuild()


class VoiceAttributeConsistency(BaseModel):
    model_config = ConfigDict(frozen=True)

    attribute: str
    consistent: bool | None
    observed_values: tuple[str, ...]


class VoiceSampleConsistencyEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    classification: VoiceAnalysisConsistency
    agreement_ratio: float | None
    consistent_attribute_count: int
    total_attribute_count: int = 8
    divergent_attributes: tuple[str, ...]
    attributes: tuple[VoiceAttributeConsistency, ...]


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
    sufficiency: VoiceAnalysisSufficiency
    sample_consistency: VoiceSampleConsistencyEvidence
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
