from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditEvent,
    EnterpriseAdminAuditOutcome,
)


class EnterpriseAdminAuditWriter(Protocol):
    def create(
        self,
        event: EnterpriseAdminAuditEvent,
    ) -> EnterpriseAdminAuditEvent: ...


class EnterpriseAdminAuditRecordingIntegrityError(
    RuntimeError
):
    pass


@dataclass(frozen=True, slots=True)
class EnterpriseAdminAuditRecordInput:
    workspace_id: str
    actor_user_id: str
    action: EnterpriseAdminAuditAction
    outcome: EnterpriseAdminAuditOutcome
    target_type: str | None = None
    target_id: str | None = None
    failure_reason: str | None = None


class EnterpriseAdminAuditRecordingService:
    def __init__(
        self,
        *,
        repository: EnterpriseAdminAuditWriter,
        event_id_factory: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._event_id_factory = (
            event_id_factory
            or _default_event_id
        )
        self._clock = clock or _utc_now

    def build_event(
        self,
        command: EnterpriseAdminAuditRecordInput,
    ) -> EnterpriseAdminAuditEvent:
        return EnterpriseAdminAuditEvent(
            audit_event_id=self._event_id_factory(),
            workspace_id=command.workspace_id,
            actor_user_id=command.actor_user_id,
            action=command.action,
            outcome=command.outcome,
            target_type=command.target_type,
            target_id=command.target_id,
            occurred_at=self._clock(),
            failure_reason=command.failure_reason,
        )

    def record(
        self,
        command: EnterpriseAdminAuditRecordInput,
    ) -> EnterpriseAdminAuditEvent:
        event = self.build_event(command)

        persisted = self._repository.create(event)

        if persisted != event:
            raise EnterpriseAdminAuditRecordingIntegrityError(
                "enterprise admin audit repository returned "
                "an event different from the event supplied "
                "for persistence"
            )

        return persisted


def _default_event_id() -> str:
    return (
        "enterprise_admin_audit_"
        f"{uuid4().hex}"
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
