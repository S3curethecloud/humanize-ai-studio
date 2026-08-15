from __future__ import annotations

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.repositories.enterprise_quota import (
    EnterpriseQuotaAccountingRepository,
    InMemoryEnterpriseQuotaAccountingRepository,
    SQLiteEnterpriseQuotaAccountingRepository,
)
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
    InMemoryEnterpriseQuotaLimitRepository,
    SQLiteEnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_quota_decision_service import (
    EnterpriseQuotaDecisionService,
)
from app.v2.services.enterprise_quota_enforcement_service import (
    EnterpriseQuotaEnforcementService,
)
from app.v2.services.enterprise_quota_runtime import (
    EnterpriseQuotaRuntime,
)
from app.v2.services.enterprise_quota_runtime_context_service import (
    EnterpriseQuotaRuntimeContextService,
)


class ExternalEnterpriseQuotaPersistenceUnavailableError(
    RuntimeError,
):
    pass


def build_enterprise_quota_runtime(
    settings: V2PersistenceSettings,
) -> EnterpriseQuotaRuntime:
    settings.validate()

    accounting: EnterpriseQuotaAccountingRepository
    limits: EnterpriseQuotaLimitRepository

    if settings.backend is PersistenceBackend.MEMORY:
        accounting = InMemoryEnterpriseQuotaAccountingRepository()
        limits = InMemoryEnterpriseQuotaLimitRepository()

    elif settings.backend is PersistenceBackend.SQLITE:
        if settings.sqlite_path is None:
            raise ValueError(
                "SQLite enterprise quota persistence requires "
                "a database path."
            )

        accounting = SQLiteEnterpriseQuotaAccountingRepository(
            database_path=settings.sqlite_path,
        )
        limits = SQLiteEnterpriseQuotaLimitRepository(
            database_path=settings.sqlite_path,
        )

    elif settings.backend is PersistenceBackend.EXTERNAL:
        raise ExternalEnterpriseQuotaPersistenceUnavailableError(
            "External enterprise quota persistence is configured "
            "but no external quota persistence adapter "
            "has been installed."
        )

    else:
        raise RuntimeError(
            "Unsupported enterprise quota persistence backend."
        )

    decision_service = EnterpriseQuotaDecisionService()

    runtime_context = EnterpriseQuotaRuntimeContextService(
        limits=limits,
    )

    enforcement = EnterpriseQuotaEnforcementService(
        accounting=accounting,
        limits=limits,
        decision_service=decision_service,
    )

    return EnterpriseQuotaRuntime(
        limits=limits,
        runtime_context=runtime_context,
        enforcement=enforcement,
    )
