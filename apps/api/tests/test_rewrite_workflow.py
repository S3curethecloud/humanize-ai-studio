from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rewrite_removes_formulaic_language_and_preserves_number() -> None:
    response = client.post(
        "/api/v1/rewrites",
        json={
            "text": (
                "Furthermore, it is important to note that "
                "the team completed the project in 30 days."
            ),
            "document_type": "professional_email",
            "audience": "executive stakeholder",
            "tone": "direct and professional",
            "intensity": "natural_rewrite",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["rewritten_text"] == "The team completed the project in 30 days."
    assert body["verification"]["decision"] == "pass"
    assert body["verification"]["missing_facts"] == []
    assert body["workflow_states"][-1] == "ready_for_review"
    assert any(fact["value"] == "30" for fact in body["protected_facts"])


def test_empty_text_is_rejected() -> None:
    response = client.post(
        "/api/v1/rewrites",
        json={
            "text": "",
        },
    )

    assert response.status_code == 422


def test_date_is_preserved() -> None:
    response = client.post(
        "/api/v1/rewrites",
        json={
            "text": ("In conclusion, the architecture review is scheduled for August 4, 2026."),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "August 4, 2026" in body["rewritten_text"]
    assert body["verification"]["decision"] == "pass"
