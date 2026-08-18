from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app.v2.api.routes as v2_routes
from app.main import app
from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.services.enterprise_quota_admin_service import (
    EnterpriseQuotaAdministrationError,
    QuotaAdministrationFailureReason,
)

client = TestClient(app)


def _quota_limit() -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id="limit_requests",
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        window=EnterpriseQuotaWindow(
            window_start=datetime(
                2026,
                8,
                1,
                tzinfo=UTC,
            ),
            window_end=datetime(
                2026,
                9,
                1,
                tzinfo=UTC,
            ),
        ),
        limit=100,
    )


def _create_payload() -> dict[str, object]:
    return {
        "actor_user_id": "user_admin",
        "quota_limit_id": "limit_requests",
        "dimension": "rewrite_requests",
        "window": {
            "window_start": "2026-08-01T00:00:00+00:00",
            "window_end": "2026-09-01T00:00:00+00:00",
        },
        "limit": 100,
    }


def setup_function() -> None:
    v2_routes.services.quota_admin = MagicMock()


def test_create_quota_limit_binds_workspace_path() -> None:
    quota_admin = v2_routes.services.quota_admin
    quota_admin.create_limit.return_value = _quota_limit()

    response = client.post(
        "/api/v2/workspaces/workspace_test/quota-limits",
        json=_create_payload(),
    )

    assert response.status_code == 201
    assert response.json()["quota_limit"]["workspace_id"] == (
        "workspace_test"
    )

    call = quota_admin.create_limit.call_args

    assert call.kwargs["actor_user_id"] == "user_admin"
    assert call.kwargs["workspace_id"] == "workspace_test"
    assert (
        call.kwargs["quota_limit"].workspace_id
        == "workspace_test"
    )


def test_create_quota_limit_rejects_body_workspace_id() -> None:
    payload = _create_payload()
    payload["workspace_id"] = "workspace_other"

    response = client.post(
        "/api/v2/workspaces/workspace_test/quota-limits",
        json=payload,
    )

    assert response.status_code == 422


def test_create_quota_limit_maps_authorization_denied() -> None:
    v2_routes.services.quota_admin.create_limit.side_effect = (
        EnterpriseQuotaAdministrationError(
            QuotaAdministrationFailureReason.AUTHORIZATION_DENIED
        )
    )

    response = client.post(
        "/api/v2/workspaces/workspace_test/quota-limits",
        json=_create_payload(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "authorization_denied"


def test_create_quota_limit_maps_repository_conflict() -> None:
    v2_routes.services.quota_admin.create_limit.side_effect = (
        ValueError(
            "enterprise quota limit overlaps existing authority"
        )
    )

    response = client.post(
        "/api/v2/workspaces/workspace_test/quota-limits",
        json=_create_payload(),
    )

    assert response.status_code == 409


def test_get_quota_limit() -> None:
    v2_routes.services.quota_admin.get_limit.return_value = (
        _quota_limit()
    )

    response = client.get(
        (
            "/api/v2/workspaces/workspace_test/"
            "quota-limits/limit_requests"
        ),
        params={
            "actor_user_id": "user_viewer",
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["quota_limit"]["quota_limit_id"]
        == "limit_requests"
    )

    v2_routes.services.quota_admin.get_limit.assert_called_once_with(
        actor_user_id="user_viewer",
        workspace_id="workspace_test",
        quota_limit_id="limit_requests",
    )


def test_get_quota_limit_maps_not_found() -> None:
    v2_routes.services.quota_admin.get_limit.side_effect = (
        EnterpriseQuotaAdministrationError(
            QuotaAdministrationFailureReason.LIMIT_NOT_FOUND
        )
    )

    response = client.get(
        (
            "/api/v2/workspaces/workspace_test/"
            "quota-limits/missing"
        ),
        params={
            "actor_user_id": "user_viewer",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "limit_not_found"


def test_get_quota_limit_maps_resolution_failure() -> None:
    v2_routes.services.quota_admin.get_limit.side_effect = (
        EnterpriseQuotaAdministrationError(
            QuotaAdministrationFailureReason.AUTHORIZATION_RESOLUTION_FAILED
        )
    )

    response = client.get(
        (
            "/api/v2/workspaces/workspace_test/"
            "quota-limits/limit_requests"
        ),
        params={
            "actor_user_id": "user_viewer",
        },
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "authorization_resolution_failed"
    )


def test_list_quota_limits() -> None:
    v2_routes.services.quota_admin.list_limits.return_value = (
        _quota_limit(),
    )

    response = client.get(
        "/api/v2/workspaces/workspace_test/quota-limits",
        params={
            "actor_user_id": "user_viewer",
            "dimension": "rewrite_requests",
            "limit": 25,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["workspace_id"] == "workspace_test"
    assert body["dimension"] == "rewrite_requests"
    assert len(body["quota_limits"]) == 1

    v2_routes.services.quota_admin.list_limits.assert_called_once_with(
        actor_user_id="user_viewer",
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        limit=25,
    )


def test_list_quota_limits_maps_authorization_denied() -> None:
    v2_routes.services.quota_admin.list_limits.side_effect = (
        EnterpriseQuotaAdministrationError(
            QuotaAdministrationFailureReason.AUTHORIZATION_DENIED
        )
    )

    response = client.get(
        "/api/v2/workspaces/workspace_test/quota-limits",
        params={
            "actor_user_id": "user_viewer",
            "dimension": "rewrite_requests",
        },
    )

    assert response.status_code == 403


def test_actor_identity_is_required_for_reads() -> None:
    response = client.get(
        (
            "/api/v2/workspaces/workspace_test/"
            "quota-limits/limit_requests"
        ),
    )

    assert response.status_code == 422


def test_list_limit_is_bounded_by_api_contract() -> None:
    response = client.get(
        "/api/v2/workspaces/workspace_test/quota-limits",
        params={
            "actor_user_id": "user_viewer",
            "dimension": "rewrite_requests",
            "limit": 10001,
        },
    )

    assert response.status_code == 422
