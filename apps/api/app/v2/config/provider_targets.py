from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
)
from app.v2.services.provider_execution_factory import (
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
)

PROVIDER_TARGETS_ENVIRONMENT_VARIABLE = (
    "HUMANIZE_V2_PROVIDER_TARGETS_JSON"
)

DEFAULT_DETERMINISTIC_TARGET_ID = (
    "deterministic-primary"
)


@dataclass(
    frozen=True,
    slots=True,
)
class ProviderTargetDeclarationSettings:
    targets: tuple[ProviderModelTarget, ...]

    @classmethod
    def from_environment(
        cls,
    ) -> ProviderTargetDeclarationSettings:
        raw = os.getenv(
            PROVIDER_TARGETS_ENVIRONMENT_VARIABLE
        )

        if raw is None or not raw.strip():
            return cls(
                targets=(
                    _default_deterministic_target(),
                ),
            )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{PROVIDER_TARGETS_ENVIRONMENT_VARIABLE} "
                "must contain valid JSON."
            ) from exc

        if not isinstance(payload, list):
            raise ValueError(
                f"{PROVIDER_TARGETS_ENVIRONMENT_VARIABLE} "
                "must contain a JSON array."
            )

        if not payload:
            raise ValueError(
                f"{PROVIDER_TARGETS_ENVIRONMENT_VARIABLE} "
                "must declare at least one provider target."
            )

        targets = tuple(
            _parse_target(
                item=item,
                index=index,
            )
            for index, item in enumerate(payload)
        )

        settings = cls(
            targets=targets,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.targets:
            raise ValueError(
                "provider target settings require "
                "at least one target."
            )

        target_ids = tuple(
            target.target_id
            for target in self.targets
        )

        if len(set(target_ids)) != len(
            target_ids
        ):
            raise ValueError(
                "provider target declarations "
                "must have unique target IDs."
            )

        provider_models = tuple(
            (
                target.provider.provider_id,
                target.model.model_id,
            )
            for target in self.targets
        )

        if len(set(provider_models)) != len(
            provider_models
        ):
            raise ValueError(
                "provider target declarations must "
                "have unique provider/model pairs."
            )


def _default_deterministic_target(
) -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=DEFAULT_DETERMINISTIC_TARGET_ID,
        provider=ProviderIdentity(
            provider_id=DETERMINISTIC_PROVIDER_ID,
            display_name="Deterministic",
        ),
        model=ModelIdentity(
            provider_id=DETERMINISTIC_PROVIDER_ID,
            model_id=DETERMINISTIC_MODEL_ID,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            ),
        ),
        enabled=True,
    )


def _parse_target(
    *,
    item: Any,
    index: int,
) -> ProviderModelTarget:
    if not isinstance(item, dict):
        raise ValueError(
            f"{PROVIDER_TARGETS_ENVIRONMENT_VARIABLE} "
            f"entry {index} must be a JSON object."
        )

    try:
        return ProviderModelTarget.model_validate(
            item
        )
    except ValidationError as exc:
        raise ValueError(
            f"{PROVIDER_TARGETS_ENVIRONMENT_VARIABLE} "
            f"entry {index} is invalid."
        ) from exc
