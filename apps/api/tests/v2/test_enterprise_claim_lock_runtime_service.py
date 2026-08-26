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

from datetime import UTC, datetime

from app.v2.domain.claim_lock import (
    ProtectedClaim,
    ProtectedValue,
    ProtectedValueKind,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.services.claim_lock_extractor import (
    ExplicitProtectedTerm,
)
from app.v2.services.claim_lock_preparation import (
    ClaimLockPreparationService,
)
from app.v2.services.enterprise_claim_lock_runtime_service import (
    EnterpriseClaimLockRuntimeIntegrityError,
    EnterpriseClaimLockRuntimeService,
)


_RUNTIME_TEST_NOW = datetime(2026, 1, 1, tzinfo=UTC)


class _RuntimePolicyRepository:
    def __init__(
        self,
        policy: EnterpriseWorkspaceClaimLockPolicy | None = None,
        *,
        error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.policy = policy
        self.error = error
        self.events = events
        self.lookups: list[str] = []

    def get_for_workspace(
        self,
        workspace_id: str,
    ) -> EnterpriseWorkspaceClaimLockPolicy | None:
        self.lookups.append(workspace_id)

        if self.events is not None:
            self.events.append("policy_lookup")

        if self.error is not None:
            raise self.error

        return self.policy


class _RuntimeAuthorizationGate:
    def __init__(
        self,
        *,
        error: Exception | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.error = error
        self.events = events
        self.calls: list[
            tuple[str, str, EnterprisePermission]
        ] = []

    def require(
        self,
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> object:
        self.calls.append(
            (
                workspace_id,
                user_id,
                permission,
            )
        )

        if self.events is not None:
            self.events.append("authorization")

        if self.error is not None:
            raise self.error

        return object()


class _CountingPreparationService:
    def __init__(self) -> None:
        self.calls = 0

    def prepare(
        self,
        **_kwargs: object,
    ) -> ClaimLockPreparationResult:
        self.calls += 1
        return _preparation()


class _StaticPreparationService:
    def __init__(
        self,
        result: ClaimLockPreparationResult,
    ) -> None:
        self.result = result

    def prepare(
        self,
        **_kwargs: object,
    ) -> ClaimLockPreparationResult:
        return self.result


def _runtime_workspace_term(
    *,
    policy_id: str,
    revision: int,
    term_id: str,
    text: str,
    case_sensitive: bool = True,
) -> ProtectedTerm:
    return ProtectedTerm(
        term_id=term_id,
        text=text,
        case_sensitive=case_sensitive,
        provenance=ClaimLockProvenance(
            origin=ClaimLockOrigin.WORKSPACE,
            source_reference=(
                "workspace-claim-lock-policy:"
                f"{policy_id}:revision:{revision}"
            ),
        ),
    )


def _runtime_policy(
    *,
    policy_id: str = "policy_1",
    workspace_id: str = "workspace_1",
    status: EnterpriseClaimLockPolicyStatus = (
        EnterpriseClaimLockPolicyStatus.ACTIVE
    ),
    enforcement_mode: ClaimLockEnforcementMode = (
        ClaimLockEnforcementMode.STRICT
    ),
    protected_terms: tuple[ProtectedTerm, ...] = (),
    revision: int = 1,
) -> EnterpriseWorkspaceClaimLockPolicy:
    return EnterpriseWorkspaceClaimLockPolicy(
        policy_id=policy_id,
        workspace_id=workspace_id,
        status=status,
        enforcement_mode=enforcement_mode,
        protected_terms=protected_terms,
        created_by_user_id="user_owner",
        created_at=_RUNTIME_TEST_NOW,
        updated_by_user_id="user_owner",
        updated_at=_RUNTIME_TEST_NOW,
        revision=revision,
    )


def _runtime_service(
    *,
    repository: _RuntimePolicyRepository,
    gate: _RuntimeAuthorizationGate,
    preparation_service: object | None = None,
) -> EnterpriseClaimLockRuntimeService:
    return EnterpriseClaimLockRuntimeService(
        policies=repository,
        authorization_gate=gate,
        preparation_service=(
            preparation_service
            if preparation_service is not None
            else ClaimLockPreparationService()
        ),
    )


def test_runtime_service_no_policy_and_disabled_policy_preserve_legacy_behavior() -> None:
    no_policy = _runtime_service(
        repository=_RuntimePolicyRepository(),
        gate=_RuntimeAuthorizationGate(),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="",
    )

    disabled = _runtime_service(
        repository=_RuntimePolicyRepository(
            _runtime_policy(
                status=EnterpriseClaimLockPolicyStatus.DISABLED,
                enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
                protected_terms=(
                    _runtime_workspace_term(
                        policy_id="policy_1",
                        revision=1,
                        term_id="workspace_term_1",
                        text="Humanize Enterprise",
                    ),
                ),
            )
        ),
        gate=_RuntimeAuthorizationGate(),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="Humanize Enterprise",
    )

    for runtime in (no_policy, disabled):
        assert runtime.workspace_policy_evidence is None
        assert runtime.effective_claim_lock is None
        assert (
            runtime.effective_enforcement_mode
            is ClaimLockEnforcementMode.STRICT
        )


@pytest.mark.parametrize(
    (
        "workspace_mode",
        "request_mode",
        "expected_mode",
    ),
    (
        (
            ClaimLockEnforcementMode.AUDIT_ONLY,
            None,
            ClaimLockEnforcementMode.AUDIT_ONLY,
        ),
        (
            ClaimLockEnforcementMode.STRICT,
            None,
            ClaimLockEnforcementMode.STRICT,
        ),
        (
            ClaimLockEnforcementMode.AUDIT_ONLY,
            ClaimLockEnforcementMode.STRICT,
            ClaimLockEnforcementMode.STRICT,
        ),
        (
            ClaimLockEnforcementMode.STRICT,
            ClaimLockEnforcementMode.AUDIT_ONLY,
            ClaimLockEnforcementMode.STRICT,
        ),
    ),
)
def test_runtime_service_active_policy_mode_precedence(
    workspace_mode: ClaimLockEnforcementMode,
    request_mode: ClaimLockEnforcementMode | None,
    expected_mode: ClaimLockEnforcementMode,
) -> None:
    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(
            _runtime_policy(
                enforcement_mode=workspace_mode,
            )
        ),
        gate=_RuntimeAuthorizationGate(),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="",
        claim_lock_enforcement_mode=request_mode,
    )

    assert runtime.workspace_policy_evidence is not None
    assert runtime.effective_enforcement_mode is expected_mode


def test_runtime_service_mode_only_active_policy_rebuilds_source_lock() -> None:
    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(
            _runtime_policy(
                enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
            )
        ),
        gate=_RuntimeAuthorizationGate(),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="100",
    )

    assert runtime.request_preparation.claim_lock is not None
    assert runtime.effective_claim_lock is not None
    assert (
        runtime.effective_claim_lock
        is not runtime.request_preparation.claim_lock
    )
    assert (
        runtime.effective_claim_lock.enforcement_mode
        is ClaimLockEnforcementMode.AUDIT_ONLY
    )


def test_runtime_service_terms_only_request_defaults_strict_and_requires_use() -> None:
    gate = _RuntimeAuthorizationGate()

    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(),
        gate=gate,
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="Alpha",
        explicit_protected_terms=(
            ExplicitProtectedTerm(
                text="Alpha",
            ),
        ),
    )

    assert runtime.request_customization_requested is True
    assert runtime.effective_claim_lock is not None
    assert (
        runtime.effective_enforcement_mode
        is ClaimLockEnforcementMode.STRICT
    )
    assert gate.calls == [
        (
            "workspace_1",
            "user_1",
            EnterprisePermission.CLAIM_LOCK_USE,
        )
    ]


def test_runtime_service_mode_only_request_requires_claim_lock_use() -> None:
    gate = _RuntimeAuthorizationGate()

    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(),
        gate=gate,
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="",
        claim_lock_enforcement_mode=(
            ClaimLockEnforcementMode.AUDIT_ONLY
        ),
    )

    assert runtime.request_customization_requested is True
    assert (
        runtime.effective_enforcement_mode
        is ClaimLockEnforcementMode.AUDIT_ONLY
    )
    assert gate.calls[0][2] is EnterprisePermission.CLAIM_LOCK_USE


def test_runtime_service_claim_lock_use_denial_stops_before_preparation() -> None:
    preparation = _CountingPreparationService()

    with pytest.raises(
        PermissionError,
        match="permission_not_granted",
    ):
        _runtime_service(
            repository=_RuntimePolicyRepository(),
            gate=_RuntimeAuthorizationGate(
                error=PermissionError(
                    "permission_not_granted"
                ),
            ),
            preparation_service=preparation,
        ).resolve(
            workspace_id="workspace_1",
            user_id="user_1",
            text="Alpha",
            explicit_protected_terms=(
                ExplicitProtectedTerm(
                    text="Alpha",
                ),
            ),
        )

    assert preparation.calls == 0


def test_runtime_service_policy_lookup_precedes_request_authorization() -> None:
    events: list[str] = []

    _runtime_service(
        repository=_RuntimePolicyRepository(
            events=events,
        ),
        gate=_RuntimeAuthorizationGate(
            events=events,
        ),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="",
        claim_lock_enforcement_mode=(
            ClaimLockEnforcementMode.STRICT
        ),
    )

    assert events == [
        "policy_lookup",
        "authorization",
    ]


def test_runtime_service_mandatory_policy_requires_no_claim_lock_permission() -> None:
    gate = _RuntimeAuthorizationGate()

    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(
            _runtime_policy()
        ),
        gate=gate,
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="",
    )

    assert runtime.workspace_policy_evidence is not None
    assert gate.calls == []


@pytest.mark.parametrize(
    (
        "case_sensitive",
        "source_text",
        "expected_ids",
    ),
    (
        (
            True,
            "humanize enterprise",
            (),
        ),
        (
            False,
            "humanize   enterprise",
            ("workspace_term_1",),
        ),
        (
            True,
            "Other text",
            (),
        ),
    ),
)
def test_runtime_service_workspace_term_applicability(
    case_sensitive: bool,
    source_text: str,
    expected_ids: tuple[str, ...],
) -> None:
    term = _runtime_workspace_term(
        policy_id="policy_1",
        revision=1,
        term_id="workspace_term_1",
        text="Humanize Enterprise",
        case_sensitive=case_sensitive,
    )

    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(
            _runtime_policy(
                protected_terms=(term,),
            )
        ),
        gate=_RuntimeAuthorizationGate(),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text=source_text,
    )

    assert runtime.workspace_policy_evidence is not None
    assert (
        runtime.workspace_policy_evidence.applicable_term_ids
        == expected_ids
    )

    if expected_ids:
        assert runtime.effective_claim_lock is not None
        assert runtime.effective_claim_lock.terms == (term,)
    else:
        assert runtime.effective_claim_lock is None


def test_runtime_service_workspace_collision_wins_and_request_only_term_survives() -> None:
    workspace_term = _runtime_workspace_term(
        policy_id="policy_1",
        revision=1,
        term_id="workspace_term_1",
        text="Humanize Enterprise",
        case_sensitive=False,
    )

    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(
            _runtime_policy(
                protected_terms=(workspace_term,),
            )
        ),
        gate=_RuntimeAuthorizationGate(),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="Humanize Enterprise Alpha",
        explicit_protected_terms=(
            ExplicitProtectedTerm(
                text="Humanize Enterprise",
                case_sensitive=True,
            ),
            ExplicitProtectedTerm(
                text="Alpha",
            ),
        ),
    )

    assert runtime.effective_claim_lock is not None
    assert runtime.effective_claim_lock.terms[0] == workspace_term
    assert runtime.effective_claim_lock.terms[0].case_sensitive is False
    assert (
        runtime.effective_claim_lock.terms[0].provenance.origin
        is ClaimLockOrigin.WORKSPACE
    )
    assert runtime.effective_claim_lock.terms[1].text == "Alpha"
    assert (
        runtime.effective_claim_lock.terms[1].provenance.origin
        is ClaimLockOrigin.REQUEST
    )


def test_runtime_service_retains_source_claims_and_values_during_recomposition() -> None:
    provenance = ClaimLockProvenance(
        origin=ClaimLockOrigin.REQUEST,
        source_reference="rewrite-request",
    )
    claim = ProtectedClaim(
        claim_id="claim_source",
        text="Revenue increased",
        provenance=provenance,
    )
    value = ProtectedValue(
        value_id="value_source",
        value="100",
        kind=ProtectedValueKind.NUMBER,
        provenance=provenance,
    )
    prepared_lock = ClaimLock(
        lock_id="lock_prepared",
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        claims=(claim,),
        values=(value,),
    )

    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(
            _runtime_policy(
                enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
            )
        ),
        gate=_RuntimeAuthorizationGate(),
        preparation_service=_StaticPreparationService(
            _preparation(
                claim_lock=prepared_lock,
            )
        ),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="Revenue increased to 100",
    )

    assert runtime.effective_claim_lock is not None
    assert runtime.effective_claim_lock.claims == (claim,)
    assert runtime.effective_claim_lock.values == (value,)
    assert (
        runtime.effective_claim_lock.enforcement_mode
        is ClaimLockEnforcementMode.AUDIT_ONLY
    )


def test_runtime_service_identifier_conflict_fails_closed() -> None:
    request_preparation = ClaimLockPreparationService().prepare(
        text="Alpha Beta",
        explicit_terms=(
            ExplicitProtectedTerm(
                text="Alpha",
            ),
        ),
    )

    assert request_preparation.claim_lock is not None

    workspace_term = _runtime_workspace_term(
        policy_id="policy_conflict",
        revision=1,
        term_id=(
            request_preparation.claim_lock.terms[0].term_id
        ),
        text="Beta",
    )

    with pytest.raises(
        EnterpriseClaimLockRuntimeIntegrityError,
        match="claim_lock_composition_conflict",
    ) as caught:
        _runtime_service(
            repository=_RuntimePolicyRepository(
                _runtime_policy(
                    policy_id="policy_conflict",
                    protected_terms=(workspace_term,),
                )
            ),
            gate=_RuntimeAuthorizationGate(),
        ).resolve(
            workspace_id="workspace_1",
            user_id="user_1",
            text="Alpha Beta",
            explicit_protected_terms=(
                ExplicitProtectedTerm(
                    text="Alpha",
                ),
            ),
        )

    assert caught.value.reason == "claim_lock_composition_conflict"


def test_runtime_service_repository_failure_fails_closed() -> None:
    with pytest.raises(
        EnterpriseClaimLockRuntimeIntegrityError,
        match="claim_lock_policy_resolution_failed",
    ) as caught:
        _runtime_service(
            repository=_RuntimePolicyRepository(
                error=RuntimeError("repository failure"),
            ),
            gate=_RuntimeAuthorizationGate(),
        ).resolve(
            workspace_id="workspace_1",
            user_id="user_1",
            text="",
        )

    assert caught.value.reason == "claim_lock_policy_resolution_failed"


@pytest.mark.parametrize(
    "resolved_policy",
    (
        _runtime_policy(
            workspace_id="workspace_2",
        ),
        _runtime_policy(
            status=EnterpriseClaimLockPolicyStatus.ARCHIVED,
        ),
    ),
)
def test_runtime_service_invalid_resolved_policy_identity_fails_closed(
    resolved_policy: EnterpriseWorkspaceClaimLockPolicy,
) -> None:
    with pytest.raises(
        EnterpriseClaimLockRuntimeIntegrityError,
        match="claim_lock_policy_resolution_failed",
    ) as caught:
        _runtime_service(
            repository=_RuntimePolicyRepository(
                resolved_policy
            ),
            gate=_RuntimeAuthorizationGate(),
        ).resolve(
            workspace_id="workspace_1",
            user_id="user_1",
            text="",
        )

    assert caught.value.reason == "claim_lock_policy_resolution_failed"


def test_runtime_service_composition_is_deterministic() -> None:
    workspace_terms = (
        _runtime_workspace_term(
            policy_id="policy_1",
            revision=1,
            term_id="workspace_term_2",
            text="Workspace Two",
        ),
        _runtime_workspace_term(
            policy_id="policy_1",
            revision=1,
            term_id="workspace_term_1",
            text="Workspace One",
        ),
    )
    active = _runtime_policy(
        enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
        protected_terms=workspace_terms,
    )

    def resolve() -> EnterpriseClaimLockRuntimeContext:
        return _runtime_service(
            repository=_RuntimePolicyRepository(active),
            gate=_RuntimeAuthorizationGate(),
        ).resolve(
            workspace_id="workspace_1",
            user_id="user_1",
            text=(
                "Workspace Two Workspace One "
                "Request Two Request One 100"
            ),
            explicit_protected_terms=(
                ExplicitProtectedTerm(
                    text="Request Two",
                ),
                ExplicitProtectedTerm(
                    text="Request One",
                ),
            ),
            claim_lock_enforcement_mode=(
                ClaimLockEnforcementMode.AUDIT_ONLY
            ),
        )

    first = resolve()
    second = resolve()

    assert (
        first.effective_enforcement_mode
        is ClaimLockEnforcementMode.AUDIT_ONLY
    )
    assert first.effective_claim_lock is not None
    assert second.effective_claim_lock is not None
    assert tuple(
        term.text
        for term in first.effective_claim_lock.terms
    ) == (
        "Workspace Two",
        "Workspace One",
        "Request Two",
        "Request One",
    )
    assert (
        first.effective_claim_lock.lock_id
        == second.effective_claim_lock.lock_id
    )


def test_runtime_service_preserves_unchanged_prepared_lock_and_source_reference() -> None:
    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(),
        gate=_RuntimeAuthorizationGate(),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="Alpha",
        explicit_protected_terms=(
            ExplicitProtectedTerm(
                text="Alpha",
            ),
        ),
        source_reference="long-document-rewrite-request",
    )

    assert runtime.request_preparation.claim_lock is not None
    assert (
        runtime.effective_claim_lock
        is runtime.request_preparation.claim_lock
    )
    assert runtime.effective_claim_lock is not None
    assert (
        runtime.effective_claim_lock.terms[0].provenance.source_reference
        == "long-document-rewrite-request"
    )


def test_runtime_service_policy_revision_evidence_and_empty_lock_are_truthful() -> None:
    unrelated_term = _runtime_workspace_term(
        policy_id="policy_1",
        revision=7,
        term_id="workspace_term_1",
        text="Humanize Enterprise",
    )

    runtime = _runtime_service(
        repository=_RuntimePolicyRepository(
            _runtime_policy(
                enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
                protected_terms=(unrelated_term,),
                revision=7,
            )
        ),
        gate=_RuntimeAuthorizationGate(),
    ).resolve(
        workspace_id="workspace_1",
        user_id="user_1",
        text="Other text",
    )

    assert runtime.workspace_policy_evidence is not None
    assert runtime.workspace_policy_evidence.policy_id == "policy_1"
    assert runtime.workspace_policy_evidence.policy_revision == 7
    assert runtime.workspace_policy_evidence.applicable_term_ids == ()
    assert runtime.effective_claim_lock is None
    assert (
        runtime.effective_enforcement_mode
        is ClaimLockEnforcementMode.AUDIT_ONLY
    )
