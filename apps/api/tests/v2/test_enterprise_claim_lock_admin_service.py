from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import count
from unittest.mock import MagicMock

import pytest

from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
)
from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditOutcome,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
)
from app.v2.domain.enterprise_rbac import (
    EnterprisePermission,
)
from app.v2.domain.enterprise_workspace import (
    EnterpriseWorkspaceRole,
)
from app.v2.repositories.enterprise_admin_audit import (
    InMemoryEnterpriseAdminAuditRepository,
)
from app.v2.repositories.enterprise_claim_lock_policies import (
    EnterpriseClaimLockPolicyArchivedError,
    EnterpriseClaimLockPolicyIntegrityError,
    EnterpriseClaimLockPolicyNotFoundError,
    EnterpriseClaimLockPolicyRevisionConflictError,
    InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
)
from app.v2.repositories.enterprise_claim_lock_policy_admin_mutations import (
    EnterpriseClaimLockPolicyAdminMutationConfigurationError,
    EnterpriseClaimLockPolicyAdminMutationRepository,
    InMemoryEnterpriseClaimLockPolicyAdminMutationRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingService,
)
from app.v2.services.enterprise_authorization_resolver import (
    AuthorizationResolutionFailureReason,
    AuthorizationResolutionStatus,
    EnterpriseAuthorizationResolutionResult,
    EnterpriseAuthorizationResolver,
)
from app.v2.services.enterprise_authorization_service import (
    AuthorizationDecision,
    AuthorizationDenialReason,
    EnterpriseAuthorizationResult,
)
from app.v2.services.enterprise_claim_lock_admin_service import (
    ClaimLockAdministrationFailureReason,
    EnterpriseClaimLockAdministrationError,
    EnterpriseClaimLockAdminService,
)


WORKSPACE_ID = "workspace_test"
ACTOR_USER_ID = "user_admin"
POLICY_ID = "policy_claim_lock"

BASE_TIME = datetime(
    2026,
    8,
    24,
    12,
    0,
    tzinfo=UTC,
)


class _Clock:
    def __init__(self) -> None:
        self._index = 0

    def __call__(self) -> datetime:
        value = BASE_TIME + timedelta(
            minutes=self._index
        )
        self._index += 1
        return value


def _term(
    *,
    text: str = "Humanize Enterprise",
) -> dict[str, object]:
    return {
        "term_id": "term_product",
        "text": text,
        "case_sensitive": True,
    }


def _resolution(
    *,
    workspace_id: str,
    permission: EnterprisePermission,
    mode: str = "allow",
) -> EnterpriseAuthorizationResolutionResult:
    if mode == "resolution_failed":
        return EnterpriseAuthorizationResolutionResult(
            status=(
                AuthorizationResolutionStatus
                .RESOLUTION_FAILED
            ),
            workspace_id=workspace_id,
            user_id=ACTOR_USER_ID,
            permission=permission,
            failure_reason=(
                AuthorizationResolutionFailureReason
                .MEMBERSHIP_NOT_FOUND
            ),
        )

    decision = (
        AuthorizationDecision.DENY
        if mode == "deny"
        else AuthorizationDecision.ALLOW
    )

    authorization = EnterpriseAuthorizationResult(
        decision=decision,
        permission=permission,
        organization_id="organization_test",
        workspace_id=workspace_id,
        membership_id="membership_test",
        user_id=ACTOR_USER_ID,
        role=EnterpriseWorkspaceRole.ADMIN,
        denial_reason=(
            AuthorizationDenialReason
            .PERMISSION_NOT_GRANTED
            if decision is AuthorizationDecision.DENY
            else None
        ),
    )

    return EnterpriseAuthorizationResolutionResult(
        status=AuthorizationResolutionStatus.RESOLVED,
        workspace_id=workspace_id,
        user_id=ACTOR_USER_ID,
        permission=permission,
        authorization=authorization,
    )


def _service(
    *,
    authorization_mode: str = "allow",
):
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()

    resolver = MagicMock(
        spec=EnterpriseAuthorizationResolver,
    )

    def resolve(
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> EnterpriseAuthorizationResolutionResult:
        assert user_id == ACTOR_USER_ID

        return _resolution(
            workspace_id=workspace_id,
            permission=permission,
            mode=authorization_mode,
        )

    resolver.resolve.side_effect = resolve

    event_ids = count(1)

    audit_recording = EnterpriseAdminAuditRecordingService(
        repository=audit,
        event_id_factory=lambda: (
            f"audit_{next(event_ids):03d}"
        ),
        clock=lambda: BASE_TIME + timedelta(hours=8),
    )

    atomic = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    service = EnterpriseClaimLockAdminService(
        policies=policies,
        authorization_resolver=resolver,
        audit_recording=audit_recording,
        atomic_mutations=atomic,
        clock=_Clock(),
    )

    return service, policies, audit, resolver


def _events(audit):
    return audit.list_for_workspace(
        workspace_id=WORKSPACE_ID,
        period_start=BASE_TIME - timedelta(days=1),
        period_end=BASE_TIME + timedelta(days=2),
    )


def test_create_policy_requires_claim_lock_manage() -> None:
    service, _policies, _audit, resolver = _service()

    service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    resolver.resolve.assert_called_once_with(
        workspace_id=WORKSPACE_ID,
        user_id=ACTOR_USER_ID,
        permission=EnterprisePermission.CLAIM_LOCK_MANAGE,
    )


def test_create_policy_persists_canonical_workspace_provenance() -> None:
    service, policies, audit, _resolver = _service()

    created = service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    assert created.revision == 1
    assert (
        created.status
        is EnterpriseClaimLockPolicyStatus.ACTIVE
    )

    term = created.protected_terms[0]

    assert (
        term.provenance.origin
        is ClaimLockOrigin.WORKSPACE
    )
    assert (
        term.provenance.source_reference
        == (
            "workspace-claim-lock-policy:"
            f"{POLICY_ID}:revision:1"
        )
    )

    assert policies.get_by_id(POLICY_ID) == created

    events = _events(audit)

    assert len(events) == 1
    assert (
        events[0].action
        is EnterpriseAdminAuditAction
        .CLAIM_LOCK_POLICY_CREATE
    )
    assert (
        events[0].outcome
        is EnterpriseAdminAuditOutcome.SUCCEEDED
    )


def test_get_policy_requires_claim_lock_read() -> None:
    service, _policies, _audit, resolver = _service()

    service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    resolver.reset_mock()

    policy = service.get_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
    )

    assert policy.policy_id == POLICY_ID

    resolver.resolve.assert_called_once_with(
        workspace_id=WORKSPACE_ID,
        user_id=ACTOR_USER_ID,
        permission=EnterprisePermission.CLAIM_LOCK_READ,
    )


@pytest.mark.parametrize(
    ("mode", "reason"),
    (
        (
            "resolution_failed",
            ClaimLockAdministrationFailureReason
            .AUTHORIZATION_RESOLUTION_FAILED,
        ),
        (
            "deny",
            ClaimLockAdministrationFailureReason
            .AUTHORIZATION_DENIED,
        ),
    ),
)
def test_create_authorization_failure_is_denied_and_preserves_state(
    mode: str,
    reason: ClaimLockAdministrationFailureReason,
) -> None:
    service, policies, audit, _resolver = _service(
        authorization_mode=mode,
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.create_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            enforcement_mode=ClaimLockEnforcementMode.STRICT,
            protected_terms=(_term(),),
        )

    assert exc_info.value.reason is reason
    assert policies.get_by_id(POLICY_ID) is None

    events = _events(audit)

    assert len(events) == 1
    assert (
        events[0].outcome
        is EnterpriseAdminAuditOutcome.DENIED
    )
    assert events[0].failure_reason == reason.value


def test_lifecycle_rebuilds_revision_provenance() -> None:
    service, policies, audit, _resolver = _service()

    created = service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    disabled = service.disable_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        expected_revision=1,
    )

    assert created.revision == 1
    assert disabled.revision == 2
    assert (
        disabled.status
        is EnterpriseClaimLockPolicyStatus.DISABLED
    )
    assert disabled.created_at == created.created_at
    assert disabled.updated_at > created.updated_at

    assert (
        disabled.protected_terms[0]
        .provenance.source_reference
        == (
            "workspace-claim-lock-policy:"
            f"{POLICY_ID}:revision:2"
        )
    )

    assert policies.get_by_id(POLICY_ID) == disabled

    events = _events(audit)

    assert [
        event.action
        for event in events
    ] == [
        EnterpriseAdminAuditAction
        .CLAIM_LOCK_POLICY_CREATE,
        EnterpriseAdminAuditAction
        .CLAIM_LOCK_POLICY_DISABLE,
    ]


def test_revision_conflict_is_failed_and_preserves_state() -> None:
    service, policies, audit, _resolver = _service()

    created = service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.update_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            expected_revision=99,
            enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
            protected_terms=(
                _term(text="Must Not Persist"),
            ),
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .REVISION_CONFLICT
    )

    assert policies.get_by_id(POLICY_ID) == created

    event = _events(audit)[-1]

    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        event.failure_reason
        == ClaimLockAdministrationFailureReason
        .REVISION_CONFLICT.value
    )


@pytest.mark.parametrize(
    "protected_terms",
    (
        (
            {
                "term_id": "term_product",
                "text": "Humanize Enterprise",
                "case_sensitive": True,
                "provenance": "client-forbidden",
            },
        ),
        (
            _term(
                text="Humanize Enterprise",
            ),
            {
                "term_id": "term_second",
                "text": "Humanize Enterprise",
                "case_sensitive": True,
            },
        ),
    ),
)
def test_invalid_workspace_term_fails_with_failed_audit(
    protected_terms: tuple[dict[str, object], ...],
) -> None:
    service, policies, audit, _resolver = _service()

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.create_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            enforcement_mode=ClaimLockEnforcementMode.STRICT,
            protected_terms=protected_terms,
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .INVALID_WORKSPACE_TERM
    )

    assert policies.get_by_id(POLICY_ID) is None

    events = _events(audit)

    assert len(events) == 1
    assert (
        events[0].outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        events[0].failure_reason
        == ClaimLockAdministrationFailureReason
        .INVALID_WORKSPACE_TERM.value
    )


def test_duplicate_current_policy_fails_and_preserves_state() -> None:
    service, policies, audit, _resolver = _service()

    created = service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    second_policy_id = "policy_claim_lock_second"

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.create_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=second_policy_id,
            enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
            protected_terms=(
                {
                    "term_id": "term_second",
                    "text": "Governed Intelligence",
                    "case_sensitive": False,
                },
            ),
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .POLICY_ALREADY_EXISTS
    )

    assert policies.get_by_id(POLICY_ID) == created
    assert policies.get_by_id(second_policy_id) is None

    event = _events(audit)[-1]

    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        event.failure_reason
        == ClaimLockAdministrationFailureReason
        .POLICY_ALREADY_EXISTS.value
    )


def test_normal_patch_preserves_active_and_disabled_status() -> None:
    service, policies, _audit, _resolver = _service()

    created = service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    active_updated = service.update_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        expected_revision=1,
        enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
        protected_terms=(
            _term(text="Humanize Enterprise AI"),
        ),
    )

    assert (
        active_updated.status
        is EnterpriseClaimLockPolicyStatus.ACTIVE
    )
    assert active_updated.revision == 2
    assert active_updated.created_at == created.created_at
    assert (
        active_updated.protected_terms[0]
        .provenance.source_reference
        == (
            "workspace-claim-lock-policy:"
            f"{POLICY_ID}:revision:2"
        )
    )

    disabled = service.disable_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        expected_revision=2,
    )

    disabled_updated = service.update_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        expected_revision=3,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(
            _term(text="Governed Intelligence"),
        ),
    )

    assert (
        disabled.status
        is EnterpriseClaimLockPolicyStatus.DISABLED
    )
    assert (
        disabled_updated.status
        is EnterpriseClaimLockPolicyStatus.DISABLED
    )
    assert disabled_updated.revision == 4
    assert (
        disabled_updated.protected_terms[0]
        .provenance.source_reference
        == (
            "workspace-claim-lock-policy:"
            f"{POLICY_ID}:revision:4"
        )
    )

    assert (
        policies.get_by_id(POLICY_ID)
        == disabled_updated
    )


def test_enable_active_and_disable_disabled_use_specific_failures() -> None:
    service, policies, audit, _resolver = _service()

    active = service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as active_exc:
        service.enable_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            expected_revision=1,
        )

    assert (
        active_exc.value.reason
        is ClaimLockAdministrationFailureReason
        .POLICY_ALREADY_ACTIVE
    )
    assert policies.get_by_id(POLICY_ID) == active

    disabled = service.disable_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        expected_revision=1,
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as disabled_exc:
        service.disable_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            expected_revision=2,
        )

    assert (
        disabled_exc.value.reason
        is ClaimLockAdministrationFailureReason
        .POLICY_ALREADY_DISABLED
    )
    assert policies.get_by_id(POLICY_ID) == disabled

    events = _events(audit)

    assert (
        events[1].outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        events[-1].outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )


def test_archived_policy_is_terminal() -> None:
    service, policies, audit, _resolver = _service()

    service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    archived = service.archive_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        expected_revision=1,
    )

    assert (
        archived.status
        is EnterpriseClaimLockPolicyStatus.ARCHIVED
    )
    assert archived.revision == 2

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.update_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            expected_revision=2,
            enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
            protected_terms=(
                _term(text="Must Not Persist"),
            ),
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .POLICY_ARCHIVED
    )

    assert policies.get_by_id(POLICY_ID) == archived

    event = _events(audit)[-1]

    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        event.failure_reason
        == ClaimLockAdministrationFailureReason
        .POLICY_ARCHIVED.value
    )


def test_cross_workspace_policy_is_not_mutated() -> None:
    service, policies, audit, _resolver = _service()

    other_workspace_id = "workspace_other"
    foreign_policy_id = "policy_foreign"

    foreign = service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=other_workspace_id,
        policy_id=foreign_policy_id,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.update_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=foreign_policy_id,
            expected_revision=1,
            enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
            protected_terms=(
                _term(text="Cross Tenant Mutation"),
            ),
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .POLICY_SCOPE_MISMATCH
    )

    assert (
        policies.get_by_id(foreign_policy_id)
        == foreign
    )

    events = _events(audit)

    assert len(events) == 1
    assert events[0].workspace_id == WORKSPACE_ID
    assert (
        events[0].outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        events[0].failure_reason
        == ClaimLockAdministrationFailureReason
        .POLICY_SCOPE_MISMATCH.value
    )


def _service_with_atomic(
    atomic_mutations: object,
):
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    resolver = _resolver()

    event_ids = count(100)

    audit_recording = EnterpriseAdminAuditRecordingService(
        repository=audit,
        event_id_factory=lambda: (
            f"audit_failure_{next(event_ids):03d}"
        ),
        clock=lambda: (
            BASE_TIME + timedelta(hours=10)
        ),
    )

    service = EnterpriseClaimLockAdminService(
        policies=policies,
        authorization_resolver=resolver,
        audit_recording=audit_recording,
        atomic_mutations=atomic_mutations,
        clock=_Clock(),
    )

    return service, policies, audit


def _seeded_service_with_update_error(
    repository_error: Exception,
):
    seed_service, policies, audit, _seed_resolver = _service()

    created = seed_service.create_policy(
        actor_user_id=ACTOR_USER_ID,
        workspace_id=WORKSPACE_ID,
        policy_id=POLICY_ID,
        enforcement_mode=ClaimLockEnforcementMode.STRICT,
        protected_terms=(_term(),),
    )

    atomic = MagicMock(
        spec=EnterpriseClaimLockPolicyAdminMutationRepository,
    )
    atomic.update_policy_with_audit.side_effect = (
        repository_error
    )

    event_ids = count(100)

    audit_recording = EnterpriseAdminAuditRecordingService(
        repository=audit,
        event_id_factory=lambda: (
            f"audit_failure_{next(event_ids):03d}"
        ),
        clock=lambda: (
            BASE_TIME + timedelta(hours=10)
        ),
    )

    service = EnterpriseClaimLockAdminService(
        policies=policies,
        authorization_resolver=_resolver(),
        audit_recording=audit_recording,
        atomic_mutations=atomic,
        clock=_Clock(),
    )

    return service, policies, audit, created, atomic


@pytest.mark.parametrize(
    ("repository_error", "expected_reason"),
    (
        (
            EnterpriseClaimLockPolicyRevisionConflictError(
                "simulated revision race"
            ),
            ClaimLockAdministrationFailureReason
            .REVISION_CONFLICT,
        ),
        (
            EnterpriseClaimLockPolicyArchivedError(
                "simulated archive race"
            ),
            ClaimLockAdministrationFailureReason
            .POLICY_ARCHIVED,
        ),
        (
            EnterpriseClaimLockPolicyNotFoundError(
                "simulated missing-policy race"
            ),
            ClaimLockAdministrationFailureReason
            .POLICY_NOT_FOUND,
        ),
        (
            EnterpriseClaimLockPolicyAdminMutationConfigurationError(
                "simulated incompatible transaction boundary"
            ),
            ClaimLockAdministrationFailureReason
            .TRANSACTION_REQUIRED,
        ),
        (
            EnterpriseClaimLockPolicyIntegrityError(
                "simulated persistence integrity rejection"
            ),
            ClaimLockAdministrationFailureReason
            .PERSISTENCE_REJECTED,
        ),
    ),
)
def test_atomic_update_errors_map_to_frozen_vocabulary(
    repository_error: Exception,
    expected_reason: ClaimLockAdministrationFailureReason,
) -> None:
    (
        service,
        policies,
        audit,
        created,
        atomic,
    ) = _seeded_service_with_update_error(
        repository_error
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.update_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            expected_revision=1,
            enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
            protected_terms=(
                _term(text="Candidate Must Not Persist"),
            ),
        )

    assert exc_info.value.reason is expected_reason

    assert policies.get_by_id(POLICY_ID) == created

    atomic.update_policy_with_audit.assert_called_once()

    event = _events(audit)[-1]

    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert event.failure_reason == expected_reason.value


def test_atomic_create_transaction_failure_maps_to_transaction_required() -> None:
    atomic = MagicMock(
        spec=EnterpriseClaimLockPolicyAdminMutationRepository,
    )
    atomic.create_policy_with_audit.side_effect = (
        EnterpriseClaimLockPolicyAdminMutationConfigurationError(
            "incompatible atomic transaction"
        )
    )

    service, policies, audit = _service_with_atomic(
        atomic
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.create_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            enforcement_mode=ClaimLockEnforcementMode.STRICT,
            protected_terms=(_term(),),
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .TRANSACTION_REQUIRED
    )

    assert policies.get_by_id(POLICY_ID) is None

    atomic.create_policy_with_audit.assert_called_once()

    event = _events(audit)[-1]

    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        event.failure_reason
        == ClaimLockAdministrationFailureReason
        .TRANSACTION_REQUIRED.value
    )


def test_generic_atomic_rejection_maps_to_persistence_rejected() -> None:
    atomic = MagicMock(
        spec=EnterpriseClaimLockPolicyAdminMutationRepository,
    )
    atomic.create_policy_with_audit.side_effect = RuntimeError(
        "simulated persistence failure"
    )

    service, policies, audit = _service_with_atomic(
        atomic
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.create_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            enforcement_mode=ClaimLockEnforcementMode.STRICT,
            protected_terms=(_term(),),
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .PERSISTENCE_REJECTED
    )

    assert policies.get_by_id(POLICY_ID) is None

    event = _events(audit)[-1]

    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.FAILED
    )
    assert (
        event.failure_reason
        == ClaimLockAdministrationFailureReason
        .PERSISTENCE_REJECTED.value
    )


def test_denied_audit_persistence_failure_fails_closed() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )

    broken_audit = MagicMock()
    broken_audit.create.side_effect = RuntimeError(
        "audit persistence unavailable"
    )

    audit_recording = EnterpriseAdminAuditRecordingService(
        repository=broken_audit,
        event_id_factory=lambda: "audit_broken_denied",
        clock=lambda: BASE_TIME,
    )

    atomic = MagicMock(
        spec=EnterpriseClaimLockPolicyAdminMutationRepository,
    )

    service = EnterpriseClaimLockAdminService(
        policies=policies,
        authorization_resolver=_resolver("deny"),
        audit_recording=audit_recording,
        atomic_mutations=atomic,
        clock=_Clock(),
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.create_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            enforcement_mode=ClaimLockEnforcementMode.STRICT,
            protected_terms=(_term(),),
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .PERSISTENCE_REJECTED
    )

    assert policies.get_by_id(POLICY_ID) is None

    atomic.create_policy_with_audit.assert_not_called()


def test_failed_audit_persistence_failure_fails_closed() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )

    broken_audit = MagicMock()
    broken_audit.create.side_effect = RuntimeError(
        "audit persistence unavailable"
    )

    audit_recording = EnterpriseAdminAuditRecordingService(
        repository=broken_audit,
        event_id_factory=lambda: "audit_broken_failed",
        clock=lambda: BASE_TIME,
    )

    atomic = MagicMock(
        spec=EnterpriseClaimLockPolicyAdminMutationRepository,
    )

    service = EnterpriseClaimLockAdminService(
        policies=policies,
        authorization_resolver=_resolver(),
        audit_recording=audit_recording,
        atomic_mutations=atomic,
        clock=_Clock(),
    )

    with pytest.raises(
        EnterpriseClaimLockAdministrationError
    ) as exc_info:
        service.create_policy(
            actor_user_id=ACTOR_USER_ID,
            workspace_id=WORKSPACE_ID,
            policy_id=POLICY_ID,
            enforcement_mode=ClaimLockEnforcementMode.STRICT,
            protected_terms=(
                {
                    "term_id": "term_product",
                    "text": "Humanize Enterprise",
                    "case_sensitive": True,
                    "provenance": "client-forbidden",
                },
            ),
        )

    assert (
        exc_info.value.reason
        is ClaimLockAdministrationFailureReason
        .PERSISTENCE_REJECTED
    )

    assert policies.get_by_id(POLICY_ID) is None

    atomic.create_policy_with_audit.assert_not_called()


def _resolver(
    mode: str = "allow",
) -> MagicMock:
    resolver = MagicMock(
        spec=EnterpriseAuthorizationResolver,
    )

    def resolve(
        *,
        workspace_id: str,
        user_id: str,
        permission: EnterprisePermission,
    ) -> EnterpriseAuthorizationResolutionResult:
        assert user_id == ACTOR_USER_ID

        return _resolution(
            workspace_id=workspace_id,
            permission=permission,
            mode=mode,
        )

    resolver.resolve.side_effect = resolve

    return resolver
