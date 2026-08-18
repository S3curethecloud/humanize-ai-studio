from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.v2.domain.observability import (
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
    PersistentObservabilityEvent,
)
from app.v2.services.workspace_analytics_aggregator import (
    WorkspaceAnalyticsAggregationError,
    WorkspaceAnalyticsAggregator,
)

START = datetime(
    2026,
    8,
    12,
    0,
    0,
    tzinfo=UTC,
)
END = START + timedelta(days=1)
GENERATED_AT = END + timedelta(minutes=5)


def _event(
    event_id: str,
    *,
    occurred_at: datetime,
    operation: ObservabilityOperation = (ObservabilityOperation.SINGLE_REWRITE),
    outcome: ObservabilityOutcome = (ObservabilityOutcome.SUCCEEDED),
    workspace_id: str = "workspace_test",
    duration_ms: float = 10.0,
    input_char_count: int = 100,
    output_char_count: int = 120,
    provider_execution_count: int = 1,
    fallback_used: bool = False,
    input_tokens: int = 10,
    output_tokens: int = 12,
) -> PersistentObservabilityEvent:
    kwargs: dict[str, object] = {}

    if operation is ObservabilityOperation.MULTI_CANDIDATE_REWRITE:
        kwargs["candidate_count"] = 3
        kwargs["candidate_set_id"] = f"candidate_set_{event_id}"
        kwargs["rewrite_history_id"] = f"history_{event_id}"
    elif operation is ObservabilityOperation.LONG_DOCUMENT_REWRITE:
        kwargs["section_count"] = 4
        kwargs["long_document_audit_id"] = f"audit_{event_id}"
    else:
        kwargs["rewrite_history_id"] = f"history_{event_id}"

    if outcome is not ObservabilityOutcome.SUCCEEDED:
        kwargs["failure_category"] = "test_failure"
        kwargs["failure_code"] = "test_code"

    return PersistentObservabilityEvent(
        event_id=event_id,
        workspace_id=workspace_id,
        user_id="user_test",
        operation=operation,
        outcome=outcome,
        occurred_at=occurred_at,
        duration_ms=duration_ms,
        input_char_count=input_char_count,
        output_char_count=output_char_count,
        provider_execution_count=(provider_execution_count),
        provider_name=("provider-test" if provider_execution_count else None),
        fallback_used=fallback_used,
        token_usage=ObservabilityTokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(input_tokens + output_tokens),
        ),
        **kwargs,
    )


def _aggregator() -> WorkspaceAnalyticsAggregator:
    return WorkspaceAnalyticsAggregator(
        clock=lambda: GENERATED_AT,
    )


def test_aggregates_workspace_totals() -> None:
    events = (
        _event(
            "event_1",
            occurred_at=START,
            duration_ms=10.5,
            input_char_count=100,
            output_char_count=120,
            provider_execution_count=1,
            fallback_used=False,
            input_tokens=10,
            output_tokens=12,
        ),
        _event(
            "event_2",
            occurred_at=(START + timedelta(hours=1)),
            operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
            duration_ms=20.5,
            input_char_count=200,
            output_char_count=210,
            provider_execution_count=3,
            fallback_used=True,
            input_tokens=30,
            output_tokens=35,
        ),
        _event(
            "event_3",
            occurred_at=(START + timedelta(hours=2)),
            operation=(ObservabilityOperation.LONG_DOCUMENT_REWRITE),
            outcome=(ObservabilityOutcome.CONTROLLED_FAILURE),
            duration_ms=30.0,
            input_char_count=300,
            output_char_count=0,
            provider_execution_count=2,
            fallback_used=False,
            input_tokens=50,
            output_tokens=5,
        ),
    )

    snapshot = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=events,
    )

    assert snapshot.generated_at == GENERATED_AT
    assert snapshot.event_count == 3
    assert snapshot.succeeded_count == 2
    assert snapshot.controlled_failure_count == 1
    assert snapshot.system_failure_count == 0

    assert snapshot.total_duration_ms == 61.0
    assert snapshot.total_input_char_count == 600
    assert snapshot.total_output_char_count == 330

    assert snapshot.total_provider_executions == 6
    assert snapshot.total_fallbacks == 1

    assert snapshot.total_input_tokens == 90
    assert snapshot.total_output_tokens == 52
    assert snapshot.total_tokens == 142


def test_emits_all_operation_buckets_in_canonical_order() -> None:
    snapshot = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=(
            _event(
                "event_single",
                occurred_at=START,
            ),
        ),
    )

    assert tuple(bucket.operation for bucket in snapshot.operations) == tuple(
        ObservabilityOperation
    )

    assert tuple(bucket.event_count for bucket in snapshot.operations) == (
        1,
        0,
        0,
    )


def test_operation_buckets_aggregate_outcomes() -> None:
    events = (
        _event(
            "event_success",
            occurred_at=START,
            operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
        ),
        _event(
            "event_controlled",
            occurred_at=(START + timedelta(minutes=1)),
            operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
            outcome=(ObservabilityOutcome.CONTROLLED_FAILURE),
        ),
        _event(
            "event_system",
            occurred_at=(START + timedelta(minutes=2)),
            operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
            outcome=(ObservabilityOutcome.SYSTEM_FAILURE),
        ),
    )

    snapshot = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=events,
    )

    bucket = snapshot.operations[1]

    assert bucket.event_count == 3
    assert bucket.succeeded_count == 1
    assert bucket.controlled_failure_count == 1
    assert bucket.system_failure_count == 1


def test_empty_window_produces_zero_snapshot() -> None:
    snapshot = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=(),
    )

    assert snapshot.event_count == 0
    assert snapshot.succeeded_count == 0
    assert snapshot.controlled_failure_count == 0
    assert snapshot.system_failure_count == 0
    assert snapshot.total_duration_ms == 0
    assert snapshot.total_provider_executions == 0
    assert snapshot.total_fallbacks == 0
    assert snapshot.total_tokens == 0
    assert len(snapshot.operations) == 3
    assert all(bucket.event_count == 0 for bucket in snapshot.operations)


def test_source_order_does_not_change_snapshot() -> None:
    first = _event(
        "event_a",
        occurred_at=(START + timedelta(hours=2)),
        input_tokens=4,
        output_tokens=5,
    )
    second = _event(
        "event_b",
        occurred_at=(START + timedelta(hours=1)),
        operation=(ObservabilityOperation.LONG_DOCUMENT_REWRITE),
        input_tokens=7,
        output_tokens=8,
    )

    forward = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=(first, second),
    )

    reverse = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=(second, first),
    )

    assert forward == reverse


def test_accepts_period_start_boundary() -> None:
    snapshot = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=(
            _event(
                "event_start",
                occurred_at=START,
            ),
        ),
    )

    assert snapshot.event_count == 1


def test_rejects_period_end_boundary() -> None:
    with pytest.raises(
        WorkspaceAnalyticsAggregationError,
        match="outside aggregation window",
    ):
        _aggregator().aggregate(
            workspace_id="workspace_test",
            period_start=START,
            period_end=END,
            events=(
                _event(
                    "event_end",
                    occurred_at=END,
                ),
            ),
        )


def test_rejects_event_before_period_start() -> None:
    with pytest.raises(
        WorkspaceAnalyticsAggregationError,
        match="outside aggregation window",
    ):
        _aggregator().aggregate(
            workspace_id="workspace_test",
            period_start=START,
            period_end=END,
            events=(
                _event(
                    "event_before",
                    occurred_at=(START - timedelta(microseconds=1)),
                ),
            ),
        )


def test_rejects_cross_workspace_event() -> None:
    with pytest.raises(
        WorkspaceAnalyticsAggregationError,
        match="workspace does not match",
    ):
        _aggregator().aggregate(
            workspace_id="workspace_test",
            period_start=START,
            period_end=END,
            events=(
                _event(
                    "event_other",
                    occurred_at=START,
                    workspace_id=("workspace_other"),
                ),
            ),
        )


def test_rejects_naive_period_start() -> None:
    with pytest.raises(
        WorkspaceAnalyticsAggregationError,
        match="timezone-aware",
    ):
        _aggregator().aggregate(
            workspace_id="workspace_test",
            period_start=datetime(
                2026,
                8,
                12,
            ),
            period_end=END,
            events=(),
        )


def test_rejects_naive_period_end() -> None:
    with pytest.raises(
        WorkspaceAnalyticsAggregationError,
        match="timezone-aware",
    ):
        _aggregator().aggregate(
            workspace_id="workspace_test",
            period_start=START,
            period_end=datetime(
                2026,
                8,
                13,
            ),
            events=(),
        )


def test_rejects_invalid_window_order() -> None:
    with pytest.raises(
        WorkspaceAnalyticsAggregationError,
        match="period_end must be after",
    ):
        _aggregator().aggregate(
            workspace_id="workspace_test",
            period_start=END,
            period_end=START,
            events=(),
        )


def test_rejects_empty_workspace_id() -> None:
    with pytest.raises(
        WorkspaceAnalyticsAggregationError,
        match="workspace_id must not be empty",
    ):
        _aggregator().aggregate(
            workspace_id="",
            period_start=START,
            period_end=END,
            events=(),
        )


def test_generated_at_is_clock_controlled() -> None:
    snapshot = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=(),
    )

    assert snapshot.generated_at == GENERATED_AT


def test_fallback_counts_events_not_provider_executions() -> None:
    snapshot = _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=(
            _event(
                "event_fallback",
                occurred_at=START,
                provider_execution_count=4,
                fallback_used=True,
            ),
        ),
    )

    assert snapshot.total_provider_executions == 4
    assert snapshot.total_fallbacks == 1


def test_input_events_are_not_mutated() -> None:
    event = _event(
        "event_immutable",
        occurred_at=START,
    )
    before = event.model_dump()

    _aggregator().aggregate(
        workspace_id="workspace_test",
        period_start=START,
        period_end=END,
        events=(event,),
    )

    assert event.model_dump() == before
