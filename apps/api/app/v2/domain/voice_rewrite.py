from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.v2.domain.models import (
    VoiceRewriteAnalysisSnapshot,
    VoiceStyleAttributes,
)


class VoiceConstraintPriority(StrEnum):
    FACTUAL_PRESERVATION = "factual_preservation"
    REWRITE_REQUEST_CONSTRAINTS = "rewrite_request_constraints"
    V1_VERIFICATION = "v1_verification"
    VOICE_MATCHING = "voice_matching"


class VoiceGuidanceInstruction(BaseModel):
    model_config = ConfigDict(frozen=True)

    attribute: str
    value: str
    instruction: str


class VoiceRewriteGuardrails(BaseModel):
    model_config = ConfigDict(frozen=True)

    authority_order: tuple[
        VoiceConstraintPriority,
        ...,
    ] = (
        VoiceConstraintPriority.FACTUAL_PRESERVATION,
        VoiceConstraintPriority.REWRITE_REQUEST_CONSTRAINTS,
        VoiceConstraintPriority.V1_VERIFICATION,
        VoiceConstraintPriority.VOICE_MATCHING,
    )

    factual_preservation_required: bool = True
    rewrite_request_constraints_authoritative: bool = True
    v1_verification_authoritative: bool = True

    voice_can_add_claims: bool = False
    voice_can_remove_claims: bool = False
    voice_can_override_release_decision: bool = False

    policy_statement: str = (
        "Voice matching is stylistic only. It must not add, "
        "remove, infer, strengthen, weaken, or reinterpret "
        "factual claims. RewriteRequest preservation controls "
        "and existing V1 verification and release decisions "
        "remain authoritative."
    )


class VoiceRewriteGuidance(BaseModel):
    model_config = ConfigDict(frozen=True)

    guidance_version: str = "voice-rewrite-guidance-v1"

    profile_id: str
    workspace_id: str

    style_attributes: VoiceStyleAttributes
    analysis_snapshot: VoiceRewriteAnalysisSnapshot

    instructions: tuple[
        VoiceGuidanceInstruction,
        ...,
    ]

    guardrails: VoiceRewriteGuardrails = VoiceRewriteGuardrails()
