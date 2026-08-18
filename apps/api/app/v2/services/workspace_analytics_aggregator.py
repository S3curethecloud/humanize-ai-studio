from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from app.v2.domain.observability import (
    AnalyticsOperationBucket,
    ObservabilityOperation,
    ObservabilityOutcome,
    PersistentObservabilityEvent,
    WorkspaceAnalyticsSnapshot,
)


class WorkspaceAnalyticsAggregationError(ValueError):
    pass


class WorkspaceAnalyticsAggregator:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or _utc_now

    def aggregate(
        self,
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        events: Iterable[PersistentObservabilityEvent],
    ) -> WorkspaceAnalyticsSnapshot:
        if not workspace_id:
            raise WorkspaceAnalyticsAggregationError("workspace_id must not be empty")

        self._require_window(
            period_start=period_start,
            period_end=period_end,
        )

        materialized = tuple(events)

        self._require_event_scope(
            workspace_id=workspace_id,
            period_start=period_start,
            period_end=period_end,
            events=materialized,
        )

        ordered = tuple(
            sorted(
                materialized,
                key=lambda event: (
                    event.occurred_at,
                    event.event_id,
                ),
            )
        )

        succeeded_count = sum(event.outcome is ObservabilityOutcome.SUCCEEDED for event in ordered)
        controlled_failure_count = sum(
            event.outcome is ObservabilityOutcome.CONTROLLED_FAILURE for event in ordered
        )
        system_failure_count = sum(
            event.outcome is ObservabilityOutcome.SYSTEM_FAILURE for event in ordered
        )

        total_input_tokens = sum(event.token_usage.input_tokens for event in ordered)
        total_output_tokens = sum(event.token_usage.output_tokens for event in ordered)

        operations = tuple(
            self._operation_bucket(
                operation=operation,
                events=ordered,
            )
            for operation in ObservabilityOperation
        )

        return WorkspaceAnalyticsSnapshot(
            workspace_id=workspace_id,
            period_start=period_start,
            period_end=period_end,
            generated_at=self._clock(),
            event_count=len(ordered),
            succeeded_count=succeeded_count,
            controlled_failure_count=(controlled_failure_count),
            system_failure_count=(system_failure_count),
            total_duration_ms=sum(event.duration_ms for event in ordered),
            total_input_char_count=sum(event.input_char_count for event in ordered),
            total_output_char_count=sum(event.output_char_count for event in ordered),
            total_provider_executions=sum(event.provider_execution_count for event in ordered),
            total_fallbacks=sum(event.fallback_used for event in ordered),
            total_input_tokens=(total_input_tokens),
            total_output_tokens=(total_output_tokens),
            total_tokens=(total_input_tokens + total_output_tokens),
            operations=operations,
        )

    @staticmethod
    def _require_window(
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> None:
        for value in (
            period_start,
            period_end,
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise (
                    WorkspaceAnalyticsAggregationError(
                        "analytics aggregation window must be timezone-aware"
                    )
                )

        if period_end <= period_start:
            raise WorkspaceAnalyticsAggregationError(
                "analytics aggregation period_end must be after period_start"
            )

    @staticmethod
    def _require_event_scope(
        *,
        workspace_id: str,
        period_start: datetime,
        period_end: datetime,
        events: tuple[
            PersistentObservabilityEvent,
            ...,
        ],
    ) -> None:
        for event in events:
            if event.workspace_id != workspace_id:
                raise (
                    WorkspaceAnalyticsAggregationError(
                        "observability event workspace does not match aggregation workspace"
                    )
                )

            if not (period_start <= event.occurred_at < period_end):
                raise (
                    WorkspaceAnalyticsAggregationError(
                        "observability event falls outside aggregation window"
                    )
                )

    @staticmethod
    def _operation_bucket(
        *,
        operation: ObservabilityOperation,
        events: tuple[
            PersistentObservabilityEvent,
            ...,
        ],
    ) -> AnalyticsOperationBucket:
        matching = tuple(event for event in events if event.operation is operation)

        return AnalyticsOperationBucket(
            operation=operation,
            event_count=len(matching),
            succeeded_count=sum(
                event.outcome is ObservabilityOutcome.SUCCEEDED for event in matching
            ),
            controlled_failure_count=sum(
                event.outcome is ObservabilityOutcome.CONTROLLED_FAILURE for event in matching
            ),
            system_failure_count=sum(
                event.outcome is ObservabilityOutcome.SYSTEM_FAILURE for event in matching
            ),
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)
