from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
)
from app.v2.domain.enterprise_claim_lock_runtime import (
    EnterpriseClaimLockWorkspacePolicyExecutionEvidence,
)
from app.v2.domain.long_documents import (
    DocumentReconstruction,
    DocumentStructure,
    SectionRewritePlan,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationResult,
)

LONG_DOCUMENT_AUDIT_VERSION: Literal[
    "long-document-audit-v1"
] = "long-document-audit-v1"

LONG_DOCUMENT_AUDIT_V2_VERSION: Literal[
    "long-document-audit-v2"
] = "long-document-audit-v2"

LongDocumentAuditVersion = Literal[
    "long-document-audit-v1",
    "long-document-audit-v2",
]


class CrossSectionConsistencyAuditCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_id: str = Field(
        min_length=1,
        max_length=200,
    )
    ordinal: int = Field(ge=1)

    item_id: str = Field(
        min_length=1,
        max_length=200,
    )

    item_type: Literal[
        "term",
        "value",
    ]

    expected_text: str = Field(
        min_length=1,
        max_length=10_000,
    )

    status: Literal[
        "preserved",
        "missing",
    ]


class CrossSectionConsistencyAuditSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: Literal[
        "pass",
        "violation",
    ]

    checks: tuple[
        CrossSectionConsistencyAuditCheck,
        ...,
    ] = ()

    @model_validator(mode="after")
    def require_consistent_decision(
        self,
    ) -> CrossSectionConsistencyAuditSnapshot:
        missing = tuple(check for check in self.checks if check.status == "missing")

        if self.decision == "pass" and missing:
            raise ValueError("cross-section audit pass cannot contain missing checks")

        if self.decision == "violation" and not missing:
            raise ValueError("cross-section audit violation requires at least one missing check")

        return self


class LongDocumentAuditRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    audit_version: LongDocumentAuditVersion = (
        LONG_DOCUMENT_AUDIT_VERSION
    )

    audit_id: str = Field(
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

    structure: DocumentStructure
    plan: SectionRewritePlan

    reconstruction: DocumentReconstruction

    claim_lock_validation: ClaimLockValidationResult

    effective_claim_lock: ClaimLock | None = None
    claim_lock_workspace_policy: (
        EnterpriseClaimLockWorkspacePolicyExecutionEvidence
        | None
    ) = None

    cross_section_consistency: CrossSectionConsistencyAuditSnapshot

    v1_failed_section_ids: tuple[
        str,
        ...,
    ] = ()

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_complete_audit_linkage(
        self,
    ) -> LongDocumentAuditRecord:
        if self.plan.structure_id != self.structure.structure_id:
            raise ValueError("long-document audit plan structure ID must match structure")

        if self.reconstruction.structure != self.structure:
            raise ValueError(
                "long-document audit reconstruction structure must match audit structure"
            )

        if self.v1_failed_section_ids:
            raise ValueError(
                "completed long-document audit cannot contain authoritative V1 failures"
            )

        if len(self.plan.entries) != len(self.structure.sections):
            raise ValueError(
                "long-document audit plan must contain one entry for every structure section"
            )

        if len(self.reconstruction.section_results) != len(self.structure.sections):
            raise ValueError(
                "long-document audit reconstruction "
                "must contain one result for every "
                "structure section"
            )

        for section, entry, result in zip(
            self.structure.sections,
            self.plan.entries,
            self.reconstruction.section_results,
            strict=True,
        ):
            if entry.section_id != section.section_id:
                raise ValueError("long-document audit plan section IDs must match structure order")

            if entry.ordinal != section.ordinal:
                raise ValueError("long-document audit plan ordinals must match structure order")

            if result.section_id != section.section_id:
                raise ValueError(
                    "long-document audit result section IDs must match structure order"
                )

            if result.ordinal != section.ordinal:
                raise ValueError("long-document audit result ordinals must match structure order")

            if result.disposition is not entry.disposition:
                raise ValueError("long-document audit result disposition must match plan")

            if result.source_text != section.source_text:
                raise ValueError(
                    "long-document audit result source must match exact structure section"
                )

        if self.audit_version == LONG_DOCUMENT_AUDIT_VERSION:
            if (
                self.effective_claim_lock is not None
                or self.claim_lock_workspace_policy is not None
            ):
                raise ValueError(
                    "long-document audit v1 cannot contain "
                    "C6 Claim Lock runtime evidence"
                )

            return self

        effective_claim_lock = self.effective_claim_lock
        workspace_policy = self.claim_lock_workspace_policy

        if effective_claim_lock is None:
            if (
                self.claim_lock_validation.lock_id is not None
                or self.claim_lock_validation.enforcement_mode
                is not None
            ):
                raise ValueError(
                    "long-document audit v2 validation cannot "
                    "reference a Claim Lock when the effective "
                    "snapshot is absent"
                )

            if (
                workspace_policy is not None
                and workspace_policy.applicable_term_ids
            ):
                raise ValueError(
                    "long-document audit v2 workspace applicable "
                    "terms require an effective Claim Lock"
                )

            return self

        if (
            self.claim_lock_validation.lock_id
            != effective_claim_lock.lock_id
        ):
            raise ValueError(
                "long-document audit v2 effective Claim Lock "
                "ID must match validation"
            )

        if (
            self.claim_lock_validation.enforcement_mode
            is not effective_claim_lock.enforcement_mode
        ):
            raise ValueError(
                "long-document audit v2 effective Claim Lock "
                "mode must match validation"
            )

        workspace_terms = tuple(
            term
            for term in effective_claim_lock.terms
            if term.provenance.origin
            is ClaimLockOrigin.WORKSPACE
        )

        if workspace_policy is None:
            if workspace_terms:
                raise ValueError(
                    "long-document audit v2 workspace-origin "
                    "terms require workspace policy evidence"
                )

            return self

        expected_source_reference = (
            "workspace-claim-lock-policy:"
            f"{workspace_policy.policy_id}:"
            f"revision:{workspace_policy.policy_revision}"
        )

        if any(
            term.provenance.source_reference
            != expected_source_reference
            for term in workspace_terms
        ):
            raise ValueError(
                "long-document audit v2 workspace term "
                "provenance must match policy revision"
            )

        effective_workspace_term_ids = tuple(
            term.term_id
            for term in workspace_terms
        )

        if (
            effective_workspace_term_ids
            != workspace_policy.applicable_term_ids
        ):
            raise ValueError(
                "long-document audit v2 applicable term IDs "
                "must match effective workspace contribution"
            )

        if (
            workspace_policy.enforcement_mode
            is ClaimLockEnforcementMode.STRICT
            and effective_claim_lock.enforcement_mode
            is not ClaimLockEnforcementMode.STRICT
        ):
            raise ValueError(
                "long-document audit v2 effective enforcement "
                "cannot weaken workspace policy"
            )

        return self
