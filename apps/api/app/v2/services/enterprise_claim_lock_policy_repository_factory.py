from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_claim_lock_policies import (
    EnterpriseWorkspaceClaimLockPolicyRepository,
    InMemoryEnterpriseWorkspaceClaimLockPolicyRepository,
    SQLiteEnterpriseWorkspaceClaimLockPolicyRepository,
)


class ExternalEnterpriseClaimLockPolicyPersistenceUnavailableError(
    RuntimeError,
):
    pass


def build_enterprise_claim_lock_policy_repository(
    settings: V2PersistenceSettings,
) -> EnterpriseWorkspaceClaimLockPolicyRepository:
    settings.validate()

    if settings.backend is PersistenceBackend.MEMORY:
        return InMemoryEnterpriseWorkspaceClaimLockPolicyRepository()

    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite enterprise claim lock policy persistence "
                "requires a database path."
            )

        return SQLiteEnterpriseWorkspaceClaimLockPolicyRepository(
            database_path=settings.sqlite_path,
        )

    if settings.backend is PersistenceBackend.EXTERNAL:
        raise (
            ExternalEnterpriseClaimLockPolicyPersistenceUnavailableError(
                "External enterprise claim lock policy persistence "
                "is configured but no external claim lock policy "
                "persistence adapter has been installed."
            )
        )

    raise RuntimeError(
        "Unsupported enterprise claim lock policy persistence backend."
    )
