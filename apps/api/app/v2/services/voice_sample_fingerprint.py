from __future__ import annotations

import hashlib
import json

from app.v2.domain.models import VoiceSourceSample


def voice_sample_fingerprint(
    samples: tuple[VoiceSourceSample, ...],
) -> str:
    canonical_samples = [
        {
            "sample_id": sample.sample_id,
            "text": sample.text.strip(),
        }
        for sample in samples
    ]

    payload = json.dumps(
        canonical_samples,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()
