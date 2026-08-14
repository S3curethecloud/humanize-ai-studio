from __future__ import annotations

from app.domain.models import RewriteRequest
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
)
from app.v2.services.enterprise_quota_enforcement_service import (
    EnterpriseQuotaEnforcementResult,
    EnterpriseQuotaEnforcementService,
)
from app.v2.services.enterprise_quota_runtime_context_service import (
    EnterpriseQuotaRuntimeContextService,
)
from app.v2.services.enterprise_single_rewrite_quota_admission_service import (
    EnterpriseQuotaAdmissionDeniedError,
)


class EnterpriseLongDocumentQuotaAdmissionService:
    def __init__(
        self,
        *,
        runtime_context: EnterpriseQuotaRuntimeContextService,
        enforcement: EnterpriseQuotaEnforcementService,
    ) -> None:
        self._runtime_context = runtime_context
        self._enforcement = enforcement

    def admit(
        self,
        *,
        workspace_id: str,
        request: RewriteRequest,
        section_count: int,
    ) -> EnterpriseQuotaEnforcementResult:
        context = self._runtime_context.resolve(
            workspace_id=workspace_id,
            operation=EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
        )

        result = self._enforcement.enforce(
            workspace_id=workspace_id,
            operation=EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
            window=context.window,
            accounting_group_id=context.accounting_group_id,
            requested_quantities={
                EnterpriseQuotaDimension.REWRITE_REQUESTS: 1,
                EnterpriseQuotaDimension.INPUT_CHARACTERS: len(request.text),
                EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS: section_count,
            },
            occurred_at=context.occurred_at,
        )

        if not result.allowed:
            raise EnterpriseQuotaAdmissionDeniedError(result)

        return result
