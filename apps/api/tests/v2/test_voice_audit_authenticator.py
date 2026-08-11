from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.v2.domain.models import (
    VoiceRewriteAnalysisSnapshot,
    VoiceStyleAttributes,
    VoiceWarmth,
)
from app.v2.services.voice_audit_authenticator import (
    VoiceAuditAuthenticator,
    VoiceAuditHmacKey,
)


def _snapshot() -> VoiceRewriteAnalysisSnapshot:
    return VoiceRewriteAnalysisSnapshot(
        analysis_state="current",
        analyzer_version="voice-dna-v1",
        analyzed_at=datetime(
            2026,
            8,
            11,
            12,
            0,
            tzinfo=UTC,
        ),
        source_sample_ids=("sample_1",),
        source_fingerprint="a" * 64,
        sample_count=1,
        sufficiency="limited",
        consistency="not_applicable",
        style_attributes=VoiceStyleAttributes(),
    )


def _authenticator(
    *,
    secret: bytes = b"k" * 32,
    key_id: str = "voice-audit-key-v1",
) -> VoiceAuditAuthenticator:
    return VoiceAuditAuthenticator(
        key=VoiceAuditHmacKey(
            key_id=key_id,
            secret=secret,
        )
    )


def test_voice_audit_hmac_is_deterministic() -> None:
    snapshot = _snapshot()
    authenticator = _authenticator()

    first = authenticator.sign(snapshot)
    second = authenticator.sign(snapshot)

    assert first == second
    assert first.algorithm == "hmac-sha256"
    assert first.authentication_version == "voice-snapshot-authenticity-v1"
    assert first.key_id == "voice-audit-key-v1"
    assert len(first.mac) == 64
    assert authenticator.verify(
        snapshot=snapshot,
        authenticity=first,
    )


def test_voice_audit_hmac_rejects_modified_snapshot() -> None:
    snapshot = _snapshot()
    authenticator = _authenticator()

    authenticity = authenticator.sign(snapshot)

    modified_style = snapshot.style_attributes.model_copy(
        update={
            "warmth": VoiceWarmth.WARM,
        }
    )

    modified_snapshot = snapshot.model_copy(
        update={
            "style_attributes": modified_style,
        }
    )

    assert not authenticator.verify(
        snapshot=modified_snapshot,
        authenticity=authenticity,
    )


def test_voice_audit_hmac_rejects_wrong_secret() -> None:
    snapshot = _snapshot()

    signer = _authenticator(
        secret=b"a" * 32,
    )
    verifier = _authenticator(
        secret=b"b" * 32,
    )

    authenticity = signer.sign(snapshot)

    assert not verifier.verify(
        snapshot=snapshot,
        authenticity=authenticity,
    )


def test_voice_audit_hmac_rejects_wrong_key_id() -> None:
    snapshot = _snapshot()

    signer = _authenticator(
        key_id="voice-audit-key-v1",
    )
    verifier = _authenticator(
        key_id="voice-audit-key-v2",
    )

    authenticity = signer.sign(snapshot)

    assert not verifier.verify(
        snapshot=snapshot,
        authenticity=authenticity,
    )


@pytest.mark.parametrize(
    "secret",
    (
        b"",
        b"a",
        b"a" * 31,
    ),
)
def test_voice_audit_hmac_rejects_short_keys(
    secret: bytes,
) -> None:
    with pytest.raises(
        ValueError,
        match="at least 32 bytes",
    ):
        VoiceAuditHmacKey(
            key_id="voice-audit-key-v1",
            secret=secret,
        )


def test_voice_audit_hmac_rejects_blank_key_id() -> None:
    with pytest.raises(
        ValueError,
        match="key_id must be non-empty",
    ):
        VoiceAuditHmacKey(
            key_id="   ",
            secret=b"k" * 32,
        )


def test_voice_audit_keyring_verifies_historical_key() -> None:
    from app.v2.services.voice_audit_authenticator import (
        VoiceAuditHmacKeyring,
    )

    snapshot = _snapshot()

    old_authenticator = VoiceAuditAuthenticator(
        key=VoiceAuditHmacKey(
            key_id="voice-audit-key-v1",
            secret=b"a" * 32,
        )
    )

    authenticity = old_authenticator.sign(snapshot)

    rotated = VoiceAuditAuthenticator(
        keyring=VoiceAuditHmacKeyring(
            active_key_id="voice-audit-key-v2",
            keys=(
                VoiceAuditHmacKey(
                    key_id="voice-audit-key-v1",
                    secret=b"a" * 32,
                ),
                VoiceAuditHmacKey(
                    key_id="voice-audit-key-v2",
                    secret=b"b" * 32,
                ),
            ),
        )
    )

    assert rotated.verify(
        snapshot=snapshot,
        authenticity=authenticity,
    )

    new_authenticity = rotated.sign(snapshot)

    assert new_authenticity.key_id == "voice-audit-key-v2"


def test_voice_audit_keyring_rejects_unknown_historical_key() -> None:
    from app.v2.services.voice_audit_authenticator import (
        VoiceAuditHmacKeyring,
    )

    snapshot = _snapshot()

    old_authenticator = VoiceAuditAuthenticator(
        key=VoiceAuditHmacKey(
            key_id="voice-audit-key-v1",
            secret=b"a" * 32,
        )
    )

    authenticity = old_authenticator.sign(snapshot)

    rotated = VoiceAuditAuthenticator(
        keyring=VoiceAuditHmacKeyring(
            active_key_id="voice-audit-key-v2",
            keys=(
                VoiceAuditHmacKey(
                    key_id="voice-audit-key-v2",
                    secret=b"b" * 32,
                ),
            ),
        )
    )

    assert not rotated.verify(
        snapshot=snapshot,
        authenticity=authenticity,
    )
