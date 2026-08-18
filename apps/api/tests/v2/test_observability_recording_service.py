from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.v2.domain.observability import (
    ObservabilityControlDecision,
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
    PersistentObservabilityEvent,
)
from app.v2.repositories.observability import (
    InMemoryObservabilityEventRepository,
    SQLiteObservabilityEventRepository,
)
from app.v2.services.observability_recording_service import (
    ObservabilityEventWriter,
    ObservabilityRecordingIntegrityError,
    ObservabilityRecordingService,
    ObservabilityRecordInput,
)

NOW = datetime(
    2026,
    8,
    12,
    18,
    0,
    tzinfo=UTC,
)


def _command(
    **updates: object,
) -> ObservabilityRecordInput:
    values: dict[str, object] = {
        "workspace_id": "workspace_test",
        "user_id": "user_test",
        "operation": (ObservabilityOperation.SINGLE_REWRITE),
        "outcome": (ObservabilityOutcome.SUCCEEDED),
        "duration_ms": 125.5,
        "input_char_count": 100,
        "output_char_count": 110,
        "provider_execution_count": 1,
        "provider_name": "test-provider",
        "fallback_used": False,
        "token_usage": (
            ObservabilityTokenUsage(
                input_tokens=10,
                output_tokens=12,
                total_tokens=22,
            )
        ),
        "v1_release_decision": (ObservabilityControlDecision.PASS),
    }

    values.update(updates)

    typed_values = cast(
        Any,
        values,
    )

    return ObservabilityRecordInput(**typed_values)


def _service(
    repository: ObservabilityEventWriter,
    *,
    event_id: str = "event_test",
    now: datetime = NOW,
) -> ObservabilityRecordingService:
    return ObservabilityRecordingService(
        repository=repository,
        event_id_factory=lambda: event_id,
        clock=lambda: now,
    )


def test_records_exact_event_in_memory() -> None:
    repository = InMemoryObservabilityEventRepository()
    service = _service(repository)

    recorded = service.record(_command())

    assert recorded.event_id == "event_test"
    assert recorded.occurred_at == NOW
    assert repository.get("event_test") == recorded


def test_recording_maps_all_safe_common_fields() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _service(
        repository,
    ).record(
        _command(
            duration_ms=987.25,
            input_char_count=1234,
            output_char_count=1200,
            provider_execution_count=2,
            provider_name="provider-test",
            fallback_used=True,
            rewrite_history_id=("rewrite_test"),
            claim_lock_decision=(ObservabilityControlDecision.WARN),
        )
    )

    assert recorded.duration_ms == 987.25
    assert recorded.input_char_count == 1234
    assert recorded.output_char_count == 1200
    assert recorded.provider_execution_count == 2
    assert recorded.provider_name == "provider-test"
    assert recorded.fallback_used is True
    assert recorded.rewrite_history_id == "rewrite_test"
    assert recorded.claim_lock_decision is ObservabilityControlDecision.WARN


def test_multi_candidate_recording_maps_dimensions() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _service(
        repository,
    ).record(
        _command(
            operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
            candidate_count=3,
            candidate_set_id=("candidate_set_test"),
            rewrite_history_id=None,
        )
    )

    assert recorded.candidate_count == 3
    assert recorded.candidate_set_id == "candidate_set_test"
    assert recorded.section_count is None


def test_long_document_recording_maps_dimensions() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _service(
        repository,
    ).record(
        _command(
            operation=(ObservabilityOperation.LONG_DOCUMENT_REWRITE),
            section_count=5,
            long_document_audit_id=("audit_test"),
            rewrite_history_id=None,
        )
    )

    assert recorded.section_count == 5
    assert recorded.long_document_audit_id == "audit_test"
    assert recorded.candidate_count is None


def test_controlled_failure_maps_bounded_classification() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _service(
        repository,
    ).record(
        _command(
            outcome=(ObservabilityOutcome.CONTROLLED_FAILURE),
            output_char_count=0,
            failure_category="claim_lock",
            failure_code="strict_violation",
        )
    )

    assert recorded.outcome is ObservabilityOutcome.CONTROLLED_FAILURE
    assert recorded.failure_category == "claim_lock"
    assert recorded.failure_code == "strict_violation"


def test_system_failure_maps_bounded_classification() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _service(
        repository,
    ).record(
        _command(
            outcome=(ObservabilityOutcome.SYSTEM_FAILURE),
            output_char_count=0,
            provider_execution_count=0,
            provider_name=None,
            failure_category="provider",
            failure_code="unavailable",
        )
    )

    assert recorded.outcome is ObservabilityOutcome.SYSTEM_FAILURE
    assert recorded.failure_category == "provider"


class CountingWriter:
    def __init__(self) -> None:
        self.calls = 0
        self.events: list[PersistentObservabilityEvent] = []

    def create(
        self,
        event: PersistentObservabilityEvent,
    ) -> PersistentObservabilityEvent:
        self.calls += 1
        self.events.append(event)
        return event


def test_invalid_event_fails_before_repository_write() -> None:
    writer = CountingWriter()
    service = _service(writer)

    with pytest.raises(
        ValidationError,
        match="requires candidate_count",
    ):
        service.record(
            _command(
                operation=(ObservabilityOperation.MULTI_CANDIDATE_REWRITE),
            )
        )

    assert writer.calls == 0
    assert writer.events == []


def test_naive_clock_fails_before_repository_write() -> None:
    writer = CountingWriter()

    service = _service(
        writer,
        now=datetime(
            2026,
            8,
            12,
            18,
            0,
        ),
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        service.record(_command())

    assert writer.calls == 0


class FailingWriter:
    def __init__(self) -> None:
        self.calls = 0

    def create(
        self,
        event: PersistentObservabilityEvent,
    ) -> PersistentObservabilityEvent:
        self.calls += 1
        raise RuntimeError("persistence unavailable")


def test_repository_failure_propagates_without_retry() -> None:
    writer = FailingWriter()
    service = _service(writer)

    with pytest.raises(
        RuntimeError,
        match="persistence unavailable",
    ):
        service.record(_command())

    assert writer.calls == 1


class MismatchingWriter:
    def __init__(self) -> None:
        self.calls = 0

    def create(
        self,
        event: PersistentObservabilityEvent,
    ) -> PersistentObservabilityEvent:
        self.calls += 1

        return event.model_copy(update={"duration_ms": (event.duration_ms + 1)})


def test_repository_mismatch_fails_closed() -> None:
    writer = MismatchingWriter()
    service = _service(writer)

    with pytest.raises(
        ObservabilityRecordingIntegrityError,
        match="different",
    ):
        service.record(_command())

    assert writer.calls == 1


def test_duplicate_event_id_surfaces_without_retry() -> None:
    repository = InMemoryObservabilityEventRepository()
    service = _service(
        repository,
        event_id="event_duplicate",
    )

    service.record(_command())

    with pytest.raises(
        ValueError,
        match="already exists",
    ):
        service.record(_command())

    stored = repository.get("event_duplicate")

    assert stored is not None


def test_record_input_exposes_no_raw_content_fields() -> None:
    names = {field.name for field in fields(ObservabilityRecordInput)}

    forbidden = {
        "source_text",
        "rewritten_text",
        "prompt",
        "protected_terms",
        "metadata",
    }

    assert names.isdisjoint(forbidden)


def test_sqlite_record_survives_repository_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "recording-service.sqlite3"

    first = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    recorded = _service(
        first,
        event_id="event_sqlite",
    ).record(_command())

    second = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    assert second.get("event_sqlite") == recorded


def test_service_calls_repository_once_on_success() -> None:
    writer = CountingWriter()
    service = _service(writer)

    recorded = service.record(_command())

    assert writer.calls == 1
    assert writer.events == [recorded]


def test_default_event_id_and_clock_are_valid() -> None:
    repository = InMemoryObservabilityEventRepository()

    before = datetime.now(UTC)

    recorded = ObservabilityRecordingService(
        repository=repository,
    ).record(_command())

    after = datetime.now(UTC)

    assert recorded.event_id.startswith("observability_event_")
    assert before <= recorded.occurred_at <= after
    assert recorded.occurred_at.tzinfo is not None
