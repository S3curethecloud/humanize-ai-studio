from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from app.main import app
from app.observability.context import (
    reset_request_id,
    set_request_id,
)
from app.observability.logging import JsonLogFormatter
from app.observability.metrics import metrics_registry

client = TestClient(app)


def test_generated_request_id_is_returned() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert request_id.startswith("request_")
    assert len(request_id) > len("request_")


def test_valid_supplied_request_id_is_preserved() -> None:
    response = client.get(
        "/health",
        headers={
            "X-Request-ID": "client-request-123",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-request-123"


def test_invalid_request_id_is_replaced() -> None:
    response = client.get(
        "/health",
        headers={
            "X-Request-ID": "invalid request id",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "invalid request id"
    assert response.headers["X-Request-ID"].startswith("request_")


def test_json_formatter_includes_context_fields() -> None:
    formatter = JsonLogFormatter()
    token = set_request_id("request-log-test")

    try:
        record = logging.LogRecord(
            name="humanize.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="test_event",
            args=(),
            exc_info=None,
        )
        record.event_fields = {
            "event": "test_event",
            "decision": "minimal_edit",
        }

        payload = json.loads(formatter.format(record))
    finally:
        reset_request_id(token)

    assert payload["level"] == "info"
    assert payload["message"] == "test_event"
    assert payload["request_id"] == "request-log-test"
    assert payload["event"] == "test_event"
    assert payload["decision"] == "minimal_edit"


def test_metrics_expose_request_and_rewrite_counters() -> None:
    metrics_registry.reset_for_tests()

    rewrite_response = client.post(
        "/api/v1/rewrites",
        headers={
            "X-Request-ID": "metrics-test-request",
        },
        json={
            "text": ("Furthermore, the migration completed in 30 days."),
            "document_type": "general",
            "audience": "general audience",
            "tone": "natural and clear",
            "intensity": "natural_rewrite",
            "preserve_numbers": True,
            "preserve_dates": True,
        },
    )

    assert rewrite_response.status_code == 200

    metrics_response = client.get("/metrics")

    assert metrics_response.status_code == 200

    body = metrics_response.text

    assert (
        'humanize_http_requests_total{method="POST",'
        'route="/api/v1/rewrites",status="200"} 1' in body
    )
    assert 'humanize_rewrite_decisions_total{decision="minimal_edit"} 1' in body
    assert 'humanize_provider_executions_total{provider="rewrite-necessity-analyzer"} 1' in body
    assert 'humanize_rewrite_fallback_total{used="false"} 1' in body
    assert "humanize_http_request_duration_seconds_sum" in body
