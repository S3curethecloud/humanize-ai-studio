from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.v2.domain.enterprise_admin_audit import (
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditEvent,
    EnterpriseAdminAuditOutcome,
)
from app.v2.repositories.enterprise_admin_audit import (
    InMemoryEnterpriseAdminAuditRepository,
)
from app.v2.services.enterprise_admin_audit_recording_service import (
    EnterpriseAdminAuditRecordingIntegrityError,
    EnterpriseAdminAuditRecordingService,
    EnterpriseAdminAuditRecordInput,
)

FIXED_TIME = datetime(
    2026,
    8,
    15,
    12,
    30,
    tzinfo=UTC,
)


def _command(
    *,
    outcome: EnterpriseAdminAuditOutcome = (
        EnterpriseAdminAuditOutcome.SUCCEEDED
    ),
    failure_reason: str | None = None,
) -> EnterpriseAdminAuditRecordInput:
    return EnterpriseAdminAuditRecordInput(
        workspace_id="workspace_1",
        actor_user_id="user_admin",
        action=(
            EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
        ),
        outcome=outcome,
        target_type="quota_limit",
        target_id="limit_requests",
        failure_reason=failure_reason,
    )


def test_record_persists_exact_event() -> None:
    repository = (
        InMemoryEnterpriseAdminAuditRepository()
    )
    service = EnterpriseAdminAuditRecordingService(
        repository=repository,
        event_id_factory=lambda: "audit_1",
        clock=lambda: FIXED_TIME,
    )

    event = service.record(_command())

    assert event == EnterpriseAdminAuditEvent(
        audit_event_id="audit_1",
        workspace_id="workspace_1",
        actor_user_id="user_admin",
        action=(
            EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
        ),
        outcome=EnterpriseAdminAuditOutcome.SUCCEEDED,
        target_type="quota_limit",
        target_id="limit_requests",
        occurred_at=FIXED_TIME,
    )

    assert repository.get("audit_1") == event


def test_record_calls_clock_once() -> None:
    repository = (
        InMemoryEnterpriseAdminAuditRepository()
    )
    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return FIXED_TIME

    service = EnterpriseAdminAuditRecordingService(
        repository=repository,
        event_id_factory=lambda: "audit_1",
        clock=clock,
    )

    service.record(_command())

    assert calls == 1


def test_record_denied_event() -> None:
    repository = (
        InMemoryEnterpriseAdminAuditRepository()
    )
    service = EnterpriseAdminAuditRecordingService(
        repository=repository,
        event_id_factory=lambda: "audit_denied",
        clock=lambda: FIXED_TIME,
    )

    event = service.record(
        _command(
            outcome=(
                EnterpriseAdminAuditOutcome.DENIED
            ),
            failure_reason="authorization_denied",
        )
    )

    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.DENIED
    )
    assert (
        event.failure_reason
        == "authorization_denied"
    )


def test_record_validation_remains_domain_authoritative() -> None:
    repository = (
        InMemoryEnterpriseAdminAuditRepository()
    )
    service = EnterpriseAdminAuditRecordingService(
        repository=repository,
        event_id_factory=lambda: "audit_invalid",
        clock=lambda: FIXED_TIME,
    )

    with pytest.raises(
        ValueError,
        match="requires failure_reason",
    ):
        service.record(
            _command(
                outcome=(
                    EnterpriseAdminAuditOutcome.FAILED
                ),
            )
        )


def test_repository_result_must_match_exact_event() -> None:
    class CorruptingRepository:
        def create(
            self,
            event: EnterpriseAdminAuditEvent,
        ) -> EnterpriseAdminAuditEvent:
            return event.model_copy(
                update={
                    "workspace_id": "workspace_other",
                }
            )

    service = EnterpriseAdminAuditRecordingService(
        repository=CorruptingRepository(),
        event_id_factory=lambda: "audit_1",
        clock=lambda: FIXED_TIME,
    )

    with pytest.raises(
        EnterpriseAdminAuditRecordingIntegrityError,
        match="different from the event supplied",
    ):
        service.record(_command())
