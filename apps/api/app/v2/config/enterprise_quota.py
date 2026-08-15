from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseQuotaActivationSettings:
    enabled: bool

    @classmethod
    def from_environment(
        cls,
    ) -> EnterpriseQuotaActivationSettings:
        return cls(
            enabled=_parse_bool(
                "HUMANIZE_V2_ENTERPRISE_QUOTA_ENABLED",
                default=False,
            )
        )


def _parse_bool(
    name: str,
    *,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if normalized in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False

    raise ValueError(
        f"{name} must be a boolean value."
    )
