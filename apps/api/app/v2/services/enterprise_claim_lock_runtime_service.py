from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ProtectedClaim,
    ProtectedTerm,
    ProtectedValue,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)
from app.v2.domain.enterprise_claim_lock_runtime import (
    ENTERPRISE_CLAIM_LOCK_RUNTIME_VERSION,
    EnterpriseClaimLockRuntimeContext,
    EnterpriseClaimLockWorkspacePolicyExecutionEvidence,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.repositories.enterprise_claim_lock_policies import (
    EnterpriseWorkspaceClaimLockPolicyRepository,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
    ClaimLockPreparationService,
)
from app.v2.services.workspace_authorization_gate import (
    WorkspaceAuthorizationGate,
)


EnterpriseClaimLockRuntimeIntegrityReason = Literal[
    "claim_lock_policy_resolution_failed",
    "claim_lock_composition_conflict",
]


class EnterpriseClaimLockRuntimeIntegrityError(RuntimeError):
    def __init__(
        self,
        reason: EnterpriseClaimLockRuntimeIntegrityReason,
    ) -> None:
        self.reason = reason
        super().__init__(reason)


class EnterpriseClaimLockRuntimeService:
    def __init__(
        self,
        *,
        policies: EnterpriseWorkspaceClaimLockPolicyRepository,
        authorization_gate: WorkspaceAuthorizationGate,
        preparation_service: ClaimLockPreparationService,
    ) -> None:
        self._policies = policies
        self._authorization_gate = authorization_gate
        self._preparation_service = preparation_service

    def resolve(
        self,
        *,
        workspace_id: str,
        user_id: str,
        text: str,
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ] = (),
        claim_lock_enforcement_mode: (
            ClaimLockEnforcementMode | None
        ) = None,
        source_reference: str | None = "rewrite-request",
    ) -> EnterpriseClaimLockRuntimeContext:
        policy = self._resolve_workspace_policy(
            workspace_id=workspace_id,
        )

        request_customization_requested = bool(
            explicit_protected_terms
        ) or claim_lock_enforcement_mode is not None

        if request_customization_requested:
            self._authorization_gate.require(
                workspace_id=workspace_id,
                user_id=user_id,
                permission=EnterprisePermission.CLAIM_LOCK_USE,
            )

        preparation_mode = (
            claim_lock_enforcement_mode
            or ClaimLockEnforcementMode.STRICT
        )

        request_preparation = self._preparation_service.prepare(
            text=text,
            explicit_terms=explicit_protected_terms,
            enforcement_mode=preparation_mode,
            source_reference=source_reference,
        )

        active_policy = (
            policy
            if (
                policy is not None
                and policy.status
                is EnterpriseClaimLockPolicyStatus.ACTIVE
            )
            else None
        )

        applicable_workspace_terms = (
            self._applicable_workspace_terms(
                text=text,
                policy=active_policy,
            )
            if active_policy is not None
            else ()
        )

        request_contribution = self._request_mode_contribution(
            explicit_protected_terms=explicit_protected_terms,
            claim_lock_enforcement_mode=(
                claim_lock_enforcement_mode
            ),
        )

        effective_mode = self._effective_mode(
            active_policy=active_policy,
            request_contribution=request_contribution,
        )

        workspace_policy_evidence = (
            EnterpriseClaimLockWorkspacePolicyExecutionEvidence(
                policy_version=active_policy.policy_version,
                policy_id=active_policy.policy_id,
                policy_revision=active_policy.revision,
                enforcement_mode=active_policy.enforcement_mode,
                applicable_term_ids=tuple(
                    term.term_id
                    for term in applicable_workspace_terms
                ),
            )
            if active_policy is not None
            else None
        )

        effective_claim_lock = self._compose_effective_lock(
            request_preparation=request_preparation,
            applicable_workspace_terms=(
                applicable_workspace_terms
            ),
            effective_mode=effective_mode,
        )

        return EnterpriseClaimLockRuntimeContext(
            request_preparation=request_preparation,
            effective_claim_lock=effective_claim_lock,
            workspace_policy_evidence=workspace_policy_evidence,
            request_customization_requested=(
                request_customization_requested
            ),
            effective_enforcement_mode=effective_mode,
        )

    def _resolve_workspace_policy(
        self,
        *,
        workspace_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None:
        try:
            policy = self._policies.get_for_workspace(
                workspace_id,
            )
        except Exception as exc:
            raise EnterpriseClaimLockRuntimeIntegrityError(
                "claim_lock_policy_resolution_failed"
            ) from exc

        if policy is None:
            return None

        if policy.workspace_id != workspace_id:
            raise EnterpriseClaimLockRuntimeIntegrityError(
                "claim_lock_policy_resolution_failed"
            )

        if (
            policy.status
            is EnterpriseClaimLockPolicyStatus.ARCHIVED
        ):
            raise EnterpriseClaimLockRuntimeIntegrityError(
                "claim_lock_policy_resolution_failed"
            )

        return policy

    @staticmethod
    def _request_mode_contribution(
        *,
        explicit_protected_terms: tuple[
            ExplicitProtectedTerm,
            ...,
        ],
        claim_lock_enforcement_mode: (
            ClaimLockEnforcementMode | None
        ),
    ) -> ClaimLockEnforcementMode | None:
        if claim_lock_enforcement_mode is not None:
            return claim_lock_enforcement_mode

        if explicit_protected_terms:
            return ClaimLockEnforcementMode.STRICT

        return None

    @staticmethod
    def _effective_mode(
        *,
        active_policy: (
            EnterpriseWorkspaceClaimLockPolicy | None
        ),
        request_contribution: (
            ClaimLockEnforcementMode | None
        ),
    ) -> ClaimLockEnforcementMode:
        if active_policy is None:
            return (
                request_contribution
                or ClaimLockEnforcementMode.STRICT
            )

        if (
            active_policy.enforcement_mode
            is ClaimLockEnforcementMode.STRICT
            or request_contribution
            is ClaimLockEnforcementMode.STRICT
        ):
            return ClaimLockEnforcementMode.STRICT

        return ClaimLockEnforcementMode.AUDIT_ONLY

    @staticmethod
    def _applicable_workspace_terms(
        *,
        text: str,
        policy: EnterpriseWorkspaceClaimLockPolicy,
    ) -> tuple[
        ProtectedTerm,
        ...,
    ]:
        return tuple(
            term
            for term in policy.protected_terms
            if _workspace_term_is_applicable(
                text=text,
                term=term,
            )
        )

    @staticmethod
    def _compose_effective_lock(
        *,
        request_preparation: ClaimLockPreparationResult,
        applicable_workspace_terms: tuple[
            ProtectedTerm,
            ...,
        ],
        effective_mode: ClaimLockEnforcementMode,
    ) -> ClaimLock | None:
        prepared_lock = request_preparation.claim_lock

        claims = (
            prepared_lock.claims
            if prepared_lock is not None
            else ()
        )
        request_terms = (
            prepared_lock.terms
            if prepared_lock is not None
            else ()
        )
        values = (
            prepared_lock.values
            if prepared_lock is not None
            else ()
        )

        workspace_semantic_keys = {
            term.semantic_key()
            for term in applicable_workspace_terms
        }

        surviving_request_terms = tuple(
            term
            for term in request_terms
            if term.semantic_key()
            not in workspace_semantic_keys
        )

        effective_terms = (
            applicable_workspace_terms
            + surviving_request_terms
        )

        if not (claims or effective_terms or values):
            return None

        if (
            prepared_lock is not None
            and effective_terms == prepared_lock.terms
            and effective_mode
            is prepared_lock.enforcement_mode
        ):
            return prepared_lock

        _require_global_identifier_integrity(
            claims=claims,
            terms=effective_terms,
            values=values,
        )

        lock_id = _stable_effective_lock_id(
            enforcement_mode=effective_mode,
            claims=claims,
            terms=effective_terms,
            values=values,
        )

        try:
            if prepared_lock is not None:
                return ClaimLock(
                    lock_id=lock_id,
                    enforcement_mode=effective_mode,
                    claims=claims,
                    terms=effective_terms,
                    values=values,
                    created_at=prepared_lock.created_at,
                )

            return ClaimLock(
                lock_id=lock_id,
                enforcement_mode=effective_mode,
                claims=claims,
                terms=effective_terms,
                values=values,
            )
        except ValueError as exc:
            raise EnterpriseClaimLockRuntimeIntegrityError(
                "claim_lock_composition_conflict"
            ) from exc


def _workspace_term_is_applicable(
    *,
    text: str,
    term: ProtectedTerm,
) -> bool:
    parts = term.text.split()
    pattern = r"\s+".join(
        re.escape(part)
        for part in parts
    )
    flags = 0 if term.case_sensitive else re.IGNORECASE

    return re.search(
        pattern,
        text,
        flags=flags,
    ) is not None


def _require_global_identifier_integrity(
    *,
    claims: tuple[ProtectedClaim, ...],
    terms: tuple[ProtectedTerm, ...],
    values: tuple[ProtectedValue, ...],
) -> None:
    identifiers = (
        tuple(claim.claim_id for claim in claims)
        + tuple(term.term_id for term in terms)
        + tuple(value.value_id for value in values)
    )

    normalized = tuple(
        identifier.casefold()
        for identifier in identifiers
    )

    if len(set(normalized)) != len(normalized):
        raise EnterpriseClaimLockRuntimeIntegrityError(
            "claim_lock_composition_conflict"
        )


def _stable_effective_lock_id(
    *,
    enforcement_mode: ClaimLockEnforcementMode,
    claims: tuple[ProtectedClaim, ...],
    terms: tuple[ProtectedTerm, ...],
    values: tuple[ProtectedValue, ...],
) -> str:
    canonical_payload = {
        "runtime_version": (
            ENTERPRISE_CLAIM_LOCK_RUNTIME_VERSION
        ),
        "enforcement_mode": enforcement_mode.value,
        "claims": [
            claim.model_dump(mode="json")
            for claim in claims
        ],
        "terms": [
            term.model_dump(mode="json")
            for term in terms
        ],
        "values": [
            value.model_dump(mode="json")
            for value in values
        ],
    }

    canonical_bytes = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    digest = hashlib.sha256(
        canonical_bytes
    ).hexdigest()[:20]

    return f"lock_{digest}"
