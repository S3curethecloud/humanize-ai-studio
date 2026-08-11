from __future__ import annotations

import json
import os
from dataclasses import dataclass

from app.v2.services.voice_audit_authenticator import (
    VoiceAuditAuthenticator,
    VoiceAuditHmacKey,
    VoiceAuditHmacKeyring,
)


@dataclass(frozen=True)
class VoiceAuditAuthenticitySettings:
    enabled: bool
    active_key_id: str | None
    keys: tuple[VoiceAuditHmacKey, ...]

    @classmethod
    def from_environment(
        cls,
    ) -> VoiceAuditAuthenticitySettings:
        enabled = _parse_bool(
            "HUMANIZE_V2_VOICE_AUDIT_AUTH_ENABLED",
            default=False,
        )

        if not enabled:
            return cls(
                enabled=False,
                active_key_id=None,
                keys=(),
            )

        active_key_id = _required_value("HUMANIZE_V2_VOICE_AUDIT_HMAC_ACTIVE_KEY_ID")

        raw_keys = _required_value("HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON")

        keys = _parse_keyring(raw_keys)

        settings = cls(
            enabled=True,
            active_key_id=active_key_id,
            keys=keys,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.enabled:
            return

        if self.active_key_id is None:
            raise ValueError("Voice audit authenticity requires an active key ID.")

        key_ids = {key.key_id for key in self.keys}

        if self.active_key_id not in key_ids:
            raise ValueError(
                "Voice audit active HMAC key is not present in the configured keyring."
            )

    def build_authenticator(
        self,
    ) -> VoiceAuditAuthenticator | None:
        if not self.enabled:
            return None

        assert self.active_key_id is not None

        return VoiceAuditAuthenticator(
            keyring=VoiceAuditHmacKeyring(
                active_key_id=self.active_key_id,
                keys=self.keys,
            )
        )


def _parse_keyring(
    raw_value: str,
) -> tuple[VoiceAuditHmacKey, ...]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON must contain valid JSON.") from exc

    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("HUMANIZE_V2_VOICE_AUDIT_HMAC_KEYS_JSON must be a non-empty JSON object.")

    keys: list[VoiceAuditHmacKey] = []

    for key_id, encoded_secret in parsed.items():
        if not isinstance(key_id, str):
            raise ValueError("Voice audit HMAC key IDs must be strings.")

        if not isinstance(encoded_secret, str):
            raise ValueError("Voice audit HMAC secrets must be hex strings.")

        try:
            secret = bytes.fromhex(encoded_secret)
        except ValueError as exc:
            raise ValueError("Voice audit HMAC secrets must be valid hex.") from exc

        keys.append(
            VoiceAuditHmacKey(
                key_id=key_id,
                secret=secret,
            )
        )

    return tuple(keys)


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

    raise ValueError(f"{name} must be a boolean value.")


def _required_value(
    name: str,
) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(f"{name} is required when Voice DNA audit authenticity is enabled.")

    return value.strip()
