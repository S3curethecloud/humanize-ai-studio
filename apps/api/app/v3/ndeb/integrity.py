"""NFC + RFC8785 identity material and digest verification."""

from __future__ import annotations

import copy
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .contracts import (
    MAX_CANONICAL_BYTES,
    SUPPORTED_CANONICALIZATION,
    SUPPORTED_IDENTITY_MATERIAL_VERSION,
    SUPPORTED_INTEGRITY_ALGORITHM,
    NdebIssueCode,
    NdebValidationIssue,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class NfcKeyCollisionError(ValueError):
    pass


@dataclass(frozen=True)
class IntegrityValidationResult:
    issues: tuple[NdebValidationIssue, ...]
    computed_digest_sha256: str | None


def normalize_nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [normalize_nfc(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise NfcKeyCollisionError(normalized_key)
            normalized[normalized_key] = normalize_nfc(child)
        return normalized
    return value


def identity_material(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_nfc(copy.deepcopy(candidate))
    if not isinstance(normalized, dict):
        raise TypeError("normalized candidate must be object")
    normalized.pop("bundle_id", None)
    integrity = normalized.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("content_digest_sha256", None)
    return normalized


def canonical_bytes(candidate: dict[str, Any]) -> bytes:
    try:
        import rfc8785
    except ImportError as exc:
        raise RuntimeError("required rfc8785 dependency unavailable") from exc
    data = rfc8785.dumps(identity_material(candidate))
    if len(data) > MAX_CANONICAL_BYTES:
        raise OverflowError("canonical bytes exceed bound")
    return data


def compute_digest_sha256(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(candidate)).hexdigest()


def validate_integrity(candidate: dict[str, Any]) -> IntegrityValidationResult:
    integrity = candidate.get("integrity")
    if not isinstance(integrity, dict):
        return IntegrityValidationResult(
            (NdebValidationIssue(NdebIssueCode.INTEGRITY_METADATA_INVALID, "/integrity"),),
            None,
        )
    required = {
        "algorithm",
        "canonicalization",
        "identity_material_version",
        "content_digest_sha256",
    }
    if set(integrity) != required:
        return IntegrityValidationResult(
            (NdebValidationIssue(NdebIssueCode.INTEGRITY_METADATA_INVALID, "/integrity"),),
            None,
        )
    algorithm = integrity.get("algorithm")
    canonicalization = integrity.get("canonicalization")
    material_version = integrity.get("identity_material_version")
    digest = integrity.get("content_digest_sha256")
    if not isinstance(algorithm, str) or not isinstance(canonicalization, str):
        return IntegrityValidationResult(
            (NdebValidationIssue(NdebIssueCode.INTEGRITY_METADATA_INVALID, "/integrity"),),
            None,
        )
    if not isinstance(material_version, int) or isinstance(material_version, bool):
        return IntegrityValidationResult(
            (NdebValidationIssue(NdebIssueCode.INTEGRITY_METADATA_INVALID, "/integrity"),),
            None,
        )
    if not isinstance(digest, str) or _SHA256_RE.fullmatch(digest) is None:
        return IntegrityValidationResult(
            (
                NdebValidationIssue(
                    NdebIssueCode.INTEGRITY_METADATA_INVALID, "/integrity/content_digest_sha256"
                ),
            ),
            None,
        )
    unsupported: list[NdebValidationIssue] = []
    if algorithm != SUPPORTED_INTEGRITY_ALGORITHM:
        unsupported.append(
            NdebValidationIssue(
                NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED, "/integrity/algorithm"
            )
        )
    if canonicalization != SUPPORTED_CANONICALIZATION:
        unsupported.append(
            NdebValidationIssue(
                NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED, "/integrity/canonicalization"
            )
        )
    if material_version != SUPPORTED_IDENTITY_MATERIAL_VERSION:
        unsupported.append(
            NdebValidationIssue(
                NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED, "/integrity/identity_material_version"
            )
        )
    if unsupported:
        return IntegrityValidationResult(tuple(sorted(unsupported)), None)
    try:
        computed = compute_digest_sha256(candidate)
    except NfcKeyCollisionError:
        return IntegrityValidationResult(
            (NdebValidationIssue(NdebIssueCode.NFC_KEY_COLLISION, ""),),
            None,
        )
    except OverflowError:
        return IntegrityValidationResult(
            (NdebValidationIssue(NdebIssueCode.CANONICAL_SIZE_EXCEEDED, ""),),
            None,
        )
    except (RuntimeError, TypeError, ValueError):
        return IntegrityValidationResult(
            (NdebValidationIssue(NdebIssueCode.CANONICALIZATION_FAILED, ""),),
            None,
        )
    issues: list[NdebValidationIssue] = []
    if digest != computed:
        issues.append(
            NdebValidationIssue(
                NdebIssueCode.INTEGRITY_DIGEST_MISMATCH, "/integrity/content_digest_sha256"
            )
        )
    expected_bundle_id = f"ndeb:sha256:{computed}"
    if candidate.get("bundle_id") != expected_bundle_id:
        issues.append(NdebValidationIssue(NdebIssueCode.BUNDLE_ID_MISMATCH, "/bundle_id"))
    return IntegrityValidationResult(tuple(sorted(issues)), computed)
