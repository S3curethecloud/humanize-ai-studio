from __future__ import annotations

from dataclasses import dataclass

from app.v2.repositories.enterprise_admin_audit import (
    EnterpriseAdminAuditRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingService,
)


@dataclass(frozen=True, slots=True)
class EnterpriseAdminAuditRuntime:
    repository: EnterpriseAdminAuditRepository
    recording: EnterpriseAdminAuditRecordingService
