from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_claim_lock_policies import (
    InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
    SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
)
from app.v2.repositories.enterprise_claim_lock_policy_admin_mutations import (
    InMemoryEnterpriseClaimLockPolicyAdminMutationRepository,
    SQLiteEnterpriseClaimLockPolicyAdminMutationRepository,
)
from app.v2.services.enterprise_claim_lock_policy_repository_factory import (
    ExternalEnterpriseClaimLockPolicyPersistenceUnavailableError,
    build_enterprise_claim_lock_policy_repository,
)


def _memory_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _sqlite_settings(
    database_path: Path,
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=database_path,
        database_url=None,
    )


def _external_settings() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url="postgresql://example.invalid/humanize",
    )


def test_factory_builds_memory_claim_lock_policy_repository() -> None:
    repository = build_enterprise_claim_lock_policy_repository(
        _memory_settings()
    )

    assert isinstance(
        repository,
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
    )


def test_factory_builds_sqlite_claim_lock_policy_repository_on_exact_path(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "claim-lock-policy.db"

    repository = build_enterprise_claim_lock_policy_repository(
        _sqlite_settings(database_path)
    )

    assert isinstance(
        repository,
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
    )
    assert repository._database_path == database_path


def test_factory_validates_sqlite_settings_before_repository_selection() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=None,
        database_url=None,
    )

    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_SQLITE_PATH is required",
    ):
        build_enterprise_claim_lock_policy_repository(settings)


def test_factory_validates_external_settings_before_adapter_resolution() -> None:
    settings = V2PersistenceSettings(
        backend=PersistenceBackend.EXTERNAL,
        sqlite_path=None,
        database_url=None,
    )

    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_DATABASE_URL is required",
    ):
        build_enterprise_claim_lock_policy_repository(settings)


def test_factory_external_backend_fails_closed_without_adapter() -> None:
    with pytest.raises(
        ExternalEnterpriseClaimLockPolicyPersistenceUnavailableError,
        match=(
            "no external claim lock policy "
            "persistence adapter has been installed"
        ),
    ):
        build_enterprise_claim_lock_policy_repository(
            _external_settings()
        )


def test_memory_v2_services_reuse_exact_claim_lock_authorities() -> None:
    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_memory_settings(),
    )

    policies = services.enterprise_claim_lock_policies
    mutations = (
        services.enterprise_claim_lock_policy_admin_mutations
    )
    admin = services.claim_lock_admin

    assert isinstance(
        policies,
        InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
    )
    assert isinstance(
        mutations,
        InMemoryEnterpriseClaimLockPolicyAdminMutationRepository,
    )

    assert admin._policies is policies
    assert admin._atomic_mutations is mutations

    assert (
        admin._authorization_resolver
        is services.enterprise_authorization.authorization_resolver
    )
    assert (
        admin._audit_recording
        is services.enterprise_admin_audit.recording
    )

    assert mutations._policies is policies
    assert (
        mutations._audit
        is services.enterprise_admin_audit.repository
    )


def test_sqlite_v2_services_share_exact_claim_lock_transaction_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "claim-lock-composition.db"

    services = V2Services(
        workflow=MagicMock(),
        persistence_settings=_sqlite_settings(database_path),
    )

    policies = services.enterprise_claim_lock_policies
    mutations = (
        services.enterprise_claim_lock_policy_admin_mutations
    )
    admin = services.claim_lock_admin

    assert isinstance(
        policies,
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
    )
    assert isinstance(
        mutations,
        SQLiteEnterpriseClaimLockPolicyAdminMutationRepository,
    )

    assert admin._policies is policies
    assert admin._atomic_mutations is mutations

    assert (
        admin._authorization_resolver
        is services.enterprise_authorization.authorization_resolver
    )
    assert (
        admin._audit_recording
        is services.enterprise_admin_audit.recording
    )

    assert policies._database_path == database_path
    assert (
        services.enterprise_admin_audit.repository._database_path
        == database_path
    )
    assert mutations._database_path == database_path


def test_sqlite_claim_lock_policy_authority_persists_across_composition(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "claim-lock-recompose.db"
    settings = _sqlite_settings(database_path)

    first = V2Services(
        workflow=MagicMock(),
        persistence_settings=settings,
    )

    assert isinstance(
        first.enterprise_claim_lock_policies,
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
    )

    first_repository_path = (
        first.enterprise_claim_lock_policies._database_path
    )

    second = V2Services(
        workflow=MagicMock(),
        persistence_settings=settings,
    )

    assert isinstance(
        second.enterprise_claim_lock_policies,
        SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
    )

    assert first_repository_path == database_path
    assert (
        second.enterprise_claim_lock_policies._database_path
        == database_path
    )
    assert (
        second.enterprise_claim_lock_policy_admin_mutations
        ._database_path
        == database_path
    )
    assert (
        second.enterprise_admin_audit.repository._database_path
        == database_path
    )
