from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.v2.domain.observability import (
    ObservabilityControlDecision,
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
    PersistentObservabilityEvent,
)


class ObservabilityEventWriter(Protocol):
    def create(
        self,
        event: PersistentObservabilityEvent,
    ) -> PersistentObservabilityEvent: ...


class ObservabilityRecordingIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObservabilityRecordInput:
    workspace_id: str
    user_id: str
    operation: ObservabilityOperation
    outcome: ObservabilityOutcome
    duration_ms: float
    input_char_count: int
    output_char_count: int
    token_usage: ObservabilityTokenUsage

    provider_execution_count: int = 0
    provider_name: str | None = None
    fallback_used: bool = False

    v1_release_decision: ObservabilityControlDecision | None = None

    claim_lock_decision: ObservabilityControlDecision | None = None

    candidate_count: int | None = None
    section_count: int | None = None

    rewrite_history_id: str | None = None
    candidate_set_id: str | None = None
    long_document_audit_id: str | None = None

    failure_category: str | None = None
    failure_code: str | None = None


class ObservabilityRecordingService:
    def __init__(
        self,
        *,
        repository: ObservabilityEventWriter,
        event_id_factory: Callable[
            [],
            str,
        ]
        | None = None,
        clock: Callable[
            [],
            datetime,
        ]
        | None = None,
    ) -> None:
        self._repository = repository
        self._event_id_factory = event_id_factory or _default_event_id
        self._clock = clock or _utc_now

    def record(
        self,
        command: ObservabilityRecordInput,
    ) -> PersistentObservabilityEvent:
        event = PersistentObservabilityEvent(
            event_id=self._event_id_factory(),
            workspace_id=command.workspace_id,
            user_id=command.user_id,
            operation=command.operation,
            outcome=command.outcome,
            occurred_at=self._clock(),
            duration_ms=command.duration_ms,
            input_char_count=(command.input_char_count),
            output_char_count=(command.output_char_count),
            provider_execution_count=(command.provider_execution_count),
            provider_name=command.provider_name,
            fallback_used=command.fallback_used,
            token_usage=command.token_usage,
            v1_release_decision=(command.v1_release_decision),
            claim_lock_decision=(command.claim_lock_decision),
            candidate_count=(command.candidate_count),
            section_count=command.section_count,
            rewrite_history_id=(command.rewrite_history_id),
            candidate_set_id=(command.candidate_set_id),
            long_document_audit_id=(command.long_document_audit_id),
            failure_category=(command.failure_category),
            failure_code=command.failure_code,
        )

        persisted = self._repository.create(event)

        if persisted != event:
            raise (
                ObservabilityRecordingIntegrityError(
                    "observability repository returned "
                    "an event different from the "
                    "event supplied for persistence"
                )
            )

        return persisted


def _default_event_id() -> str:
    return f"observability_event_{uuid4().hex}"


def _utc_now() -> datetime:
    return datetime.now(UTC)
