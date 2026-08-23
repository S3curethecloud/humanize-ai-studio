from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.api.dependencies import (
    V2Services,
)
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.domain.observability import (
    ObservabilityOperation,
    ObservabilityOutcome,
    ObservabilityTokenUsage,
)
from app.v2.services.observability_recording_service import (
    ObservabilityRecordInput,
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


@pytest.fixture
def services(
    monkeypatch: pytest.MonkeyPatch,
) -> V2Services:
    test_services = V2Services(
        persistence_settings=(
            V2PersistenceSettings(
                backend=(PersistenceBackend.MEMORY),
                sqlite_path=None,
                database_url=None,
            )
        ),
    )

    monkeypatch.setattr(
        v2_routes,
        "services",
        test_services,
    )

    return test_services


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _workspace(
    services: V2Services,
) -> tuple[str, str]:
    user = services.workspace.create_user(
        email="analytics@example.com",
        display_name="Analytics User",
    )

    workspace = services.workspace_provisioning.create_workspace(
        user_id=user.user_id,
        name="Analytics Workspace",
    )

    return (
        workspace.workspace_id,
        user.user_id,
    )


def test_workspace_analytics_api_returns_snapshot(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace_id, user_id = _workspace(services)

    recorded = services.observability_recording.record(
        ObservabilityRecordInput(
            workspace_id=workspace_id,
            user_id=user_id,
            operation=(ObservabilityOperation.SINGLE_REWRITE),
            outcome=(ObservabilityOutcome.SUCCEEDED),
            duration_ms=25.0,
            input_char_count=100,
            output_char_count=120,
            provider_execution_count=1,
            provider_name="provider-test",
            fallback_used=False,
            token_usage=(
                ObservabilityTokenUsage(
                    input_tokens=12,
                    output_tokens=8,
                    total_tokens=20,
                )
            ),
            rewrite_history_id=("history_api_test"),
        )
    )

    period_start = recorded.occurred_at - timedelta(seconds=1)
    period_end = recorded.occurred_at + timedelta(seconds=1)

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": user_id,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["workspace_id"] == workspace_id
    assert payload["event_count"] == 1
    assert payload["succeeded_count"] == 1
    assert payload["total_tokens"] == 20
    assert len(payload["operations"]) == 3


def test_workspace_analytics_api_requires_membership(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace_id, _ = _workspace(services)

    outsider = services.workspace.create_user(
        email="outsider@example.com",
        display_name="Outsider",
    )

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": outsider.user_id,
            "period_start": START.isoformat(),
            "period_end": END.isoformat(),
        },
    )

    assert response.status_code == 403


def test_workspace_analytics_api_rejects_invalid_window(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace_id, user_id = _workspace(services)

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": user_id,
            "period_start": END.isoformat(),
            "period_end": START.isoformat(),
        },
    )

    assert response.status_code == 400
    assert "period_end must be after" in response.json()["detail"]


def test_workspace_analytics_api_returns_empty_window(
    services: V2Services,
    client: TestClient,
) -> None:
    workspace_id, user_id = _workspace(services)

    response = client.get(
        (f"/api/v2/workspaces/{workspace_id}/analytics"),
        params={
            "user_id": user_id,
            "period_start": START.isoformat(),
            "period_end": END.isoformat(),
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["event_count"] == 0
    assert payload["total_tokens"] == 0
    assert len(payload["operations"]) == 3
