from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.v2.domain.observability import (
    OBSERVABILITY_EVENT_VERSION,
    WORKSPACE_ANALYTICS_VERSION,
    AnalyticsOperationBucket,
    ObservabilityControlDecision,
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
    PersistentObservabilityEvent,
    WorkspaceAnalyticsSnapshot,
)

NOW = datetime(
    2026,
    8,
    12,
    12,
    0,
    tzinfo=UTC,
)


def _event(
    **updates: object,
) -> PersistentObservabilityEvent:
    values: dict[str, object] = {
        "event_id": "event_test",
        "workspace_id": "workspace_test",
        "user_id": "user_test",
        "operation": (ObservabilityOperation.SINGLE_REWRITE),
        "outcome": (ObservabilityOutcome.SUCCEEDED),
        "occurred_at": NOW,
        "duration_ms": 125.5,
        "input_char_count": 100,
        "output_char_count": 110,
        "provider_execution_count": 1,
        "provider_name": "test-provider",
        "fallback_used": False,
        "token_usage": {
            "input_tokens": 10,
            "output_tokens": 12,
            "total_tokens": 22,
        },
        "v1_release_decision": (ObservabilityControlDecision.PASS),
    }

    values.update(updates)

    return PersistentObservabilityEvent(**values)


def _snapshot(
    **updates: object,
) -> WorkspaceAnalyticsSnapshot:
    values: dict[str, object] = {
        "workspace_id": "workspace_test",
        "period_start": datetime(
            2026,
            8,
            1,
            tzinfo=UTC,
        ),
        "period_end": datetime(
            2026,
            9,
            1,
            tzinfo=UTC,
        ),
        "generated_at": NOW,
        "event_count": 3,
        "succeeded_count": 2,
        "controlled_failure_count": 1,
        "system_failure_count": 0,
        "total_duration_ms": 300.0,
        "total_input_char_count": 300,
        "total_output_char_count": 280,
        "total_provider_executions": 3,
        "total_fallbacks": 1,
        "total_input_tokens": 30,
        "total_output_tokens": 20,
        "total_tokens": 50,
        "operations": (
            {
                "operation": (ObservabilityOperation.SINGLE_REWRITE),
                "event_count": 3,
                "succeeded_count": 2,
                "controlled_failure_count": 1,
                "system_failure_count": 0,
            },
        ),
    }

    values.update(updates)

    return WorkspaceAnalyticsSnapshot(**values)


def test_versions_are_frozen() -> None:
    assert OBSERVABILITY_EVENT_VERSION == "observability-event-v1"

    assert WORKSPACE_ANALYTICS_VERSION == "workspace-analytics-v1"


def test_event_is_immutable_and_forbids_extra_fields() -> None:
    event = _event()

    with pytest.raises(
        ValidationError,
    ):
        event.event_id = "mutated"  # type: ignore[misc]

    with pytest.raises(
        ValidationError,
    ):
        PersistentObservabilityEvent.model_validate(
            {
                **event.model_dump(),
                "source_text": "must-not-be-stored",
            }
        )


def test_event_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _event(
            occurred_at=datetime(
                2026,
                8,
                12,
                12,
                0,
            )
        )


def test_single_rewrite_rejects_candidate_dimensions() -> None:
    with pytest.raises(
        ValidationError,
        match="single rewrite observability",
    ):
        _event(
            candidate_count=2,
        )


def test_multi_candidate_requires_candidate_count() -> None:
    with pytest.raises(
        ValidationError,
        match="requires candidate_count",
    ):
        _event(
            operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
        )


def test_multi_candidate_contract_accepts_candidate_linkage() -> None:
    event = _event(
        operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
        candidate_count=3,
        candidate_set_id="candidate_set_test",
    )

    assert event.candidate_count == 3
    assert event.candidate_set_id == "candidate_set_test"


def test_long_document_requires_section_count() -> None:
    with pytest.raises(
        ValidationError,
        match="requires section_count",
    ):
        _event(
            operation=(ObservabilityOperation.LONG_DOCUMENT_REWRITE),
        )


def test_long_document_contract_accepts_audit_linkage() -> None:
    event = _event(
        operation=(ObservabilityOperation.LONG_DOCUMENT_REWRITE),
        section_count=4,
        long_document_audit_id=("long_document_audit_test"),
    )

    assert event.section_count == 4
    assert event.long_document_audit_id == "long_document_audit_test"


def test_success_rejects_failure_classification() -> None:
    with pytest.raises(
        ValidationError,
        match="successful observability event",
    ):
        _event(
            failure_category=("control_failure"),
        )


def test_failed_event_requires_failure_category() -> None:
    with pytest.raises(
        ValidationError,
        match="requires failure_category",
    ):
        _event(
            outcome=(ObservabilityOutcome.CONTROLLED_FAILURE),
        )


def test_controlled_failure_accepts_safe_classification() -> None:
    event = _event(
        outcome=(ObservabilityOutcome.CONTROLLED_FAILURE),
        output_char_count=0,
        failure_category="claim_lock",
        failure_code="strict_violation",
    )

    assert event.failure_category == "claim_lock"
    assert event.failure_code == "strict_violation"


def test_token_usage_requires_exact_total() -> None:
    with pytest.raises(
        ValidationError,
        match="token total",
    ):
        ObservabilityTokenUsage(
            input_tokens=10,
            output_tokens=20,
            total_tokens=31,
        )


def test_analytics_snapshot_requires_outcome_totals() -> None:
    with pytest.raises(
        ValidationError,
        match="event_count",
    ):
        _snapshot(
            event_count=4,
        )


def test_analytics_snapshot_requires_unique_operation_buckets() -> None:
    bucket = AnalyticsOperationBucket(
        operation=(ObservabilityOperation.SINGLE_REWRITE),
        event_count=3,
        succeeded_count=2,
        controlled_failure_count=1,
        system_failure_count=0,
    )

    with pytest.raises(
        ValidationError,
        match="unique",
    ):
        _snapshot(
            event_count=6,
            succeeded_count=4,
            controlled_failure_count=2,
            operations=(
                bucket,
                bucket,
            ),
        )


def test_analytics_snapshot_requires_operation_bucket_sum() -> None:
    with pytest.raises(
        ValidationError,
        match="sum to event_count",
    ):
        _snapshot(
            operations=(),
        )


def test_analytics_snapshot_requires_valid_time_window() -> None:
    with pytest.raises(
        ValidationError,
        match="period_end",
    ):
        _snapshot(
            period_end=datetime(
                2026,
                8,
                1,
                tzinfo=UTC,
            ),
        )


def test_analytics_snapshot_requires_exact_token_total() -> None:
    with pytest.raises(
        ValidationError,
        match="token total",
    ):
        _snapshot(
            total_tokens=51,
        )


def test_analytics_fallbacks_cannot_exceed_provider_executions() -> None:
    with pytest.raises(
        ValidationError,
        match="fallbacks",
    ):
        _snapshot(
            total_provider_executions=1,
            total_fallbacks=2,
        )
