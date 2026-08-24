from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
)
from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditEvent,
    EnterpriseAdminAuditOutcome,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)
from app.v2.repositories.enterprise_admin_audit import (
    InMemoryEnterpriseAdminAuditRepository,
    SQLiteEnterpriseAdminAuditRepository,
)
from app.v2.repositories.enterprise_claim_lock_policies import (
    EnterpriseClaimLockPolicyAlreadyExistsError,
    EnterpriseClaimLockPolicyRevisionConflictError,
    InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
    SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
)
from app.v2.repositories.enterprise_claim_lock_policy_admin_mutations import (
    EnterpriseClaimLockPolicyAdminMutationConfigurationError,
    InMemoryEnterpriseClaimLockPolicyAdminMutationRepository,
    SQLiteEnterpriseClaimLockPolicyAdminMutationRepository,
    build_enterprise_claim_lock_policy_admin_mutation_repository,
)

WORKSPACE_ID = "workspace_test"
POLICY_ID = "policy_test"
CREATED_AT = datetime(
    2026,
    8,
    23,
    20,
    0,
    tzinfo=UTC,
)


def _source_reference(
    *,
    policy_id: str = POLICY_ID,
    revision: int,
) -> str:
    return (
        "workspace-claim-lock-policy:"
        f"{policy_id}:revision:{revision}"
    )


def _term(
    *,
    policy_id: str = POLICY_ID,
    revision: int,
    text: str = "Humanize Enterprise",
) -> ProtectedTerm:
    return ProtectedTerm(
        term_id="term_product",
        text=text,
        case_sensitive=True,
        provenance=ClaimLockProvenance(
            origin=ClaimLockOrigin.WORKSPACE,
            source_reference=_source_reference(
                policy_id=policy_id,
                revision=revision,
            ),
        ),
    )


def _policy(
    *,
    policy_id: str = POLICY_ID,
    workspace_id: str = WORKSPACE_ID,
    revision: int = 1,
    status: EnterpriseClaimLockPolicyStatus = (
        EnterpriseClaimLockPolicyStatus.ACTIVE
    ),
    enforcement_mode: ClaimLockEnforcementMode = (
        ClaimLockEnforcementMode.STRICT
    ),
    updated_by_user_id: str = "user_admin",
    term_text: str = "Humanize Enterprise",
) -> EnterpriseWorkspaceClaimLockPolicy:
    return EnterpriseWorkspaceClaimLockPolicy(
        policy_id=policy_id,
        workspace_id=workspace_id,
        status=status,
        enforcement_mode=enforcement_mode,
        protected_terms=(
            _term(
                policy_id=policy_id,
                revision=revision,
                text=term_text,
            ),
        ),
        created_by_user_id="user_creator",
        created_at=CREATED_AT,
        updated_by_user_id=updated_by_user_id,
        updated_at=(
            CREATED_AT + timedelta(minutes=revision)
        ),
        revision=revision,
    )


def _audit_event(
    *,
    audit_event_id: str,
    action: EnterpriseAdminAuditAction,
    policy: EnterpriseWorkspaceClaimLockPolicy,
    outcome: EnterpriseAdminAuditOutcome = (
        EnterpriseAdminAuditOutcome.SUCCEEDED
    ),
    target_type: str = "claim_lock_policy",
    target_id: str | None = None,
    workspace_id: str | None = None,
) -> EnterpriseAdminAuditEvent:
    return EnterpriseAdminAuditEvent(
        audit_event_id=audit_event_id,
        workspace_id=(
            workspace_id
            if workspace_id is not None
            else policy.workspace_id
        ),
        actor_user_id="user_admin",
        action=action,
        outcome=outcome,
        target_type=target_type,
        target_id=(
            target_id
            if target_id is not None
            else policy.policy_id
        ),
        occurred_at=CREATED_AT + timedelta(hours=1),
        failure_reason=(
            None
            if outcome is EnterpriseAdminAuditOutcome.SUCCEEDED
            else "expected test failure"
        ),
    )


def test_memory_create_commits_policy_and_audit() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policy = _policy()
    event = _audit_event(
        audit_event_id="audit_create",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_CREATE
        ),
        policy=policy,
    )

    assert mutations.create_policy_with_audit(
        policy=policy,
        audit_event=event,
    ) == policy

    assert policies.get_by_id(POLICY_ID) == policy
    assert audit.get("audit_create") == event


def test_memory_create_audit_collision_commits_neither() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policy = _policy()
    event = _audit_event(
        audit_event_id="audit_create",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_CREATE
        ),
        policy=policy,
    )

    audit.create(event)

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        mutations.create_policy_with_audit(
            policy=policy,
            audit_event=event,
        )

    assert policies.get_by_id(POLICY_ID) is None
    assert audit.get("audit_create") == event


def test_memory_duplicate_policy_commits_no_audit() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policy = _policy()
    policies.create(policy)

    event = _audit_event(
        audit_event_id="audit_duplicate",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_CREATE
        ),
        policy=policy,
    )

    with pytest.raises(
        EnterpriseClaimLockPolicyAlreadyExistsError,
    ):
        mutations.create_policy_with_audit(
            policy=policy,
            audit_event=event,
        )

    assert audit.get("audit_duplicate") is None


def test_memory_update_commits_policy_and_audit() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policies.create(_policy())

    updated = _policy(
        revision=2,
        term_text="Claim Lock Enterprise",
    )

    event = _audit_event(
        audit_event_id="audit_update",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_UPDATE
        ),
        policy=updated,
    )

    assert mutations.update_policy_with_audit(
        policy=updated,
        expected_revision=1,
        audit_event=event,
    ) == updated

    assert policies.get_by_id(POLICY_ID) == updated
    assert audit.get("audit_update") == event


@pytest.mark.parametrize(
    ("status", "action"),
    (
        (
            EnterpriseClaimLockPolicyStatus.DISABLED,
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_DISABLE,
        ),
        (
            EnterpriseClaimLockPolicyStatus.ARCHIVED,
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_ARCHIVE,
        ),
    ),
)
def test_memory_lifecycle_actions_use_update_primitive(
    status: EnterpriseClaimLockPolicyStatus,
    action: EnterpriseAdminAuditAction,
) -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policies.create(_policy())

    updated = _policy(
        revision=2,
        status=status,
    )
    event = _audit_event(
        audit_event_id=f"audit_{action.value}",
        action=action,
        policy=updated,
    )

    mutations.update_policy_with_audit(
        policy=updated,
        expected_revision=1,
        audit_event=event,
    )

    assert policies.get_by_id(POLICY_ID) == updated
    assert audit.get(event.audit_event_id) == event


def test_memory_enable_action_is_accepted() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policies.create(
        _policy(
            status=EnterpriseClaimLockPolicyStatus.DISABLED,
        )
    )

    enabled = _policy(
        revision=2,
        status=EnterpriseClaimLockPolicyStatus.ACTIVE,
    )
    event = _audit_event(
        audit_event_id="audit_enable",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_ENABLE
        ),
        policy=enabled,
    )

    mutations.update_policy_with_audit(
        policy=enabled,
        expected_revision=1,
        audit_event=event,
    )

    assert policies.get_by_id(POLICY_ID) == enabled
    assert audit.get("audit_enable") == event


def test_update_revision_conflict_commits_no_audit() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    initial = _policy()
    policies.create(initial)

    updated = _policy(
        revision=2,
    )
    event = _audit_event(
        audit_event_id="audit_conflict",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_UPDATE
        ),
        policy=updated,
    )

    with pytest.raises(
        EnterpriseClaimLockPolicyRevisionConflictError,
    ):
        mutations.update_policy_with_audit(
            policy=updated,
            expected_revision=9,
            audit_event=event,
        )

    assert policies.get_by_id(POLICY_ID) == initial
    assert audit.get("audit_conflict") is None


def test_create_rejects_wrong_audit_action() -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policy = _policy()
    event = _audit_event(
        audit_event_id="audit_wrong",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_UPDATE
        ),
        policy=policy,
    )

    with pytest.raises(
        ValueError,
        match="CLAIM_LOCK_POLICY_CREATE",
    ):
        mutations.create_policy_with_audit(
            policy=policy,
            audit_event=event,
        )

    assert policies.get_by_id(POLICY_ID) is None
    assert audit.get("audit_wrong") is None


@pytest.mark.parametrize(
    "bad_field",
    (
        "outcome",
        "workspace",
        "target_type",
        "target_id",
    ),
)
def test_create_rejects_invalid_audit_semantics(
    bad_field: str,
) -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = InMemoryEnterpriseAdminAuditRepository()
    mutations = (
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policy = _policy()

    kwargs: dict[str, object] = {}

    if bad_field == "outcome":
        kwargs["outcome"] = EnterpriseAdminAuditOutcome.FAILED
    elif bad_field == "workspace":
        kwargs["workspace_id"] = "workspace_other"
    elif bad_field == "target_type":
        kwargs["target_type"] = "quota_limit"
    elif bad_field == "target_id":
        kwargs["target_id"] = "policy_other"

    event = _audit_event(
        audit_event_id=f"audit_{bad_field}",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_CREATE
        ),
        policy=policy,
        **kwargs,
    )

    with pytest.raises(ValueError):
        mutations.create_policy_with_audit(
            policy=policy,
            audit_event=event,
        )

    assert policies.get_by_id(POLICY_ID) is None
    assert audit.get(event.audit_event_id) is None


def test_builder_rejects_mixed_backends(
    tmp_path: Path,
) -> None:
    policies = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=tmp_path / "audit.db",
    )

    with pytest.raises(
        EnterpriseClaimLockPolicyAdminMutationConfigurationError,
        match="compatible",
    ):
        build_enterprise_claim_lock_policy_admin_mutation_repository(
            policies=policies,
            audit=audit,
        )


def test_sqlite_requires_same_database(
    tmp_path: Path,
) -> None:
    policies = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=tmp_path / "policies.db",
        )
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=tmp_path / "audit.db",
    )

    with pytest.raises(
        EnterpriseClaimLockPolicyAdminMutationConfigurationError,
        match="same SQLite database",
    ):
        SQLiteEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )


def test_sqlite_create_commits_policy_and_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v2.db"

    policies = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    mutations = (
        SQLiteEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policy = _policy()
    event = _audit_event(
        audit_event_id="audit_create",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_CREATE
        ),
        policy=policy,
    )

    mutations.create_policy_with_audit(
        policy=policy,
        audit_event=event,
    )

    assert policies.get_by_id(POLICY_ID) == policy
    assert audit.get("audit_create") == event


def test_sqlite_audit_collision_rolls_back_policy(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "rollback.db"

    policies = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    mutations = (
        SQLiteEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    policy = _policy()
    event = _audit_event(
        audit_event_id="audit_collision",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_CREATE
        ),
        policy=policy,
    )

    audit.create(event)

    with pytest.raises(Exception):
        mutations.create_policy_with_audit(
            policy=policy,
            audit_event=event,
        )

    assert policies.get_by_id(POLICY_ID) is None
    assert audit.get("audit_collision") == event


def test_sqlite_update_audit_collision_rolls_back_policy(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "update-rollback.db"

    policies = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )
    audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )
    mutations = (
        SQLiteEnterpriseClaimLockPolicyAdminMutationRepository(
            policies=policies,
            audit=audit,
        )
    )

    initial = _policy()
    policies.create(initial)

    updated = _policy(
        revision=2,
        term_text="Updated Enterprise",
    )
    event = _audit_event(
        audit_event_id="audit_update_collision",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_UPDATE
        ),
        policy=updated,
    )

    audit.create(event)

    with pytest.raises(Exception):
        mutations.update_policy_with_audit(
            policy=updated,
            expected_revision=1,
            audit_event=event,
        )

    assert policies.get_by_id(POLICY_ID) == initial
    assert audit.get("audit_update_collision") == event


def test_sqlite_concurrent_updates_have_one_success_audit(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "concurrency.db"

    initial_policies = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )
    initial_audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )

    initial_policies.create(_policy())

    first = _policy(
        revision=2,
        updated_by_user_id="user_first",
        term_text="First update",
    )
    second = _policy(
        revision=2,
        updated_by_user_id="user_second",
        term_text="Second update",
    )

    first_event = _audit_event(
        audit_event_id="audit_first",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_UPDATE
        ),
        policy=first,
    )
    second_event = _audit_event(
        audit_event_id="audit_second",
        action=(
            EnterpriseAdminAuditAction.CLAIM_LOCK_POLICY_UPDATE
        ),
        policy=second,
    )

    def attempt(
        item: tuple[
            EnterpriseWorkspaceClaimLockPolicy,
            EnterpriseAdminAuditEvent,
        ],
    ) -> str:
        policy, event = item

        policies = (
            SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
                database_path=database_path,
            )
        )
        audit = SQLiteEnterpriseAdminAuditRepository(
            database_path=database_path,
        )
        mutations = (
            SQLiteEnterpriseClaimLockPolicyAdminMutationRepository(
                policies=policies,
                audit=audit,
            )
        )

        try:
            mutations.update_policy_with_audit(
                policy=policy,
                expected_revision=1,
                audit_event=event,
            )
        except EnterpriseClaimLockPolicyRevisionConflictError:
            return "conflict"

        return "success"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                attempt,
                (
                    (first, first_event),
                    (second, second_event),
                ),
            )
        )

    assert sorted(results) == [
        "conflict",
        "success",
    ]

    final_policies = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )
    final_audit = SQLiteEnterpriseAdminAuditRepository(
        database_path=database_path,
    )

    final_policy = final_policies.get_by_id(POLICY_ID)

    assert final_policy is not None
    assert final_policy.revision == 2

    audit_results = (
        final_audit.get("audit_first"),
        final_audit.get("audit_second"),
    )

    assert sum(
        event is not None
        for event in audit_results
    ) == 1
