from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    GENERAL = "general"
    PROFESSIONAL_EMAIL = "professional_email"
    INTERVIEW_ANSWER = "interview_answer"
    TECHNICAL_DOCUMENT = "technical_document"
    SOCIAL_POST = "social_post"


class RewriteIntensity(StrEnum):
    LIGHT_EDIT = "light_edit"
    NATURAL_REWRITE = "natural_rewrite"
    DEEP_RECONSTRUCTION = "deep_reconstruction"


class WorkflowState(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    CLAIMS_EXTRACTED = "claims_extracted"
    PATTERNS_ANALYZED = "patterns_analyzed"
    REWRITE_GENERATED = "rewrite_generated"
    OUTPUT_VERIFIED = "output_verified"
    READY_FOR_REVIEW = "ready_for_review"
    REQUIRES_REVIEW = "requires_review"
    BLOCKED = "blocked"


class ReleaseDecision(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class RewriteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    document_type: DocumentType = DocumentType.GENERAL
    audience: str = Field(default="general audience", min_length=1, max_length=200)
    tone: str = Field(default="natural and clear", min_length=1, max_length=100)
    intensity: RewriteIntensity = RewriteIntensity.NATURAL_REWRITE
    preserve_numbers: bool = True
    preserve_dates: bool = True


class TextSpan(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class ProtectedFact(BaseModel):
    fact_id: str
    value: str
    fact_type: Literal["number", "date"]
    source_span: TextSpan


class FlaggedSegment(BaseModel):
    text: str
    reason: str
    source_span: TextSpan


class PatternScores(BaseModel):
    generic_language: float = Field(ge=0.0, le=1.0)
    repetition: float = Field(ge=0.0, le=1.0)
    sentence_uniformity: float = Field(ge=0.0, le=1.0)
    transition_overuse: float = Field(ge=0.0, le=1.0)


class AnalysisResult(BaseModel):
    scores: PatternScores
    flagged_segments: list[FlaggedSegment]


class RewriteChange(BaseModel):
    change_id: str
    original: str
    replacement: str
    reason: str
    change_type: str


class VerificationResult(BaseModel):
    decision: ReleaseDecision
    preserved_facts: list[str]
    missing_facts: list[str]
    unexpected_facts: list[str]
    warnings: list[str]


class EditorialQualityDecision(StrEnum):
    PASS = "pass"
    REVIEW = "review"


class EditorialQualityResult(BaseModel):
    decision: EditorialQualityDecision
    naturalness_score: float = Field(ge=0.0, le=1.0)
    source_flag_count: int = Field(ge=0)
    remaining_flag_count: int = Field(ge=0)
    removed_flag_count: int = Field(ge=0)
    remaining_flagged_segments: list[FlaggedSegment]
    warnings: list[str]


class ProviderUsageEvidence(BaseModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ProviderExecutionEvidence(BaseModel):
    latency_ms: float = Field(ge=0.0)
    primary_provider_name: str
    actual_provider_name: str
    fallback_used: bool
    provider_error_category: str | None
    usage: ProviderUsageEvidence


class RewriteNecessitySignalEvidence(BaseModel):
    signal_type: Literal[
        "formulaic_language",
        "repetition",
        "verbosity",
        "intensity_request",
        "already_clear",
    ]
    description: str
    score: int = Field(ge=0, le=100)
    evidence: list[str]


class RewriteNecessityEvidence(BaseModel):
    decision: Literal[
        "no_change",
        "minimal_edit",
        "full_rewrite",
    ]
    score: int = Field(ge=0, le=100)
    provider_required: bool
    signals: list[RewriteNecessitySignalEvidence]
    rationale: str


class RewriteResponse(BaseModel):
    trace_id: str
    workflow_states: list[WorkflowState]
    source_text: str
    rewritten_text: str
    provider_name: str
    model_name: str
    prompt_version: str
    provider_execution: ProviderExecutionEvidence
    rewrite_necessity: RewriteNecessityEvidence
    analysis: AnalysisResult
    editorial_quality: EditorialQualityResult
    protected_facts: list[ProtectedFact]
    changes: list[RewriteChange]
    verification: VerificationResult
