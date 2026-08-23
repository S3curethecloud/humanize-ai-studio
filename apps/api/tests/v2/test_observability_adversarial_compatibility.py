from __future__ import annotations

from tests.v2.test_support_authorization_gate import allow_all_workspace_authorization_gate
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.observability import (
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
    PersistentObservabilityEvent,
)
from app.v2.repositories.observability import (
    InMemoryObservabilityEventRepository,
)
from app.v2.services.observability_recording_service import (
    ObservabilityRecordInput,
)
from app.v2.services.workspace_analytics_aggregator import (
    WorkspaceAnalyticsAggregator,
)
from app.v2.services.workspace_analytics_query_service import (
    WorkspaceAnalyticsQueryService,
)

client = TestClient(app)

START = datetime(
    2026,
    8,
    12,
    0,
    0,
    tzinfo=UTC,
)
END = START + timedelta(days=1)


def _memory_services() -> V2Services:
    return V2Services(
        persistence_settings=(
            V2PersistenceSettings(
                backend=PersistenceBackend.MEMORY,
                sqlite_path=None,
                database_url=None,
            )
        ),
    )


def _sqlite_services(
    database_path: Path,
) -> V2Services:
    return V2Services(
        persistence_settings=(
            V2PersistenceSettings(
                backend=PersistenceBackend.SQLITE,
                sqlite_path=database_path,
                database_url=None,
            )
        ),
    )


def _workspace(
    services: V2Services,
    *,
    email: str = "owner@example.com",
) -> tuple[str, str]:
    user = services.workspace.create_user(
        email=email,
        display_name="Owner",
    )

    workspace = services.workspace_provisioning.create_workspace(
        user_id=user.user_id,
        name="Adversarial Workspace",
    )

    return (
        workspace.workspace_id,
        user.user_id,
    )


def _event(
    event_id: str,
    *,
    workspace_id: str,
    user_id: str,
    occurred_at: datetime,
) -> PersistentObservabilityEvent:
    return PersistentObservabilityEvent(
        event_id=event_id,
        workspace_id=workspace_id,
        user_id=user_id,
        operation=(ObservabilityOperation.SINGLE_REWRITE),
        outcome=(ObservabilityOutcome.SUCCEEDED),
        occurred_at=occurred_at,
        duration_ms=1.0,
        input_char_count=10,
        output_char_count=12,
        provider_execution_count=1,
        provider_name="provider-test",
        fallback_used=False,
        token_usage=ObservabilityTokenUsage(
            input_tokens=2,
            output_tokens=3,
            total_tokens=5,
        ),
        rewrite_history_id=(f"history_{event_id}"),
    )


def test_sqlite_restart_preserves_workspace_analytics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "observability-restart.sqlite3"

    first = _sqlite_services(database_path)

    workspace_id, user_id = _workspace(first)

    recorded = first.observability_recording.record(
        ObservabilityRecordInput(
            workspace_id=workspace_id,
            user_id=user_id,
            operation=(ObservabilityOperation.SINGLE_REWRITE),
            outcome=(ObservabilityOutcome.SUCCEEDED),
            duration_ms=20.0,
            input_char_count=100,
            output_char_count=125,
            provider_execution_count=1,
            provider_name="provider-test",
            fallback_used=False,
            token_usage=(
                ObservabilityTokenUsage(
                    input_tokens=11,
                    output_tokens=7,
                    total_tokens=18,
                )
            ),
            rewrite_history_id=("history_restart"),
        )
    )

    restarted = _sqlite_services(database_path)

    monkeypatch.setattr(
        v2_routes,
        "services",
        restarted,
    )

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": user_id,
            "period_start": (recorded.occurred_at - timedelta(seconds=1)).isoformat(),
            "period_end": (recorded.occurred_at + timedelta(seconds=1)).isoformat(),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["event_count"] == 1
    assert payload["succeeded_count"] == 1
    assert payload["total_tokens"] == 18


def test_sqlite_restart_preserves_membership_denial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "observability-auth-restart.sqlite3"

    first = _sqlite_services(database_path)

    workspace_id, owner_id = _workspace(first)

    outsider = first.workspace.create_user(
        email="outsider@example.com",
        display_name="Outsider",
    )

    recorded = first.observability_recording.record(
        ObservabilityRecordInput(
            workspace_id=workspace_id,
            user_id=owner_id,
            operation=(ObservabilityOperation.SINGLE_REWRITE),
            outcome=(ObservabilityOutcome.SUCCEEDED),
            duration_ms=1.0,
            input_char_count=1,
            output_char_count=1,
            token_usage=(
                ObservabilityTokenUsage(
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                )
            ),
            rewrite_history_id=("history_private"),
        )
    )

    restarted = _sqlite_services(database_path)

    monkeypatch.setattr(
        v2_routes,
        "services",
        restarted,
    )

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": outsider.user_id,
            "period_start": (recorded.occurred_at - timedelta(seconds=1)).isoformat(),
            "period_end": (recorded.occurred_at + timedelta(seconds=1)).isoformat(),
        },
    )

    assert response.status_code == 403


def test_analytics_api_fails_closed_on_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _memory_services()

    workspace_id, user_id = _workspace(services)

    repository = InMemoryObservabilityEventRepository()

    for index in range(3):
        repository.create(
            _event(
                f"event_{index}",
                workspace_id=workspace_id,
                user_id=user_id,
                occurred_at=(START + timedelta(minutes=index)),
            )
        )

    services.workspace_analytics = WorkspaceAnalyticsQueryService(
        repository=repository,
        aggregator=(WorkspaceAnalyticsAggregator()),
        event_limit=2,
        authorization_gate=allow_all_workspace_authorization_gate(),
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        services,
    )

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": user_id,
            "period_start": START.isoformat(),
            "period_end": END.isoformat(),
        },
    )

    assert response.status_code == 409
    assert "narrow the query window" in response.json()["detail"]


def test_analytics_api_rejects_malformed_datetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _memory_services()

    workspace_id, user_id = _workspace(services)

    monkeypatch.setattr(
        v2_routes,
        "services",
        services,
    )

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": user_id,
            "period_start": "not-a-datetime",
            "period_end": END.isoformat(),
        },
    )

    assert response.status_code == 422


def test_analytics_response_does_not_echo_raw_rewrite_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _memory_services()

    workspace_id, user_id = _workspace(services)

    monkeypatch.setattr(
        v2_routes,
        "services",
        services,
    )

    raw_text = "Distinctive private source text ALPHA-RAW-987654."

    period_start = datetime.now(UTC) - timedelta(seconds=2)

    rewrite_response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/rewrites"),
        json={
            "user_id": user_id,
            "rewrite": {
                "text": raw_text,
                "document_type": "general",
                "audience": ("general audience"),
                "tone": "natural and clear",
                "intensity": ("natural_rewrite"),
                "preserve_numbers": True,
                "preserve_dates": True,
            },
        },
    )

    assert rewrite_response.status_code == 200

    period_end = datetime.now(UTC) + timedelta(seconds=2)

    analytics_response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": user_id,
            "period_start": (period_start.isoformat()),
            "period_end": (period_end.isoformat()),
        },
    )

    assert analytics_response.status_code == 200
    assert analytics_response.json()["event_count"] == 1
    assert raw_text not in analytics_response.text
    assert "source_text" not in analytics_response.text
    assert "rewritten_text" not in analytics_response.text


def test_metrics_whitespace_configuration_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_METRICS_BEARER_TOKEN",
        "   ",
    )

    response = client.get("/metrics")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "authorization",
    (
        "bearer expected-token",
        "Basic expected-token",
        "Bearer",
        "Bearer  expected-token",
    ),
)
def test_metrics_reject_malformed_authorization(
    authorization: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_METRICS_BEARER_TOKEN",
        "expected-token",
    )

    response = client.get(
        "/metrics",
        headers={
            "Authorization": authorization,
        },
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "authorization",
    (
        "Bearer expected-token-extra",
        "Bearer prefix-expected-token",
    ),
)
def test_metrics_reject_non_exact_token_matches(
    authorization: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HUMANIZE_METRICS_BEARER_TOKEN",
        "expected-token",
    )

    response = client.get(
        "/metrics",
        headers={
            "Authorization": authorization,
        },
    )

    assert response.status_code == 403


def test_health_and_ready_remain_available_when_metrics_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_METRICS_BEARER_TOKEN",
        raising=False,
    )

    health = client.get("/health")
    ready = client.get("/ready")
    metrics = client.get("/metrics")

    assert health.status_code == 200
    assert ready.status_code == 200
    assert metrics.status_code == 404


def test_v1_rewrite_remains_backward_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "HUMANIZE_METRICS_BEARER_TOKEN",
        raising=False,
    )

    response = client.post(
        "/api/v1/rewrites",
        json={
            "text": ("Furthermore, the team completed the migration in 30 days."),
            "document_type": "general",
            "audience": "general audience",
            "tone": "natural and clear",
            "intensity": "natural_rewrite",
            "preserve_numbers": True,
            "preserve_dates": True,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert "trace_id" in payload
    assert "rewritten_text" in payload
    assert "verification" in payload


def test_v2_rewrite_still_persists_history_and_observability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = _memory_services()

    workspace_id, user_id = _workspace(services)

    monkeypatch.setattr(
        v2_routes,
        "services",
        services,
    )

    period_start = datetime.now(UTC) - timedelta(seconds=2)

    response = client.post(
        (f"/api/v2/workspaces/{workspace_id}/rewrites"),
        json={
            "user_id": user_id,
            "rewrite": {
                "text": (
                    "Furthermore, it is important to note that the team completed the migration."
                ),
                "document_type": "general",
                "audience": ("general audience"),
                "tone": "natural and clear",
                "intensity": ("natural_rewrite"),
                "preserve_numbers": True,
                "preserve_dates": True,
            },
        },
    )

    assert response.status_code == 200

    rewrite_payload = response.json()

    history = client.get(
        (f"/api/v2/workspaces/{workspace_id}/history"),
        params={
            "user_id": user_id,
        },
    )

    assert history.status_code == 200
    assert len(history.json()["records"]) == 1

    period_end = datetime.now(UTC) + timedelta(seconds=2)

    analytics = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": user_id,
            "period_start": (period_start.isoformat()),
            "period_end": (period_end.isoformat()),
        },
    )

    assert analytics.status_code == 200

    analytics_payload = analytics.json()

    assert analytics_payload["event_count"] == 1
    assert rewrite_payload["history"]["rewrite_id"] is not None
