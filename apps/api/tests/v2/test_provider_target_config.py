from __future__ import annotations

import json

import pytest

from app.v2.config.provider_targets import (
    DEFAULT_DETERMINISTIC_TARGET_ID,
    PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
    ProviderTargetDeclarationSettings,
)
from app.v2.domain.provider_routing import (
    ProviderCapability,
)
from app.v2.services.provider_execution_factory import (
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
)


def _target_payload(
    *,
    target_id: str,
    provider_id: str,
    model_id: str,
    enabled: bool = True,
) -> dict[str, object]:
    return {
        "target_id": target_id,
        "provider": {
            "provider_id": provider_id,
            "display_name": provider_id,
        },
        "model": {
            "provider_id": provider_id,
            "model_id": model_id,
        },
        "capabilities": {
            "capabilities": [
                "rewrite",
            ],
        },
        "enabled": enabled,
    }


def test_environment_absence_declares_only_deterministic_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        raising=False,
    )

    settings = (
        ProviderTargetDeclarationSettings
        .from_environment()
    )

    assert len(settings.targets) == 1

    target = settings.targets[0]

    assert (
        target.target_id
        == DEFAULT_DETERMINISTIC_TARGET_ID
    )
    assert (
        target.provider.provider_id
        == DETERMINISTIC_PROVIDER_ID
    )
    assert (
        target.model.model_id
        == DETERMINISTIC_MODEL_ID
    )
    assert target.enabled is True
    assert target.capabilities.capabilities == frozenset(
        {
            ProviderCapability.REWRITE,
        }
    )


def test_blank_environment_preserves_deterministic_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        "   ",
    )

    settings = (
        ProviderTargetDeclarationSettings
        .from_environment()
    )

    assert tuple(
        target.target_id
        for target in settings.targets
    ) == (
        DEFAULT_DETERMINISTIC_TARGET_ID,
    )


def test_explicit_targets_replace_default_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        _target_payload(
            target_id="cloudflare-primary",
            provider_id="cloudflare-workers-ai",
            model_id="@cf/catalog/model",
        ),
        _target_payload(
            target_id="openai-secondary",
            provider_id="openai",
            model_id="gpt-5-mini",
            enabled=False,
        ),
    ]

    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        json.dumps(payload),
    )

    settings = (
        ProviderTargetDeclarationSettings
        .from_environment()
    )

    assert tuple(
        target.target_id
        for target in settings.targets
    ) == (
        "cloudflare-primary",
        "openai-secondary",
    )

    assert settings.targets[0].enabled is True
    assert settings.targets[1].enabled is False


def test_explicit_deterministic_target_is_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        _target_payload(
            target_id="rules",
            provider_id=DETERMINISTIC_PROVIDER_ID,
            model_id=DETERMINISTIC_MODEL_ID,
        ),
    ]

    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        json.dumps(payload),
    )

    settings = (
        ProviderTargetDeclarationSettings
        .from_environment()
    )

    assert settings.targets[0].target_id == "rules"


def test_invalid_json_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        "{not-json",
    )

    with pytest.raises(
        ValueError,
        match="must contain valid JSON",
    ):
        (
            ProviderTargetDeclarationSettings
            .from_environment()
        )


def test_non_array_json_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        json.dumps(
            {
                "target_id": "primary",
            }
        ),
    )

    with pytest.raises(
        ValueError,
        match="must contain a JSON array",
    ):
        (
            ProviderTargetDeclarationSettings
            .from_environment()
        )


def test_empty_array_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        "[]",
    )

    with pytest.raises(
        ValueError,
        match="at least one provider target",
    ):
        (
            ProviderTargetDeclarationSettings
            .from_environment()
        )


def test_non_object_entry_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        json.dumps(
            [
                "provider",
            ]
        ),
    )

    with pytest.raises(
        ValueError,
        match="entry 0 must be a JSON object",
    ):
        (
            ProviderTargetDeclarationSettings
            .from_environment()
        )


def test_invalid_target_domain_payload_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        _target_payload(
            target_id="primary",
            provider_id="provider-a",
            model_id="model-a",
        ),
    ]
    payload[0]["model"] = {
        "provider_id": "provider-b",
        "model_id": "model-a",
    }

    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        json.dumps(payload),
    )

    with pytest.raises(
        ValueError,
        match="entry 0 is invalid",
    ):
        (
            ProviderTargetDeclarationSettings
            .from_environment()
        )


def test_duplicate_target_ids_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        _target_payload(
            target_id="primary",
            provider_id="provider-a",
            model_id="model-a",
        ),
        _target_payload(
            target_id="primary",
            provider_id="provider-b",
            model_id="model-b",
        ),
    ]

    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        json.dumps(payload),
    )

    with pytest.raises(
        ValueError,
        match="unique target IDs",
    ):
        (
            ProviderTargetDeclarationSettings
            .from_environment()
        )


def test_duplicate_provider_model_pairs_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        _target_payload(
            target_id="primary",
            provider_id="provider",
            model_id="model",
        ),
        _target_payload(
            target_id="secondary",
            provider_id="provider",
            model_id="model",
        ),
    ]

    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        json.dumps(payload),
    )

    with pytest.raises(
        ValueError,
        match="unique provider/model pairs",
    ):
        (
            ProviderTargetDeclarationSettings
            .from_environment()
        )


def test_unknown_target_fields_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = [
        _target_payload(
            target_id="primary",
            provider_id="provider",
            model_id="model",
        ),
    ]
    payload[0]["api_key"] = "must-not-be-accepted"

    monkeypatch.setenv(
        PROVIDER_TARGETS_ENVIRONMENT_VARIABLE,
        json.dumps(payload),
    )

    with pytest.raises(
        ValueError,
        match="entry 0 is invalid",
    ):
        (
            ProviderTargetDeclarationSettings
            .from_environment()
        )
