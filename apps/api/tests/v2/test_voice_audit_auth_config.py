from __future__ import annotations

import json

import pytest

from app.v2.config.voice_audit_auth import (
    VoiceAuditAuthenticitySettings,
)

_ENVIRONMENT_NAMES = (
    "HUMANIZE_V2_VOICE_AUDIT_AUTH_ENABLED",
    "HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID",
    "HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON",
)


def _clear_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in _ENVIRONMENT_NAMES:
        monkeypatch.delenv(
            name,
            raising=False,
        )


def test_voice_audit_auth_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)

    settings = VoiceAuditAuthenticitySettings.from_environment()

    assert not settings.enabled
    assert settings.active_key_id is None
    assert settings.keys == ()
    assert settings.build_authenticator() is None


def test_enabled_voice_audit_auth_builds_versioned_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)

    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID",
        "voice-audit-key-v2",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON",
        json.dumps(
            {
                "voice-audit-key-v1": (b"a" * 32).hex(),
                "voice-audit-key-v2": (b"b" * 32).hex(),
            }
        ),
    )

    settings = VoiceAuditAuthenticitySettings.from_environment()

    assert settings.enabled
    assert settings.active_key_id == "voice-audit-key-v2"
    assert {key.key_id for key in settings.keys} == {
        "voice-audit-key-v1",
        "voice-audit-key-v2",
    }

    authenticator = settings.build_authenticator()

    assert authenticator is not None


@pytest.mark.parametrize(
    "missing_name",
    (
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID",
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON",
    ),
)
def test_enabled_voice_audit_auth_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
    missing_name: str,
) -> None:
    _clear_environment(monkeypatch)

    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID",
        "voice-audit-key-v1",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON",
        json.dumps(
            {
                "voice-audit-key-v1": (b"a" * 32).hex(),
            }
        ),
    )

    monkeypatch.delenv(
        missing_name,
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="required",
    ):
        VoiceAuditAuthenticitySettings.from_environment()


def test_enabled_voice_audit_auth_requires_active_key_in_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)

    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID",
        "voice-audit-key-v2",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON",
        json.dumps(
            {
                "voice-audit-key-v1": (b"a" * 32).hex(),
            }
        ),
    )

    with pytest.raises(
        ValueError,
        match="not present",
    ):
        VoiceAuditAuthenticitySettings.from_environment()


def test_enabled_voice_audit_auth_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)

    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID",
        "voice-audit-key-v1",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON",
        "{not-json}",
    )

    with pytest.raises(
        ValueError,
        match="valid JSON",
    ):
        VoiceAuditAuthenticitySettings.from_environment()


def test_enabled_voice_audit_auth_rejects_invalid_hex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)

    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID",
        "voice-audit-key-v1",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON",
        json.dumps(
            {
                "voice-audit-key-v1": "not-hex",
            }
        ),
    )

    with pytest.raises(
        ValueError,
        match="valid hex",
    ):
        VoiceAuditAuthenticitySettings.from_environment()


def test_enabled_voice_audit_auth_rejects_short_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_environment(monkeypatch)

    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_AUTH_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID",
        "voice-audit-key-v1",
    )
    monkeypatch.setenv(
        "HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON",
        json.dumps(
            {
                "voice-audit-key-v1": (b"a" * 31).hex(),
            }
        ),
    )

    with pytest.raises(
        ValueError,
        match="at least 32 bytes",
    ):
        VoiceAuditAuthenticitySettings.from_environment()
