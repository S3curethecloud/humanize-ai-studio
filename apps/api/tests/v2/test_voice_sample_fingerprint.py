from datetime import UTC, datetime, timedelta

from app.v2.domain.models import VoiceSourceSample
from app.v2.services.voice_sample_fingerprint import (
    voice_sample_fingerprint,
)


def _sample(
    *,
    sample_id: str,
    text: str,
    label: str | None = None,
    created_at: datetime | None = None,
) -> VoiceSourceSample:
    return VoiceSourceSample(
        sample_id=sample_id,
        text=text,
        label=label,
        created_at=(created_at if created_at is not None else datetime(2026, 8, 10, tzinfo=UTC)),
    )


def test_voice_sample_fingerprint_is_deterministic() -> None:
    samples = (
        _sample(
            sample_id="sample_1",
            text="We document the architecture.",
        ),
        _sample(
            sample_id="sample_2",
            text="We review the evidence.",
        ),
    )

    first = voice_sample_fingerprint(samples)
    second = voice_sample_fingerprint(samples)

    assert first == second
    assert len(first) == 64


def test_voice_sample_fingerprint_changes_when_text_changes() -> None:
    original = (
        _sample(
            sample_id="sample_1",
            text="We document the architecture.",
        ),
    )
    changed = (
        _sample(
            sample_id="sample_1",
            text="We document the security architecture.",
        ),
    )

    assert voice_sample_fingerprint(original) != voice_sample_fingerprint(changed)


def test_voice_sample_fingerprint_changes_when_sample_identity_changes() -> None:
    original = (
        _sample(
            sample_id="sample_1",
            text="We document the architecture.",
        ),
    )
    changed = (
        _sample(
            sample_id="sample_2",
            text="We document the architecture.",
        ),
    )

    assert voice_sample_fingerprint(original) != voice_sample_fingerprint(changed)


def test_voice_sample_fingerprint_changes_when_order_changes() -> None:
    first = _sample(
        sample_id="sample_1",
        text="First sample.",
    )
    second = _sample(
        sample_id="sample_2",
        text="Second sample.",
    )

    assert voice_sample_fingerprint((first, second)) != voice_sample_fingerprint((second, first))


def test_voice_sample_fingerprint_ignores_created_at() -> None:
    first = (
        _sample(
            sample_id="sample_1",
            text="We document the architecture.",
            created_at=datetime(
                2026,
                8,
                10,
                tzinfo=UTC,
            ),
        ),
    )
    second = (
        _sample(
            sample_id="sample_1",
            text="We document the architecture.",
            created_at=(
                datetime(
                    2026,
                    8,
                    10,
                    tzinfo=UTC,
                )
                + timedelta(days=30)
            ),
        ),
    )

    assert voice_sample_fingerprint(first) == voice_sample_fingerprint(second)


def test_voice_sample_fingerprint_ignores_label() -> None:
    first = (
        _sample(
            sample_id="sample_1",
            text="We document the architecture.",
            label="Architecture",
        ),
    )
    second = (
        _sample(
            sample_id="sample_1",
            text="We document the architecture.",
            label="Technical Writing",
        ),
    )

    assert voice_sample_fingerprint(first) == voice_sample_fingerprint(second)


def test_voice_sample_fingerprint_ignores_outer_whitespace() -> None:
    first = (
        _sample(
            sample_id="sample_1",
            text="We document the architecture.",
        ),
    )
    second = (
        _sample(
            sample_id="sample_1",
            text="  We document the architecture.  ",
        ),
    )

    assert voice_sample_fingerprint(first) == voice_sample_fingerprint(second)
