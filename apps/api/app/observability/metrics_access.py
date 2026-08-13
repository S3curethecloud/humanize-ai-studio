from __future__ import annotations

import os
from hmac import compare_digest

METRICS_BEARER_TOKEN_ENV = "HUMANIZE_METRICS_BEARER_TOKEN"


class MetricsExposureDisabledError(RuntimeError):
    pass


class MetricsAccessDeniedError(PermissionError):
    pass


def require_metrics_access(
    *,
    authorization: str | None,
) -> None:
    configured_token = os.getenv(
        METRICS_BEARER_TOKEN_ENV,
        "",
    ).strip()

    if not configured_token:
        raise MetricsExposureDisabledError("metrics exposure is disabled")

    prefix = "Bearer "

    if authorization is None or not authorization.startswith(prefix):
        raise MetricsAccessDeniedError("metrics authorization required")

    supplied_token = authorization[len(prefix) :]

    if not supplied_token or not compare_digest(
        supplied_token,
        configured_token,
    ):
        raise MetricsAccessDeniedError("metrics authorization failed")
