from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

OBSERVABILITY_EVENT_VERSION: Literal["observability-event-v1"] = "observability-event-v1"

WORKSPACE_ANALYTICS_VERSION: Literal["workspace-analytics-v1"] = "workspace-analytics-v1"


class ObservabilityOperation(StrEnum):
    SINGLE_REWRITE = "single_rewrite"
    MULTI_CANDIDATE_REWRITE = "multi_candidate_rewrite"
    LONG_DOCUMENT_REWRITE = "long_document_rewrite"


class ObservabilityOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    CONTROLLED_FAILURE = "controlled_failure"
    SYSTEM_FAILURE = "system_failure"


class ObservabilityControlDecision(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    VIOLATION = "violation"
    NOT_EVALUATED = "not_evaluated"


class ObservabilityTokenUsage(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def require_coherent_total(
        self,
    ) -> ObservabilityTokenUsage:
        if self.total_tokens != (self.input_tokens + self.output_tokens):
            raise ValueError("observability token total must equal input plus output tokens")

        return self


class PersistentObservabilityEvent(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event_version: Literal["observability-event-v1"] = OBSERVABILITY_EVENT_VERSION

    event_id: str = Field(
        min_length=1,
        max_length=200,
    )

    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    user_id: str = Field(
        min_length=1,
        max_length=200,
    )

    operation: ObservabilityOperation
    outcome: ObservabilityOutcome

    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    duration_ms: float = Field(ge=0)

    input_char_count: int = Field(ge=0)
    output_char_count: int = Field(ge=0)

    provider_execution_count: int = Field(
        default=0,
        ge=0,
    )

    provider_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    fallback_used: bool = False

    token_usage: ObservabilityTokenUsage = Field(
        default_factory=lambda: ObservabilityTokenUsage(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
        )
    )

    v1_release_decision: ObservabilityControlDecision | None = None

    claim_lock_decision: ObservabilityControlDecision | None = None

    candidate_count: int | None = Field(
        default=None,
        ge=2,
        le=5,
    )

    section_count: int | None = Field(
        default=None,
        ge=1,
    )

    rewrite_history_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    candidate_set_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    long_document_audit_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    failure_category: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    failure_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    @model_validator(mode="after")
    def require_event_integrity(
        self,
    ) -> PersistentObservabilityEvent:
        self._require_timezone()
        self._require_operation_shape()
        self._require_outcome_shape()

        return self

    def _require_timezone(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("observability event timestamp must be timezone-aware")

    def _require_operation_shape(self) -> None:
        if self.operation is ObservabilityOperation.SINGLE_REWRITE:
            if (
                self.candidate_count is not None
                or self.section_count is not None
                or self.candidate_set_id is not None
                or self.long_document_audit_id is not None
            ):
                raise ValueError(
                    "single rewrite observability cannot "
                    "contain candidate or long-document "
                    "dimensions"
                )

            return

        if self.operation is ObservabilityOperation.MULTI_CANDIDATE_REWRITE:
            if self.candidate_count is None:
                raise ValueError("multi-candidate observability requires candidate_count")

            if self.section_count is not None or self.long_document_audit_id is not None:
                raise ValueError(
                    "multi-candidate observability cannot contain long-document dimensions"
                )

            return

        if self.operation is ObservabilityOperation.LONG_DOCUMENT_REWRITE:
            if self.section_count is None:
                raise ValueError("long-document observability requires section_count")

            if self.candidate_count is not None or self.candidate_set_id is not None:
                raise ValueError("long-document observability cannot contain candidate dimensions")

    def _require_outcome_shape(self) -> None:
        if self.outcome is ObservabilityOutcome.SUCCEEDED:
            if self.failure_category is not None or self.failure_code is not None:
                raise ValueError(
                    "successful observability event cannot contain failure classification"
                )

            return

        if self.failure_category is None:
            raise ValueError("failed observability event requires failure_category")


class AnalyticsOperationBucket(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    operation: ObservabilityOperation
    event_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    controlled_failure_count: int = Field(ge=0)
    system_failure_count: int = Field(ge=0)

    @model_validator(mode="after")
    def require_bucket_totals(
        self,
    ) -> AnalyticsOperationBucket:
        expected = self.succeeded_count + self.controlled_failure_count + self.system_failure_count

        if self.event_count != expected:
            raise ValueError("analytics operation event_count must equal outcome counts")

        return self


class WorkspaceAnalyticsSnapshot(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    analytics_version: Literal["workspace-analytics-v1"] = WORKSPACE_ANALYTICS_VERSION

    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )

    period_start: datetime
    period_end: datetime

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    event_count: int = Field(ge=0)
    succeeded_count: int = Field(ge=0)
    controlled_failure_count: int = Field(ge=0)
    system_failure_count: int = Field(ge=0)

    total_duration_ms: float = Field(ge=0)

    total_input_char_count: int = Field(ge=0)
    total_output_char_count: int = Field(ge=0)

    total_provider_executions: int = Field(ge=0)
    total_fallbacks: int = Field(ge=0)

    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    operations: tuple[
        AnalyticsOperationBucket,
        ...,
    ] = ()

    @model_validator(mode="after")
    def require_snapshot_integrity(
        self,
    ) -> WorkspaceAnalyticsSnapshot:
        self._require_time_window()
        self._require_event_totals()
        self._require_operation_totals()
        self._require_token_totals()

        return self

    def _require_time_window(self) -> None:
        for value in (
            self.period_start,
            self.period_end,
            self.generated_at,
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("analytics timestamps must be timezone-aware")

        if self.period_end <= self.period_start:
            raise ValueError("analytics period_end must be after period_start")

    def _require_event_totals(self) -> None:
        expected = self.succeeded_count + self.controlled_failure_count + self.system_failure_count

        if self.event_count != expected:
            raise ValueError("analytics event_count must equal outcome counts")

    def _require_operation_totals(self) -> None:
        operations = tuple(bucket.operation for bucket in self.operations)

        if len(operations) != len(set(operations)):
            raise ValueError("analytics operation buckets must be unique")

        if sum(bucket.event_count for bucket in self.operations) != self.event_count:
            raise ValueError("analytics operation buckets must sum to event_count")

    def _require_token_totals(self) -> None:
        if self.total_tokens != (self.total_input_tokens + self.total_output_tokens):
            raise ValueError("analytics token total must equal input plus output tokens")

        if self.total_fallbacks > self.total_provider_executions:
            raise ValueError("analytics fallbacks cannot exceed provider executions")
