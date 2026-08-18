from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from app.domain.models import (
    AnalysisResult,
    EditorialQualityDecision,
    EditorialQualityResult,
    PatternScores,
    ProviderExecutionEvidence,
    ProviderUsageEvidence,
    ReleaseDecision,
    RewriteNecessityEvidence,
    RewriteRequest,
    RewriteResponse,
    VerificationResult,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.models import (
    RewriteHistoryRecord,
)
from app.v2.domain.observability import (
    ObservabilityControlDecision,
    ObservabilityOperation,
    ObservabilityOutcome,
)
from app.v2.repositories.observability import (
    InMemoryObservabilityEventRepository,
    SQLiteObservabilityEventRepository,
)
from app.v2.services.claim_lock_validator import (
    ClaimLockValidationDecision,
    ClaimLockValidationResult,
)
from app.v2.services.complex_rewrite_observability import (
    LongDocumentObservability,
    MultiCandidateObservability,
)
from app.v2.services.long_document_control_evaluator import (
    LongDocumentControlEvaluation,
)
from app.v2.services.observability_recording_service import (
    ObservabilityRecordingService,
)

NOW = datetime(
    2026,
    8,
    12,
    22,
    0,
    tzinfo=UTC,
)


def _request() -> RewriteRequest:
    return RewriteRequest(
        text="Original document 42.",
    )


def _response(
    *,
    rewritten_text: str = ("Rewritten document 42."),
    provider_required: bool = True,
    provider_name: str = "provider-a",
    input_tokens: int | None = 10,
    output_tokens: int | None = 8,
    fallback_used: bool = False,
    decision: ReleaseDecision = (ReleaseDecision.PASS),
) -> RewriteResponse:
    return RewriteResponse(
        trace_id="trace_test",
        workflow_states=[],
        source_text=("Original document 42."),
        rewritten_text=rewritten_text,
        provider_name=provider_name,
        model_name="model-test",
        prompt_version="prompt-test",
        provider_execution=(
            ProviderExecutionEvidence(
                latency_ms=10.0,
                primary_provider_name=("provider-primary"),
                actual_provider_name=(provider_name),
                fallback_used=(fallback_used),
                provider_error_category=None,
                usage=ProviderUsageEvidence(
                    input_tokens=input_tokens,
                    output_tokens=(output_tokens),
                    total_tokens=None,
                ),
            )
        ),
        rewrite_necessity=(
            RewriteNecessityEvidence(
                decision="full_rewrite",
                score=90,
                provider_required=(provider_required),
                signals=[],
                rationale="test",
            )
        ),
        analysis=AnalysisResult(
            scores=PatternScores(
                generic_language=0.0,
                repetition=0.0,
                sentence_uniformity=0.0,
                transition_overuse=0.0,
            ),
            flagged_segments=[],
        ),
        editorial_quality=(
            EditorialQualityResult(
                decision=(EditorialQualityDecision.PASS),
                naturalness_score=1.0,
                source_flag_count=0,
                remaining_flag_count=0,
                removed_flag_count=0,
                remaining_flagged_segments=[],
                warnings=[],
            )
        ),
        protected_facts=[],
        changes=[],
        verification=VerificationResult(
            decision=decision,
            preserved_facts=[],
            missing_facts=[],
            unexpected_facts=[],
            warnings=[],
        ),
    )


def _history() -> RewriteHistoryRecord:
    request = _request()
    response = _response()

    return RewriteHistoryRecord(
        rewrite_id="history_multi",
        workspace_id="workspace_test",
        user_id="user_test",
        trace_id=response.trace_id,
        source_text=response.source_text,
        rewritten_text=(response.rewritten_text),
        document_type=(request.document_type.value),
        audience=request.audience,
        tone=request.tone,
        intensity=request.intensity.value,
        provider_name=response.provider_name,
        model_name=response.model_name,
        prompt_version=(response.prompt_version),
        fallback_used=False,
        verification_decision="pass",
        editorial_quality_decision="pass",
    )


def _recording(
    repository: Any,
    *,
    event_id: str,
) -> ObservabilityRecordingService:
    return ObservabilityRecordingService(
        repository=repository,
        event_id_factory=lambda: event_id,
        clock=lambda: NOW,
    )


def test_multi_candidate_records_aggregate_execution() -> None:
    repository = InMemoryObservabilityEventRepository()

    responses = (
        _response(
            provider_name="provider-a",
            input_tokens=10,
            output_tokens=5,
        ),
        _response(
            provider_name="provider-a",
            input_tokens=20,
            output_tokens=7,
            fallback_used=True,
        ),
        _response(
            provider_required=False,
            provider_name="provider-unused",
        ),
    )

    event = MultiCandidateObservability(
        recording_service=_recording(
            repository,
            event_id="event_multi",
        )
    ).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        selected_response=responses[0],
        generated_responses=responses,
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        candidate_count=3,
        candidate_set_id="candidate_set_test",
        duration_ms=250.0,
    )

    assert event.operation is ObservabilityOperation.MULTI_CANDIDATE_REWRITE
    assert event.outcome is ObservabilityOutcome.SUCCEEDED
    assert event.candidate_count == 3
    assert event.candidate_set_id == "candidate_set_test"
    assert event.rewrite_history_id == "history_multi"
    assert event.provider_execution_count == 2
    assert event.provider_name == "provider-a"
    assert event.fallback_used is True
    assert event.token_usage.input_tokens == 30
    assert event.token_usage.output_tokens == 12
    assert event.token_usage.total_tokens == 42


def test_multi_candidate_uses_selected_v1_and_claim_lock() -> None:
    repository = InMemoryObservabilityEventRepository()

    selected = _response(
        decision=ReleaseDecision.WARN,
    )

    event = MultiCandidateObservability(
        recording_service=_recording(
            repository,
            event_id="event_multi_control",
        )
    ).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        selected_response=selected,
        generated_responses=(
            selected,
            _response(),
        ),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.VIOLATION),
            )
        ),
        candidate_count=2,
        candidate_set_id="candidate_set_test",
        duration_ms=1.0,
    )

    assert event.v1_release_decision is ObservabilityControlDecision.WARN
    assert event.claim_lock_decision is ObservabilityControlDecision.VIOLATION


def test_multiple_providers_are_bounded() -> None:
    repository = InMemoryObservabilityEventRepository()

    event = MultiCandidateObservability(
        recording_service=_recording(
            repository,
            event_id="event_multi_provider",
        )
    ).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        selected_response=_response(),
        generated_responses=(
            _response(provider_name="provider-a"),
            _response(provider_name="provider-b"),
        ),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        candidate_count=2,
        candidate_set_id="candidate_set_test",
        duration_ms=1.0,
    )

    assert event.provider_name == "multiple"


def _long_evaluation(
    responses: tuple[
        RewriteResponse,
        ...,
    ],
    *,
    section_count: int = 3,
    claim_lock_decision: (ClaimLockValidationDecision) = ClaimLockValidationDecision.PASS,
) -> LongDocumentControlEvaluation:
    sections = tuple(
        SimpleNamespace(
            section_id=f"section_{index}",
        )
        for index in range(section_count)
    )

    execution = SimpleNamespace(
        rewrite_responses=responses,
        structure=SimpleNamespace(
            sections=sections,
        ),
    )

    return cast(
        LongDocumentControlEvaluation,
        SimpleNamespace(
            execution=execution,
            claim_lock_validation=(
                ClaimLockValidationResult(
                    decision=(claim_lock_decision),
                )
            ),
        ),
    )


def _reconstruction(
    text: str,
) -> Any:
    return SimpleNamespace(
        reconstructed_text=text,
    )


def _audit(
    audit_id: str = "audit_test",
) -> Any:
    return SimpleNamespace(
        audit_id=audit_id,
    )


def test_long_document_records_aggregate_execution() -> None:
    repository = InMemoryObservabilityEventRepository()

    responses = (
        _response(
            provider_name="provider-a",
            input_tokens=11,
            output_tokens=4,
        ),
        _response(
            provider_name="provider-a",
            input_tokens=13,
            output_tokens=6,
            fallback_used=True,
            decision=ReleaseDecision.WARN,
        ),
    )

    event = LongDocumentObservability(
        recording_service=_recording(
            repository,
            event_id="event_long",
        )
    ).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        evaluation=_long_evaluation(
            responses,
            section_count=4,
        ),
        reconstruction=cast(
            Any,
            _reconstruction("Completed long document 42."),
        ),
        audit=cast(
            Any,
            _audit(),
        ),
        duration_ms=500.0,
    )

    assert event.operation is ObservabilityOperation.LONG_DOCUMENT_REWRITE
    assert event.section_count == 4
    assert event.long_document_audit_id == "audit_test"
    assert event.provider_execution_count == 2
    assert event.fallback_used is True
    assert event.token_usage.total_tokens == 34
    assert event.v1_release_decision is ObservabilityControlDecision.WARN


def test_long_document_without_rewritten_sections_has_no_v1_decision() -> None:
    repository = InMemoryObservabilityEventRepository()

    event = LongDocumentObservability(
        recording_service=_recording(
            repository,
            event_id="event_long_preserve",
        )
    ).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        evaluation=_long_evaluation(
            (),
            section_count=2,
        ),
        reconstruction=cast(
            Any,
            _reconstruction("Original document 42."),
        ),
        audit=cast(
            Any,
            _audit("audit_preserve"),
        ),
        duration_ms=1.0,
    )

    assert event.provider_execution_count == 0
    assert event.provider_name is None
    assert event.v1_release_decision is None


def test_complex_events_contain_no_raw_text() -> None:
    repository = InMemoryObservabilityEventRepository()

    event = MultiCandidateObservability(
        recording_service=_recording(
            repository,
            event_id="event_privacy",
        )
    ).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        selected_response=_response(),
        generated_responses=(
            _response(),
            _response(),
        ),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        candidate_count=2,
        candidate_set_id="candidate_set_test",
        duration_ms=1.0,
    )

    payload = event.model_dump()

    assert "source_text" not in payload
    assert "rewritten_text" not in payload
    assert "prompt" not in payload
    assert "protected_terms" not in payload
    assert "metadata" not in payload


def test_long_document_sqlite_event_survives_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "complex-observability.sqlite3"

    first = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    event = LongDocumentObservability(
        recording_service=_recording(
            first,
            event_id="event_long_sqlite",
        )
    ).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        evaluation=_long_evaluation(
            (_response(),),
        ),
        reconstruction=cast(
            Any,
            _reconstruction("Completed long document 42."),
        ),
        audit=cast(
            Any,
            _audit("audit_sqlite"),
        ),
        duration_ms=1.0,
    )

    second = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    assert second.get(event.event_id) == event


def test_v2_services_builds_complex_observability() -> None:
    from app.v2.api.dependencies import (
        V2Services,
    )

    services = V2Services(
        persistence_settings=(
            V2PersistenceSettings(
                backend=(PersistenceBackend.MEMORY),
                sqlite_path=None,
                database_url=None,
            )
        ),
    )

    assert services.multi_candidate_observability is not None
    assert services.long_document_observability is not None
