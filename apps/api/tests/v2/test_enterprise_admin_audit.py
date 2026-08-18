from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.v2.domain.enterprise_admin_audit import (
    ENTERPRISE_ADMIN_AUDIT_VERSION,
    EnterpriseAdminAuditAction,
    EnterpriseAdminAuditEvent,
    EnterpriseAdminAuditOutcome,
)


def _event(
    *,
    outcome: EnterpriseAdminAuditOutcome = (
        EnterpriseAdminAuditOutcome.SUCCEEDED
    ),
    failure_reason: str | None = None,
    target_type: str | None = "quota_limit",
    target_id: str | None = "limit_requests",
    occurred_at: datetime | None = None,
) -> EnterpriseAdminAuditEvent:
    return EnterpriseAdminAuditEvent(
        audit_event_id="audit_1",
        workspace_id="workspace_1",
        actor_user_id="user_1",
        action=(
            EnterpriseAdminAuditAction.QUOTA_LIMIT_CREATE
        ),
        outcome=outcome,
        target_type=target_type,
        target_id=target_id,
        occurred_at=(
            occurred_at
            or datetime(
                2026,
                8,
                15,
                tzinfo=UTC,
            )
        ),
        failure_reason=failure_reason,
    )


def test_audit_version_is_stable() -> None:
    event = _event()

    assert event.audit_version == (
        ENTERPRISE_ADMIN_AUDIT_VERSION
    )


def test_successful_event_is_valid() -> None:
    event = _event()

    assert (
        event.outcome
        is EnterpriseAdminAuditOutcome.SUCCEEDED
    )
    assert event.failure_reason is None


def test_denied_event_requires_failure_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="requires failure_reason",
    ):
        _event(
            outcome=EnterpriseAdminAuditOutcome.DENIED,
        )


def test_failed_event_requires_failure_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="requires failure_reason",
    ):
        _event(
            outcome=EnterpriseAdminAuditOutcome.FAILED,
        )


def test_denied_event_accepts_failure_reason() -> None:
    event = _event(
        outcome=EnterpriseAdminAuditOutcome.DENIED,
        failure_reason="authorization_denied",
    )

    assert event.failure_reason == "authorization_denied"


def test_success_cannot_contain_failure_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot contain failure_reason",
    ):
        _event(
            failure_reason="unexpected",
        )


def test_target_id_requires_target_type() -> None:
    with pytest.raises(
        ValidationError,
        match="target_id requires target_type",
    ):
        _event(
            target_type=None,
            target_id="limit_requests",
        )


def test_timezone_aware_timestamp_is_required() -> None:
    with pytest.raises(
        ValidationError,
        match="must be timezone-aware",
    ):
        _event(
            occurred_at=datetime(
                2026,
                8,
                15,
            )
        )


def test_event_is_frozen() -> None:
    event = _event()

    with pytest.raises(ValidationError):
        event.workspace_id = "workspace_other"
