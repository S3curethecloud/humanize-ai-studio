from __future__ import annotations

from dataclasses import dataclass

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.interfaces import (
    MembershipRepository,
    RewriteHistoryRepository,
    UserRepository,
    VoiceProfileRepository,
    WorkspaceRepository,
)
from app.v2.repositories.memory import (
    InMemoryMembershipRepository,
    InMemoryRewriteHistoryRepository,
    InMemoryUserRepository,
    InMemoryVoiceProfileRepository,
    InMemoryWorkspaceRepository,
)
from app.v2.repositories.sqlite import (
    SQLiteMembershipRepository,
    SQLiteRewriteHistoryRepository,
    SQLiteUserRepository,
    SQLiteVoiceProfileRepository,
    SQLiteWorkspaceRepository,
)
from app.v2.repositories.unit_of_work import (
    SQLiteUnitOfWork,
)
from app.v2.repositories.uow_interfaces import (
    UnitOfWork,
)


class ExternalPersistenceUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepositoryBundle:
    users: UserRepository
    workspaces: WorkspaceRepository
    memberships: MembershipRepository
    history: RewriteHistoryRepository
    voice_profiles: VoiceProfileRepository


def build_repository_bundle(
    settings: V2PersistenceSettings,
) -> RepositoryBundle:
    if settings.backend is PersistenceBackend.MEMORY:
        return RepositoryBundle(
            users=InMemoryUserRepository(),
            workspaces=(InMemoryWorkspaceRepository()),
            memberships=(InMemoryMembershipRepository()),
            history=(InMemoryRewriteHistoryRepository()),
            voice_profiles=(InMemoryVoiceProfileRepository()),
        )

    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError("SQLite persistence requires a database path.")

        return RepositoryBundle(
            users=SQLiteUserRepository(settings.sqlite_path),
            workspaces=SQLiteWorkspaceRepository(settings.sqlite_path),
            memberships=(SQLiteMembershipRepository(settings.sqlite_path)),
            history=(SQLiteRewriteHistoryRepository(settings.sqlite_path)),
            voice_profiles=(SQLiteVoiceProfileRepository(settings.sqlite_path)),
        )

    raise ExternalPersistenceUnavailableError(
        "External V2 persistence is configured "
        "but no production database adapter "
        "has been installed."
    )


def build_unit_of_work(
    settings: V2PersistenceSettings,
) -> UnitOfWork:
    if settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError("SQLite persistence requires a database path.")

        return SQLiteUnitOfWork(settings.sqlite_path)

    if settings.backend is PersistenceBackend.EXTERNAL:
        raise ExternalPersistenceUnavailableError(
            "External V2 persistence is configured "
            "but no production database adapter "
            "has been installed."
        )

    raise ExternalPersistenceUnavailableError(
        "The in-memory persistence backend does "
        "not provide a transactional production "
        "unit of work."
    )
