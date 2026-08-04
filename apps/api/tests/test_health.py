from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "humanize-ai-studio-api",
        "mode": "deterministic",
        "configured_provider": "deterministic",
        "active_provider": "deterministic",
    }


def test_readiness_endpoint() -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "humanize-ai-studio-api",
        "configured_provider": "deterministic",
        "active_provider": "deterministic",
    }
