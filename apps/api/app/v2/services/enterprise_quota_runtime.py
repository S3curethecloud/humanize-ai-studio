from __future__ import annotations

from dataclasses import dataclass

from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_quota_enforcement_service import (
    EnterpriseQuotaEnforcementService,
)
from app.v2.services.enterprise_quota_runtime_context_service import (
    EnterpriseQuotaRuntimeContextService,
)


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseQuotaRuntime:
    limits: EnterpriseQuotaLimitRepository
    runtime_context: EnterpriseQuotaRuntimeContextService
    enforcement: EnterpriseQuotaEnforcementService
