from __future__ import annotations

import os
from hmac import compare_digest

EVIDENCE_BEARER_TOKEN_ENV = (
    "HUMANIZE_V2_EVIDENCE_BEARER_TOKEN"
)


class EvidenceExposureDisabledError(RuntimeError):
    pass


class EvidenceAccessDeniedError(PermissionError):
    pass


def require_evidence_access(
    *,
    authorization: str | None,
) -> None:
    configured_token = os.getenv(
        EVIDENCE_BEARER_TOKEN_ENV,
        "",
    ).strip()

    if not configured_token:
        raise EvidenceExposureDisabledError(
            "evidence exposure is disabled"
        )

    prefix = "Bearer "

    if (
        authorization is None
        or not authorization.startswith(prefix)
    ):
        raise EvidenceAccessDeniedError(
            "evidence authorization required"
        )

    supplied_token = authorization[len(prefix) :]

    if (
        not supplied_token
        or not compare_digest(
            supplied_token,
            configured_token,
        )
    ):
        raise EvidenceAccessDeniedError(
            "evidence authorization failed"
        )
