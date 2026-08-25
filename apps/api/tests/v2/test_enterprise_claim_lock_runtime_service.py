from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.v2.domain.claim_lock import (
    ClaimLock,
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
)
from app.v2.domain.enterprise_claim_lock_runtime import (
    ENTERPRISE_CLAIM_LOCK_RUNTIME_VERSION,
    ENTERPRISE_CLAIM_LOCK_WORKSPACE_POLICY_EXECUTION_VERSION,
    EnterpriseClaimLockRuntimeContext,
    EnterpriseClaimLockWorkspacePolicyExecutionEvidence,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationResult,
)


def _preparation(
    *,
    claim_lock: ClaimLock | None = None,
) -> ClaimLockPreparationResult:
    return ClaimLockPreparationResult.model_construct(
        claim_extraction=None,
        protected_item_extraction=None,
        claim_lock=claim_lock,
    )


def _evidence(
    **overrides: object,
) -> EnterpriseClaimLockWorkspacePolicyExecutionEvidence:
    values: dict[str, object] = {
        "policy_id": "policy_1",
        "policy_revision": 1,
        "enforcement_mode": ClaimLockEnforcementMode.STRICT,
        "applicable_term_ids": (),
    }
    values.update(overrides)

    return EnterpriseClaimLockWorkspacePolicyExecutionEvidence(
        **values,
    )


def _lock(
    *,
    enforcement_mode: ClaimLockEnforcementMode = (
        ClaimLockEnforcementMode.STRICT
    ),
) -> ClaimLock:
    return ClaimLock(
        lock_id="lock_1",
        enforcement_mode=enforcement_mode,
        terms=(
            ProtectedTerm(
                term_id="term_request",
                text="Humanize Enterprise",
                provenance=ClaimLockProvenance(
                    origin=ClaimLockOrigin.REQUEST,
                    source_reference="rewrite-request",
                ),
            ),
        ),
    )


def _context(
    **overrides: object,
) -> EnterpriseClaimLockRuntimeContext:
    values: dict[str, object] = {
        "request_preparation": _preparation(),
        "effective_claim_lock": None,
        "workspace_policy_evidence": None,
        "request_customization_requested": False,
        "effective_enforcement_mode": (
            ClaimLockEnforcementMode.STRICT
        ),
    }
    values.update(overrides)

    return EnterpriseClaimLockRuntimeContext(
        **values,
    )


def test_runtime_contract_uses_frozen_version() -> None:
    context = _context()

    assert (
        context.runtime_version
        == ENTERPRISE_CLAIM_LOCK_RUNTIME_VERSION
    )
    assert (
        context.runtime_version
        == "enterprise-claim-lock-runtime-v1"
    )


def test_workspace_policy_evidence_uses_frozen_versions() -> None:
    evidence = _evidence()

    assert (
        evidence.evidence_version
        == ENTERPRISE_CLAIM_LOCK_WORKSPACE_POLICY_EXECUTION_VERSION
    )
    assert (
        evidence.evidence_version
        == "enterprise-claim-lock-workspace-policy-execution-v1"
    )
    assert (
        evidence.policy_version
        == "enterprise-workspace-claim-lock-policy-v1"
    )


def test_runtime_contract_is_immutable() -> None:
    context = _context()

    with pytest.raises(ValidationError):
        context.request_customization_requested = True


def test_workspace_policy_evidence_is_immutable() -> None:
    evidence = _evidence()

    with pytest.raises(ValidationError):
        evidence.policy_id = "mutated"


def test_runtime_contract_rejects_unknown_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        _context(
            unexpected="forbidden",
        )


def test_workspace_policy_evidence_rejects_unknown_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        _evidence(
            unexpected="forbidden",
        )


def test_workspace_policy_evidence_normalizes_identifiers() -> None:
    evidence = _evidence(
        policy_id="  policy_1  ",
        applicable_term_ids=(
            "  term_1  ",
            "TERM_2",
        ),
    )

    assert evidence.policy_id == "policy_1"
    assert evidence.applicable_term_ids == (
        "term_1",
        "TERM_2",
    )


def test_workspace_policy_evidence_allows_no_applicable_terms() -> None:
    evidence = _evidence(
        applicable_term_ids=(),
    )

    assert evidence.applicable_term_ids == ()


def test_workspace_policy_evidence_rejects_blank_policy_id() -> None:
    with pytest.raises(
        ValidationError,
        match="policy_id must be non-empty",
    ):
        _evidence(
            policy_id="   ",
        )


def test_workspace_policy_evidence_rejects_revision_below_one() -> None:
    with pytest.raises(
        ValidationError,
        match="greater than or equal to 1",
    ):
        _evidence(
            policy_revision=0,
        )


def test_workspace_policy_evidence_rejects_blank_term_id() -> None:
    with pytest.raises(
        ValidationError,
        match="term identifiers must be non-empty",
    ):
        _evidence(
            applicable_term_ids=("   ",),
        )


def test_workspace_policy_evidence_rejects_oversized_term_id() -> None:
    with pytest.raises(
        ValidationError,
        match="must not exceed 200 characters",
    ):
        _evidence(
            applicable_term_ids=("x" * 201,),
        )


def test_workspace_policy_evidence_rejects_duplicate_term_ids_case_insensitively() -> None:
    with pytest.raises(
        ValidationError,
        match="term identifiers must be unique",
    ):
        _evidence(
            applicable_term_ids=(
                "term_1",
                "TERM_1",
            ),
        )


def test_runtime_allows_no_effective_lock() -> None:
    context = _context()

    assert context.effective_claim_lock is None
    assert context.workspace_policy_evidence is None
    assert (
        context.effective_enforcement_mode
        is ClaimLockEnforcementMode.STRICT
    )


def test_runtime_allows_policy_evidence_without_effective_lock() -> None:
    evidence = _evidence(
        enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
    )

    context = _context(
        workspace_policy_evidence=evidence,
        effective_enforcement_mode=(
            ClaimLockEnforcementMode.AUDIT_ONLY
        ),
    )

    assert context.effective_claim_lock is None
    assert context.workspace_policy_evidence is evidence


def test_runtime_allows_mode_only_request_customization_without_lock() -> None:
    context = _context(
        request_customization_requested=True,
        effective_enforcement_mode=(
            ClaimLockEnforcementMode.AUDIT_ONLY
        ),
    )

    assert context.effective_claim_lock is None
    assert context.request_customization_requested is True


def test_runtime_accepts_effective_lock_matching_resolved_mode() -> None:
    lock = _lock()

    context = _context(
        request_preparation=_preparation(
            claim_lock=lock,
        ),
        effective_claim_lock=lock,
        request_customization_requested=True,
    )

    assert context.effective_claim_lock is lock
    assert (
        context.effective_claim_lock.enforcement_mode
        is context.effective_enforcement_mode
    )


def test_runtime_rejects_effective_lock_mode_mismatch() -> None:
    lock = _lock()

    with pytest.raises(
        ValidationError,
        match="effective lock mode must match",
    ):
        _context(
            request_preparation=_preparation(
                claim_lock=lock,
            ),
            effective_claim_lock=lock,
            request_customization_requested=True,
            effective_enforcement_mode=(
                ClaimLockEnforcementMode.AUDIT_ONLY
            ),
        )


def test_runtime_rejects_discarding_prepared_protected_items() -> None:
    lock = _lock()

    with pytest.raises(
        ValidationError,
        match="cannot discard prepared protected items",
    ):
        _context(
            request_preparation=_preparation(
                claim_lock=lock,
            ),
            effective_claim_lock=None,
            request_customization_requested=True,
        )
