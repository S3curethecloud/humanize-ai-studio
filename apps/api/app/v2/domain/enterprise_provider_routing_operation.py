from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.v2.domain.enterprise_provider_routing_policy import (
    ENTERPRISE_WORKSPACE_PROVIDER_ROUTING_POLICY_VERSION,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
)


ENTERPRISE_WORKSPACE_PROVIDER_ROUTING_OPERATION_VERSION: Literal[
    "enterprise-workspace-provider-routing-operation-v1"
] = "enterprise-workspace-provider-routing-operation-v1"

ENTERPRISE_PROVIDER_ROUTING_EVIDENCE_BINDING_VERSION: Literal[
    "enterprise-provider-routing-evidence-binding-v1"
] = "enterprise-provider-routing-evidence-binding-v1"


class EnterpriseProviderRoutingOperationKind(StrEnum):
    SINGLE_REWRITE = "single_rewrite"
    MULTI_CANDIDATE_REWRITE = "multi_candidate_rewrite"
    LONG_DOCUMENT_REWRITE = "long_document_rewrite"


class EnterpriseProviderRoutingOperationStatus(StrEnum):
    OPEN = "open"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    NO_PROVIDER_EXECUTION = "no_provider_execution"


class EnterpriseProviderRoutingEvidenceBindingStatus(StrEnum):
    RESERVED = "reserved"
    RECORDED = "recorded"


class EnterpriseProviderRoutingEvidenceBinding(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    binding_version: Literal[
        "enterprise-provider-routing-evidence-binding-v1"
    ] = ENTERPRISE_PROVIDER_ROUTING_EVIDENCE_BINDING_VERSION

    ordinal: int = Field(
        ge=1,
    )

    evidence_id: str = Field(
        min_length=1,
        max_length=200,
    )

    status: EnterpriseProviderRoutingEvidenceBindingStatus

    @field_validator(
        "evidence_id",
        mode="before",
    )
    @classmethod
    def normalize_evidence_id(
        cls,
        value: object,
    ) -> object:
        if not isinstance(
            value,
            str,
        ):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "enterprise provider routing evidence "
                "binding evidence_id must be non-empty"
            )

        return normalized


class EnterpriseWorkspaceProviderRoutingOperation(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    operation_version: Literal[
        "enterprise-workspace-provider-routing-operation-v1"
    ] = ENTERPRISE_WORKSPACE_PROVIDER_ROUTING_OPERATION_VERSION

    policy_version: Literal[
        "enterprise-workspace-provider-routing-policy-v1"
    ] = ENTERPRISE_WORKSPACE_PROVIDER_ROUTING_POLICY_VERSION

    operation_id: str = Field(
        min_length=1,
        max_length=200,
    )
    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )
    user_id: str = Field(
        min_length=1,
        max_length=200,
    )

    operation_kind: EnterpriseProviderRoutingOperationKind

    policy_id: str = Field(
        min_length=1,
        max_length=200,
    )
    policy_revision: int = Field(
        ge=1,
    )

    required_capabilities: frozenset[
        ProviderCapability
    ] = Field(
        min_length=1,
    )

    routing_evidence_bindings: tuple[
        EnterpriseProviderRoutingEvidenceBinding,
        ...,
    ] = ()

    status: EnterpriseProviderRoutingOperationStatus = (
        EnterpriseProviderRoutingOperationStatus.OPEN
    )

    rewrite_history_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    long_document_audit_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    failure_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    created_at: datetime
    updated_at: datetime

    revision: int = Field(
        ge=1,
    )

    @field_validator(
        "operation_id",
        "workspace_id",
        "user_id",
        "policy_id",
        mode="before",
    )
    @classmethod
    def normalize_required_identifier(
        cls,
        value: object,
    ) -> object:
        if not isinstance(
            value,
            str,
        ):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "enterprise provider routing operation "
                "identifiers must be non-empty"
            )

        return normalized

    @field_validator(
        "rewrite_history_id",
        "long_document_audit_id",
        "failure_code",
        mode="before",
    )
    @classmethod
    def normalize_optional_identifier(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return None

        if not isinstance(
            value,
            str,
        ):
            return value

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "enterprise provider routing optional "
                "identifiers must be non-empty when present"
            )

        return normalized

    @model_validator(mode="after")
    def require_timestamp_integrity(
        self,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        for field_name, value in (
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            if (
                value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(
                    "enterprise provider routing operation "
                    f"{field_name} must be timezone-aware"
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "enterprise provider routing operation "
                "updated_at must not precede created_at"
            )

        return self

    @model_validator(mode="after")
    def require_capability_integrity(
        self,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        capabilities = self.required_capabilities

        if (
            ProviderCapability.REWRITE
            not in capabilities
        ):
            raise ValueError(
                "enterprise provider routing operation "
                "requires rewrite capability"
            )

        if (
            self.operation_kind
            is EnterpriseProviderRoutingOperationKind.SINGLE_REWRITE
        ):
            forbidden = {
                ProviderCapability.MULTI_CANDIDATE,
                ProviderCapability.LONG_DOCUMENT,
            }

            if capabilities & forbidden:
                raise ValueError(
                    "single rewrite routing operation cannot "
                    "require multi-candidate or long-document "
                    "capabilities"
                )

            return self

        if (
            self.operation_kind
            is EnterpriseProviderRoutingOperationKind.MULTI_CANDIDATE_REWRITE
        ):
            if (
                ProviderCapability.MULTI_CANDIDATE
                not in capabilities
            ):
                raise ValueError(
                    "multi-candidate routing operation requires "
                    "multi_candidate capability"
                )

            if (
                ProviderCapability.LONG_DOCUMENT
                in capabilities
            ):
                raise ValueError(
                    "multi-candidate routing operation cannot "
                    "require long_document capability"
                )

            return self

        if (
            ProviderCapability.LONG_DOCUMENT
            not in capabilities
        ):
            raise ValueError(
                "long-document routing operation requires "
                "long_document capability"
            )

        if (
            ProviderCapability.MULTI_CANDIDATE
            in capabilities
        ):
            raise ValueError(
                "long-document routing operation cannot "
                "require multi_candidate capability"
            )

        return self

    @model_validator(mode="after")
    def require_binding_integrity(
        self,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        bindings = self.routing_evidence_bindings

        expected_ordinals = tuple(
            range(
                1,
                len(bindings) + 1,
            )
        )

        actual_ordinals = tuple(
            binding.ordinal
            for binding in bindings
        )

        if actual_ordinals != expected_ordinals:
            raise ValueError(
                "enterprise provider routing evidence "
                "binding ordinals must be contiguous "
                "and ordered"
            )

        evidence_ids = tuple(
            binding.evidence_id
            for binding in bindings
        )

        if (
            len(set(evidence_ids))
            != len(evidence_ids)
        ):
            raise ValueError(
                "enterprise provider routing evidence "
                "binding IDs must be unique"
            )

        return self

    @model_validator(mode="after")
    def require_status_integrity(
        self,
    ) -> EnterpriseWorkspaceProviderRoutingOperation:
        if (
            self.status
            is EnterpriseProviderRoutingOperationStatus.OPEN
        ):
            if (
                self.rewrite_history_id is not None
                or self.long_document_audit_id is not None
                or self.failure_code is not None
            ):
                raise ValueError(
                    "open enterprise routing operation cannot "
                    "contain terminal linkage"
                )

            return self

        if (
            self.status
            is EnterpriseProviderRoutingOperationStatus.FAILED
        ):
            if self.failure_code is None:
                raise ValueError(
                    "failed enterprise routing operation "
                    "requires failure_code"
                )

            if (
                self.rewrite_history_id is not None
                or self.long_document_audit_id is not None
            ):
                raise ValueError(
                    "failed enterprise routing operation "
                    "cannot contain success artifact linkage"
                )

            return self

        if self.failure_code is not None:
            raise ValueError(
                "successful enterprise routing operation "
                "cannot contain failure_code"
            )

        self._require_success_artifact_linkage()

        if (
            self.status
            is EnterpriseProviderRoutingOperationStatus.NO_PROVIDER_EXECUTION
        ):
            if self.routing_evidence_bindings:
                raise ValueError(
                    "no-provider-execution routing operation "
                    "cannot contain routing evidence bindings"
                )

            return self

        if not self.routing_evidence_bindings:
            raise ValueError(
                "successful routed operation requires "
                "at least one routing evidence binding"
            )

        if any(
            binding.status
            is not EnterpriseProviderRoutingEvidenceBindingStatus.RECORDED
            for binding in self.routing_evidence_bindings
        ):
            raise ValueError(
                "successful routed operation requires "
                "recorded routing evidence bindings"
            )

        return self

    def _require_success_artifact_linkage(
        self,
    ) -> None:
        if (
            self.operation_kind
            is EnterpriseProviderRoutingOperationKind.LONG_DOCUMENT_REWRITE
        ):
            if self.long_document_audit_id is None:
                raise ValueError(
                    "successful long-document routing operation "
                    "requires long_document_audit_id"
                )

            if self.rewrite_history_id is not None:
                raise ValueError(
                    "long-document routing operation cannot "
                    "contain rewrite_history_id"
                )

            return

        if self.rewrite_history_id is None:
            raise ValueError(
                "successful rewrite routing operation "
                "requires rewrite_history_id"
            )

        if self.long_document_audit_id is not None:
            raise ValueError(
                "rewrite routing operation cannot contain "
                "long_document_audit_id"
            )
