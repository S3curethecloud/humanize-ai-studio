from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import pytest

from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
    ClaimLockOrigin,
    ClaimLockProvenance,
    ProtectedTerm,
)
from app.v2.domain.enterprise_claim_lock_policy import (
    EnterpriseClaimLockPolicyStatus,
    EnterpriseWorkspaceClaimLockPolicy,
)
from app.v2.repositories.enterprise_claim_lock_policies import (
    EnterpriseClaimLockPolicyAlreadyExistsError,
    EnterpriseClaimLockPolicyArchivedError,
    EnterpriseClaimLockPolicyIntegrityError,
    EnterpriseClaimLockPolicyNotFoundError,
    EnterpriseClaimLockPolicyRevisionConflictError,
    EnterpriseWorkspaceClaimLockPolicyRepository,
    InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
    SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
)

WORKSPACE_ID = "workspace_test"
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
    policy_id: str,
    revision: int,
) -> str:
    return (
        "workspace-claim-lock-policy:"
        f"{policy_id}:revision:{revision}"
    )


def _term(
    *,
    policy_id: str,
    revision: int,
    term_id: str = "term_product",
    text: str = "Humanize Enterprise",
) -> ProtectedTerm:
    return ProtectedTerm(
        term_id=term_id,
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
    policy_id: str = "policy_test",
    workspace_id: str = WORKSPACE_ID,
    status: EnterpriseClaimLockPolicyStatus = (
        EnterpriseClaimLockPolicyStatus.ACTIVE
    ),
    enforcement_mode: ClaimLockEnforcementMode = (
        ClaimLockEnforcementMode.STRICT
    ),
    revision: int = 1,
    created_by_user_id: str = "user_creator",
    created_at: datetime = CREATED_AT,
    updated_by_user_id: str = "user_editor",
    updated_at: datetime | None = None,
    term_text: str = "Humanize Enterprise",
) -> EnterpriseWorkspaceClaimLockPolicy:
    effective_updated_at = (
        updated_at
        if updated_at is not None
        else created_at + timedelta(minutes=revision)
    )

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
        created_by_user_id=created_by_user_id,
        created_at=created_at,
        updated_by_user_id=updated_by_user_id,
        updated_at=effective_updated_at,
        revision=revision,
    )


RepositoryFactory = Callable[
    [],
    EnterpriseWorkspaceClaimLockPolicyRepository,
]


@pytest.fixture(
    params=("memory", "sqlite"),
)
def repository_factory(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> RepositoryFactory:
    if request.param == "memory":
        return (
            InMemoryEnterpriseWorkspaceClaimLockPolicyRepository
        )

    database_path = tmp_path / "claim-lock.db"

    def build_sqlite(
    ) -> SQLiteEnterpriseWorkspaceClaimLockPolicyRepository:
        return (
            SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
                database_path=database_path,
            )
        )

    return build_sqlite


def test_create_and_resolve_current_policy(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    policy = _policy()

    assert repository.create(policy) == policy
    assert repository.get_by_id(policy.policy_id) == policy
    assert repository.get_for_workspace(WORKSPACE_ID) == policy


def test_missing_policy_returns_none(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    assert repository.get_by_id("missing") is None
    assert repository.get_for_workspace("missing") is None


def test_duplicate_policy_id_is_rejected(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    policy = _policy()

    repository.create(policy)

    with pytest.raises(
        EnterpriseClaimLockPolicyAlreadyExistsError,
    ):
        repository.create(policy)


def test_second_non_archived_policy_for_workspace_is_rejected(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    repository.create(
        _policy(
            policy_id="policy_one",
        )
    )

    with pytest.raises(
        EnterpriseClaimLockPolicyAlreadyExistsError,
    ):
        repository.create(
            _policy(
                policy_id="policy_two",
            )
        )


def test_archived_policy_cannot_be_created(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    with pytest.raises(
        EnterpriseClaimLockPolicyArchivedError,
    ):
        repository.create(
            _policy(
                status=(
                    EnterpriseClaimLockPolicyStatus.ARCHIVED
                ),
            )
        )


def test_policy_must_be_created_at_revision_one(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    with pytest.raises(
        EnterpriseClaimLockPolicyIntegrityError,
        match="revision 1",
    ):
        repository.create(
            _policy(
                revision=2,
            )
        )


def test_update_requires_existing_policy(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()

    with pytest.raises(
        EnterpriseClaimLockPolicyNotFoundError,
    ):
        repository.update(
            _policy(
                revision=2,
            ),
            expected_revision=1,
        )


def test_same_status_content_update_increments_revision(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    repository.create(_policy())

    updated = _policy(
        revision=2,
        term_text="Humanize Enterprise Claim Lock",
    )

    assert repository.update(
        updated,
        expected_revision=1,
    ) == updated

    assert repository.get_by_id("policy_test") == updated
    assert (
        repository.get_for_workspace(WORKSPACE_ID)
        == updated
    )


def test_update_rejects_stale_expected_revision(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    repository.create(_policy())

    with pytest.raises(
        EnterpriseClaimLockPolicyRevisionConflictError,
    ):
        repository.update(
            _policy(
                revision=2,
            ),
            expected_revision=7,
        )

    assert repository.get_by_id("policy_test").revision == 1


def test_update_requires_candidate_revision_plus_one(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    repository.create(_policy())

    with pytest.raises(
        EnterpriseClaimLockPolicyRevisionConflictError,
        match="plus one",
    ):
        repository.update(
            _policy(
                revision=3,
            ),
            expected_revision=1,
        )


def test_update_rejects_immutable_workspace_change(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    repository.create(_policy())

    candidate = _policy(
        workspace_id="workspace_other",
        revision=2,
    )

    with pytest.raises(
        EnterpriseClaimLockPolicyIntegrityError,
        match="workspace_id is immutable",
    ):
        repository.update(
            candidate,
            expected_revision=1,
        )


def test_active_disabled_active_lifecycle(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    repository.create(_policy())

    disabled = _policy(
        status=EnterpriseClaimLockPolicyStatus.DISABLED,
        revision=2,
    )

    repository.update(
        disabled,
        expected_revision=1,
    )

    active = _policy(
        status=EnterpriseClaimLockPolicyStatus.ACTIVE,
        revision=3,
    )

    repository.update(
        active,
        expected_revision=2,
    )

    assert (
        repository.get_for_workspace(WORKSPACE_ID).status
        is EnterpriseClaimLockPolicyStatus.ACTIVE
    )


def test_archived_policy_is_historical_and_terminal(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    repository.create(_policy())

    archived = _policy(
        status=EnterpriseClaimLockPolicyStatus.ARCHIVED,
        revision=2,
    )

    repository.update(
        archived,
        expected_revision=1,
    )

    assert repository.get_by_id("policy_test") == archived
    assert repository.get_for_workspace(WORKSPACE_ID) is None

    with pytest.raises(
        EnterpriseClaimLockPolicyArchivedError,
    ):
        repository.update(
            _policy(
                status=EnterpriseClaimLockPolicyStatus.ACTIVE,
                revision=3,
            ),
            expected_revision=2,
        )


def test_new_policy_allowed_after_archival(
    repository_factory: RepositoryFactory,
) -> None:
    repository = repository_factory()
    repository.create(
        _policy(
            policy_id="policy_old",
        )
    )

    repository.update(
        _policy(
            policy_id="policy_old",
            status=EnterpriseClaimLockPolicyStatus.ARCHIVED,
            revision=2,
        ),
        expected_revision=1,
    )

    new_policy = _policy(
        policy_id="policy_new",
        revision=1,
    )

    repository.create(new_policy)

    assert (
        repository.get_for_workspace(WORKSPACE_ID)
        == new_policy
    )
    assert (
        repository.get_by_id("policy_old").status
        is EnterpriseClaimLockPolicyStatus.ARCHIVED
    )


def test_memory_ambiguous_current_state_fails_closed() -> None:
    repository = (
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()
    )

    first = _policy(
        policy_id="policy_one",
    )
    second = _policy(
        policy_id="policy_two",
    )

    repository._policies = {
        first.policy_id: first,
        second.policy_id: second,
    }

    with pytest.raises(
        EnterpriseClaimLockPolicyIntegrityError,
        match="ambiguous",
    ):
        repository.get_for_workspace(WORKSPACE_ID)


def test_sqlite_survives_repository_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "restart.db"

    first = SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
        database_path=database_path,
    )
    policy = _policy()
    first.create(policy)

    second = SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
        database_path=database_path,
    )

    assert second.get_by_id(policy.policy_id) == policy
    assert second.get_for_workspace(WORKSPACE_ID) == policy


def test_sqlite_normalizes_timestamps_to_utc(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "utc.db"
    repository = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )

    plus_two = timezone(timedelta(hours=2))
    created_at = datetime(
        2026,
        8,
        23,
        22,
        0,
        tzinfo=plus_two,
    )

    repository.create(
        _policy(
            created_at=created_at,
        )
    )

    connection = sqlite3.connect(database_path)

    try:
        row = connection.execute(
            """
            SELECT created_at, updated_at, payload
            FROM enterprise_workspace_claim_lock_policies
            WHERE policy_id = ?
            """,
            ("policy_test",),
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row[0].endswith("+00:00")
    assert row[1].endswith("+00:00")
    assert '"created_at":"2026-08-23T20:00:00Z"' in row[2]


def test_sqlite_payload_column_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "integrity.db"
    repository = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )
    repository.create(_policy())

    connection = sqlite3.connect(database_path)

    try:
        connection.execute(
            """
            UPDATE enterprise_workspace_claim_lock_policies
            SET enforcement_mode = 'audit_only'
            WHERE policy_id = ?
            """,
            ("policy_test",),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        EnterpriseClaimLockPolicyIntegrityError,
        match="integrity mismatch",
    ):
        repository.get_by_id("policy_test")


def test_sqlite_concurrent_updates_have_one_winner(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "concurrency.db"

    initial_repository = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )
    initial_repository.create(_policy())

    first_candidate = _policy(
        revision=2,
        enforcement_mode=ClaimLockEnforcementMode.AUDIT_ONLY,
        updated_by_user_id="user_first",
    )
    second_candidate = _policy(
        revision=2,
        term_text="Second candidate",
        updated_by_user_id="user_second",
    )

    def attempt(
        candidate: EnterpriseWorkspaceClaimLockPolicy,
    ) -> str:
        repository = (
            SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
                database_path=database_path,
            )
        )

        try:
            repository.update(
                candidate,
                expected_revision=1,
            )
        except EnterpriseClaimLockPolicyRevisionConflictError:
            return "conflict"

        return "success"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                attempt,
                (
                    first_candidate,
                    second_candidate,
                ),
            )
        )

    assert sorted(results) == [
        "conflict",
        "success",
    ]

    final_repository = (
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=database_path,
        )
    )
    final_policy = final_repository.get_by_id(
        "policy_test"
    )

    assert final_policy is not None
    assert final_policy.revision == 2
    assert final_policy.updated_by_user_id in {
        "user_first",
        "user_second",
    }
