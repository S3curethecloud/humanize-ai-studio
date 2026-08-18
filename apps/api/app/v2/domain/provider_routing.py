from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

PROVIDER_ROUTING_VERSION: Literal["provider-routing-v1"] = (
    "provider-routing-v1"
)


class ProviderCapability(StrEnum):
    REWRITE = "rewrite"
    MULTI_CANDIDATE = "multi_candidate"
    LONG_DOCUMENT = "long_document"
    CLAIM_LOCK = "claim_lock"
    VOICE_PROFILE = "voice_profile"


class RoutingFailureCategory(StrEnum):
    CONFIGURATION = "configuration"
    TRANSPORT = "transport"
    RESPONSE = "response"
    PROVIDER = "provider"


class RoutingCandidateIneligibilityReason(StrEnum):
    TARGET_DISABLED = "target_disabled"
    MISSING_CAPABILITY = "missing_capability"
    EXCLUDED_BY_REQUIREMENT = "excluded_by_requirement"


class RoutingDecisionStatus(StrEnum):
    SELECTED = "selected"
    NO_ELIGIBLE_TARGET = "no_eligible_target"


class RoutingDecisionReason(StrEnum):
    PRIMARY_SELECTED = "primary_selected"
    FALLBACK_SELECTED = "fallback_selected"
    NO_ELIGIBLE_TARGET = "no_eligible_target"


class ProviderIdentity(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    provider_id: str = Field(
        min_length=1,
        max_length=200,
    )
    display_name: str = Field(
        min_length=1,
        max_length=200,
    )


class ModelIdentity(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    provider_id: str = Field(
        min_length=1,
        max_length=200,
    )
    model_id: str = Field(
        min_length=1,
        max_length=300,
    )


class ProviderModelCapabilities(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    capabilities: frozenset[ProviderCapability] = Field(
        min_length=1,
    )


class ProviderModelTarget(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    routing_version: Literal["provider-routing-v1"] = (
        PROVIDER_ROUTING_VERSION
    )

    target_id: str = Field(
        min_length=1,
        max_length=200,
    )
    provider: ProviderIdentity
    model: ModelIdentity
    capabilities: ProviderModelCapabilities
    enabled: bool = True

    @model_validator(mode="after")
    def require_identity_integrity(
        self,
    ) -> ProviderModelTarget:
        if self.provider.provider_id != self.model.provider_id:
            raise ValueError(
                "provider model target provider identities must match"
            )

        return self


class FallbackPolicy(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    enabled: bool = False
    failure_categories: tuple[
        RoutingFailureCategory,
        ...,
    ] = ()

    @model_validator(mode="after")
    def require_fallback_integrity(
        self,
    ) -> FallbackPolicy:
        if len(set(self.failure_categories)) != len(
            self.failure_categories
        ):
            raise ValueError(
                "fallback failure categories must be unique"
            )

        if self.enabled and not self.failure_categories:
            raise ValueError(
                "enabled fallback policy requires failure categories"
            )

        if not self.enabled and self.failure_categories:
            raise ValueError(
                "disabled fallback policy cannot contain "
                "failure categories"
            )

        return self


class RoutingRequirement(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    required_capabilities: frozenset[
        ProviderCapability
    ] = frozenset()

    excluded_target_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_requirement_integrity(
        self,
    ) -> RoutingRequirement:
        if any(not target_id for target_id in self.excluded_target_ids):
            raise ValueError(
                "excluded target IDs must be non-empty"
            )

        if len(set(self.excluded_target_ids)) != len(
            self.excluded_target_ids
        ):
            raise ValueError(
                "excluded target IDs must be unique"
            )

        return self


class RoutingPolicy(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    routing_version: Literal["provider-routing-v1"] = (
        PROVIDER_ROUTING_VERSION
    )

    policy_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordered_target_ids: tuple[str, ...] = Field(
        min_length=1,
    )
    fallback_policy: FallbackPolicy = Field(
        default_factory=FallbackPolicy,
    )

    @model_validator(mode="after")
    def require_policy_integrity(
        self,
    ) -> RoutingPolicy:
        if any(not target_id for target_id in self.ordered_target_ids):
            raise ValueError(
                "routing policy target IDs must be non-empty"
            )

        if len(set(self.ordered_target_ids)) != len(
            self.ordered_target_ids
        ):
            raise ValueError(
                "routing policy target IDs must be unique"
            )

        if (
            len(self.ordered_target_ids) > 1
            and not self.fallback_policy.enabled
        ):
            raise ValueError(
                "multi-target routing policy requires "
                "fallback to be enabled"
            )

        return self


class RoutingCandidate(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    target_id: str = Field(
        min_length=1,
        max_length=200,
    )
    eligible: bool
    ineligibility_reasons: tuple[
        RoutingCandidateIneligibilityReason,
        ...,
    ] = ()

    @model_validator(mode="after")
    def require_candidate_integrity(
        self,
    ) -> RoutingCandidate:
        if len(set(self.ineligibility_reasons)) != len(
            self.ineligibility_reasons
        ):
            raise ValueError(
                "routing candidate ineligibility reasons must be unique"
            )

        if self.eligible and self.ineligibility_reasons:
            raise ValueError(
                "eligible routing candidate cannot have "
                "ineligibility reasons"
            )

        if not self.eligible and not self.ineligibility_reasons:
            raise ValueError(
                "ineligible routing candidate requires "
                "at least one reason"
            )

        return self


class RoutingDecision(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    routing_version: Literal["provider-routing-v1"] = (
        PROVIDER_ROUTING_VERSION
    )

    policy_id: str = Field(
        min_length=1,
        max_length=200,
    )
    status: RoutingDecisionStatus
    reason: RoutingDecisionReason
    selected_target_id: str | None = Field(
        default=None,
        max_length=200,
    )
    candidates: tuple[RoutingCandidate, ...] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def require_decision_integrity(
        self,
    ) -> RoutingDecision:
        candidate_ids = tuple(
            candidate.target_id
            for candidate in self.candidates
        )

        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError(
                "routing decision candidate IDs must be unique"
            )

        eligible_candidates = tuple(
            candidate
            for candidate in self.candidates
            if candidate.eligible
        )

        if self.status is RoutingDecisionStatus.SELECTED:
            if self.selected_target_id is None:
                raise ValueError(
                    "selected routing decision requires "
                    "selected_target_id"
                )

            if not eligible_candidates:
                raise ValueError(
                    "selected routing decision requires "
                    "an eligible candidate"
                )

            first_eligible = eligible_candidates[0]

            if self.selected_target_id != first_eligible.target_id:
                raise ValueError(
                    "selected target must be the first "
                    "eligible routing candidate"
                )

            selected_index = candidate_ids.index(
                self.selected_target_id
            )

            expected_reason = (
                RoutingDecisionReason.PRIMARY_SELECTED
                if selected_index == 0
                else RoutingDecisionReason.FALLBACK_SELECTED
            )

            if self.reason is not expected_reason:
                raise ValueError(
                    "routing decision reason does not match "
                    "selected target position"
                )

        else:
            if self.selected_target_id is not None:
                raise ValueError(
                    "no-eligible-target decision cannot contain "
                    "selected_target_id"
                )

            if eligible_candidates:
                raise ValueError(
                    "no-eligible-target decision cannot contain "
                    "eligible candidates"
                )

            if (
                self.reason
                is not RoutingDecisionReason.NO_ELIGIBLE_TARGET
            ):
                raise ValueError(
                    "no-eligible-target decision requires "
                    "no_eligible_target reason"
                )

        return self
