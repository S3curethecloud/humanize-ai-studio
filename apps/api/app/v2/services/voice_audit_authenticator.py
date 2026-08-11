from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from app.v2.domain.models import (
    VoiceRewriteAnalysisAuthenticity,
    VoiceRewriteAnalysisSnapshot,
)

_AUTHENTICATION_DOMAIN = b"humanize-ai-studio:voice-rewrite-analysis-snapshot:authenticity-v1:"


@dataclass(frozen=True)
class VoiceAuditHmacKey:
    key_id: str
    secret: bytes

    def __post_init__(self) -> None:
        if not self.key_id.strip():
            raise ValueError("Voice audit HMAC key_id must be non-empty.")

        if len(self.secret) < 32:
            raise ValueError("Voice audit HMAC secret must be at least 32 bytes.")


@dataclass(frozen=True)
class VoiceAuditHmacKeyring:
    active_key_id: str
    keys: tuple[VoiceAuditHmacKey, ...]

    def __post_init__(self) -> None:
        if not self.active_key_id.strip():
            raise ValueError("Voice audit active key ID must be non-empty.")

        key_ids = tuple(key.key_id for key in self.keys)

        if len(set(key_ids)) != len(key_ids):
            raise ValueError("Voice audit HMAC key IDs must be unique.")

        if self.active_key_id not in key_ids:
            raise ValueError("Voice audit active key is not present in the keyring.")

    def active_key(
        self,
    ) -> VoiceAuditHmacKey:
        for key in self.keys:
            if key.key_id == self.active_key_id:
                return key

        raise RuntimeError("Voice audit active key is unavailable.")

    def get(
        self,
        key_id: str,
    ) -> VoiceAuditHmacKey | None:
        for key in self.keys:
            if key.key_id == key_id:
                return key

        return None


class VoiceAuditAuthenticator:
    def __init__(
        self,
        *,
        key: VoiceAuditHmacKey | None = None,
        keyring: VoiceAuditHmacKeyring | None = None,
    ) -> None:
        if (key is None) == (keyring is None):
            raise ValueError("Provide exactly one Voice audit HMAC key or keyring.")

        if keyring is not None:
            self._keyring = keyring
        else:
            assert key is not None

            self._keyring = VoiceAuditHmacKeyring(
                active_key_id=key.key_id,
                keys=(key,),
            )

    def sign(
        self,
        snapshot: VoiceRewriteAnalysisSnapshot,
    ) -> VoiceRewriteAnalysisAuthenticity:
        key = self._keyring.active_key()

        mac = hmac.new(
            key.secret,
            self._message(snapshot),
            hashlib.sha256,
        ).hexdigest()

        return VoiceRewriteAnalysisAuthenticity(
            key_id=key.key_id,
            mac=mac,
        )

    def verify(
        self,
        *,
        snapshot: VoiceRewriteAnalysisSnapshot,
        authenticity: VoiceRewriteAnalysisAuthenticity,
    ) -> bool:
        key = self._keyring.get(authenticity.key_id)

        if key is None:
            return False

        expected_mac = hmac.new(
            key.secret,
            self._message(snapshot),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(
            authenticity.mac,
            expected_mac,
        )

    @staticmethod
    def _message(
        snapshot: VoiceRewriteAnalysisSnapshot,
    ) -> bytes:
        return _AUTHENTICATION_DOMAIN + snapshot.canonical_bytes()
