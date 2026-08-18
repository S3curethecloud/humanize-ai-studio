from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_admin_audit import (
    EnterpriseAdminAuditRepository,
    InMemoryEnterpriseAdminAuditRepository,
    SQLiteEnterpriseAdminAuditRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingService,
)
from app.v2.services.enterprise_admin_audit_runtime import (
    EnterpriseAdminAuditRuntime,
)


class ExternalEnterpriseAdminAuditPersistenceUnavailableError(
    RuntimeError
):
    pass


def build_enterprise_admin_audit_runtime(
    settings: V2PersistenceSettings,
) -> EnterpriseAdminAuditRuntime:
    settings.validate()

    repository: EnterpriseAdminAuditRepository

    if settings.backend is PersistenceBackend.MEMORY:
        repository = (
            InMemoryEnterpriseAdminAuditRepository()
        )

    elif settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite persistence requires a database path."
            )

        repository = (
            SQLiteEnterpriseAdminAuditRepository(
                database_path=settings.sqlite_path,
            )
        )

    else:
        raise (
            ExternalEnterpriseAdminAuditPersistenceUnavailableError(
                "External enterprise admin audit persistence "
                "is configured but no adapter has been installed."
            )
        )

    recording = EnterpriseAdminAuditRecordingService(
        repository=repository,
    )

    return EnterpriseAdminAuditRuntime(
        repository=repository,
        recording=recording,
    )
