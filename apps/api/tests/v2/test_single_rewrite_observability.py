from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

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
from app.v2.domain.claim_lock import (
    ClaimLockEnforcementMode,
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
from app.v2.services.observability_recording_service import (
    ObservabilityRecordingService,
)
from app.v2.services.single_rewrite_observability import (
    SingleRewriteObservability,
)

NOW = datetime(
    2026,
    8,
    12,
    20,
    0,
    tzinfo=UTC,
)


def _request() -> RewriteRequest:
    return RewriteRequest(
        text="Original text 42.",
    )


def _response(
    *,
    provider_required: bool = True,
    input_tokens: int | None = 10,
    output_tokens: int | None = 8,
    total_tokens: int | None = 18,
    fallback_used: bool = False,
    verification: ReleaseDecision = (ReleaseDecision.PASS),
) -> RewriteResponse:
    return RewriteResponse(
        trace_id="trace_test",
        workflow_states=[],
        source_text="Original text 42.",
        rewritten_text=("Natural rewritten text 42."),
        provider_name="provider-test",
        model_name="model-test",
        prompt_version="prompt-test",
        provider_execution=(
            ProviderExecutionEvidence(
                latency_ms=25.0,
                primary_provider_name=("provider-primary"),
                actual_provider_name=("provider-actual"),
                fallback_used=fallback_used,
                provider_error_category=None,
                usage=ProviderUsageEvidence(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
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
            decision=verification,
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
        rewrite_id="history_test",
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
        fallback_used=(response.provider_execution.fallback_used),
        verification_decision=(response.verification.decision.value),
        editorial_quality_decision=(response.editorial_quality.decision.value),
    )


def _instrumentation(
    repository: (InMemoryObservabilityEventRepository | SQLiteObservabilityEventRepository),
) -> SingleRewriteObservability:
    recording = ObservabilityRecordingService(
        repository=repository,
        event_id_factory=lambda: "event_single",
        clock=lambda: NOW,
    )

    return SingleRewriteObservability(
        recording_service=recording,
    )


def test_records_successful_single_rewrite() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _instrumentation(repository).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        response=_response(),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        duration_ms=125.0,
    )

    assert recorded.operation is ObservabilityOperation.SINGLE_REWRITE
    assert recorded.outcome is ObservabilityOutcome.SUCCEEDED
    assert recorded.duration_ms == 125.0
    assert recorded.input_char_count == len(_request().text)
    assert recorded.output_char_count == len(_response().rewritten_text)
    assert recorded.rewrite_history_id == "history_test"


def test_maps_v1_and_claim_lock_decisions() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _instrumentation(repository).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        response=_response(verification=(ReleaseDecision.WARN)),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.VIOLATION),
                enforcement_mode=(ClaimLockEnforcementMode.AUDIT_ONLY),
            )
        ),
        duration_ms=1.0,
    )

    assert recorded.v1_release_decision is ObservabilityControlDecision.WARN
    assert recorded.claim_lock_decision is ObservabilityControlDecision.VIOLATION


def test_provider_execution_maps_when_required() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _instrumentation(repository).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        response=_response(
            fallback_used=True,
        ),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        duration_ms=1.0,
    )

    assert recorded.provider_execution_count == 1
    assert recorded.provider_name == "provider-actual"
    assert recorded.fallback_used is True


def test_no_provider_execution_maps_zero() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _instrumentation(repository).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        response=_response(
            provider_required=False,
        ),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        duration_ms=1.0,
    )

    assert recorded.provider_execution_count == 0
    assert recorded.provider_name is None


def test_token_usage_normalizes_missing_values() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _instrumentation(repository).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        response=_response(
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        ),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        duration_ms=1.0,
    )

    assert recorded.token_usage.input_tokens == 0
    assert recorded.token_usage.output_tokens == 0
    assert recorded.token_usage.total_tokens == 0


def test_token_total_is_coherent_from_components() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _instrumentation(repository).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        response=_response(
            input_tokens=7,
            output_tokens=9,
            total_tokens=999,
        ),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        duration_ms=1.0,
    )

    assert recorded.token_usage.total_tokens == 16


def test_persistent_event_contains_no_raw_text() -> None:
    repository = InMemoryObservabilityEventRepository()

    recorded = _instrumentation(repository).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        response=_response(),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        duration_ms=1.0,
    )

    payload = recorded.model_dump()

    assert "source_text" not in payload
    assert "rewritten_text" not in payload
    assert "prompt" not in payload
    assert "protected_terms" not in payload


def test_sqlite_success_event_survives_recreation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "single-rewrite.sqlite3"

    first = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    recorded = _instrumentation(first).record_success(
        workspace_id="workspace_test",
        user_id="user_test",
        request=_request(),
        response=_response(),
        history=_history(),
        claim_lock_validation=(
            ClaimLockValidationResult(
                decision=(ClaimLockValidationDecision.PASS),
            )
        ),
        duration_ms=1.0,
    )

    second = SQLiteObservabilityEventRepository(
        database_path=database_path,
    )

    assert second.get(recorded.event_id) == recorded


def test_v2_services_memory_backend_builds_observability() -> None:
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

    assert services.observability_recording is not None
    assert services.single_rewrite_observability is not None


def test_v2_services_sqlite_backend_builds_observability(
    tmp_path: Path,
) -> None:
    from app.v2.api.dependencies import (
        V2Services,
    )

    services = V2Services(
        persistence_settings=(
            V2PersistenceSettings(
                backend=(PersistenceBackend.SQLITE),
                sqlite_path=(tmp_path / "v2.sqlite3"),
                database_url=None,
            )
        ),
    )

    assert services.observability_recording is not None
    assert services.single_rewrite_observability is not None
