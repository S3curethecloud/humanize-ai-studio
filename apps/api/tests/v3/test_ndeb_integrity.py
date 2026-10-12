from __future__ import annotations

import copy
import sys
from types import SimpleNamespace

import pytest

from app.v3.ndeb.contracts import MAX_CANONICAL_BYTES, NdebIssueCode
from app.v3.ndeb.integrity import (
    NfcKeyCollisionError,
    compute_digest_sha256,
    identity_material,
    normalize_nfc,
    validate_integrity,
)
from tests.v3.test_ndeb_validator import base_bundle


def test_nfc_normalization() -> None:
    assert normalize_nfc("e\u0301") == "é"


def test_nfc_mapping_key_collision() -> None:
    with pytest.raises(NfcKeyCollisionError):
        normalize_nfc({"é": 1, "e\u0301": 2})


def test_identity_material_excludes_exact_two_fields() -> None:
    bundle = base_bundle()
    material = identity_material(bundle)
    assert "bundle_id" not in material
    assert "content_digest_sha256" not in material["integrity"]
    assert material["tenant_id"] == "tenant-a"


def test_digest_is_deterministic() -> None:
    pytest.importorskip("rfc8785")
    bundle = base_bundle()
    assert compute_digest_sha256(bundle) == compute_digest_sha256(copy.deepcopy(bundle))


def test_normative_change_changes_digest() -> None:
    pytest.importorskip("rfc8785")
    bundle = base_bundle()
    changed = copy.deepcopy(bundle)
    changed["tenant_id"] = "tenant-b"
    assert compute_digest_sha256(bundle) != compute_digest_sha256(changed)


def test_unsupported_contract_short_circuits() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    result = validate_integrity(bundle)
    assert result.computed_digest_sha256 is None
    assert {issue.code for issue in result.issues} == {NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED}


def test_digest_and_bundle_id_mismatch() -> None:
    pytest.importorskip("rfc8785")
    bundle = base_bundle()
    result = validate_integrity(bundle)
    assert NdebIssueCode.INTEGRITY_DIGEST_MISMATCH in {issue.code for issue in result.issues}
    assert NdebIssueCode.BUNDLE_ID_MISMATCH in {issue.code for issue in result.issues}



def test_recursive_nfc_normalization() -> None:
    normalized = normalize_nfc({"outer": [{"e\u0301": "e\u0301"}]})
    assert normalized == {"outer": [{"é": "é"}]}


def test_identity_material_retains_all_other_normative_material() -> None:
    bundle = base_bundle()
    material = identity_material(bundle)
    assert set(material) == set(bundle) - {"bundle_id"}
    assert set(material["integrity"]) == set(bundle["integrity"]) - {"content_digest_sha256"}
    assert material["approved_snapshot"] == bundle["approved_snapshot"]
    assert material["classification"] == bundle["classification"]
    assert material["evidence"] == bundle["evidence"]


def test_nfc_equivalent_logical_material_has_same_digest() -> None:
    pytest.importorskip("rfc8785")
    left = base_bundle()
    right = copy.deepcopy(left)
    left["extensions"] = {"com.example/text": {"value": "e\u0301"}}
    right["extensions"] = {"com.example/text": {"value": "é"}}
    assert compute_digest_sha256(left) == compute_digest_sha256(right)


@pytest.mark.parametrize(
    ("field", "value"),
    [("algorithm", "sha-512"), ("canonicalization", "OTHER"), ("identity_material_version", 2)],
)
def test_each_unsupported_integrity_selector_short_circuits_without_rfc8785(
    field: str, value: object
) -> None:
    bundle = base_bundle()
    bundle["integrity"][field] = value  # type: ignore[index]
    result = validate_integrity(bundle)
    assert result.computed_digest_sha256 is None
    assert {issue.code for issue in result.issues} == {NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED}


def test_valid_supplied_digest_and_bundle_id() -> None:
    pytest.importorskip("rfc8785")
    bundle = base_bundle()
    digest = compute_digest_sha256(bundle)
    bundle["integrity"]["content_digest_sha256"] = digest  # type: ignore[index]
    bundle["bundle_id"] = f"ndeb:sha256:{digest}"
    result = validate_integrity(bundle)
    assert result.issues == ()
    assert result.computed_digest_sha256 == digest


def test_digest_mismatch_is_rejected_dimension() -> None:
    pytest.importorskip("rfc8785")
    bundle = base_bundle()
    digest = compute_digest_sha256(bundle)
    bundle["bundle_id"] = f"ndeb:sha256:{digest}"
    result = validate_integrity(bundle)
    assert {issue.code for issue in result.issues} == {NdebIssueCode.INTEGRITY_DIGEST_MISMATCH}


def test_bundle_id_mismatch_is_rejected_dimension() -> None:
    pytest.importorskip("rfc8785")
    bundle = base_bundle()
    digest = compute_digest_sha256(bundle)
    bundle["integrity"]["content_digest_sha256"] = digest  # type: ignore[index]
    bundle["bundle_id"] = "ndeb:sha256:" + "f" * 64
    result = validate_integrity(bundle)
    assert {issue.code for issue in result.issues} == {NdebIssueCode.BUNDLE_ID_MISMATCH}


def test_canonical_byte_limit_maps_to_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(dumps=lambda value: b"x" * (MAX_CANONICAL_BYTES + 1))
    monkeypatch.setitem(sys.modules, "rfc8785", fake)
    result = validate_integrity(base_bundle())
    assert {issue.code for issue in result.issues} == {NdebIssueCode.CANONICAL_SIZE_EXCEEDED}


def test_canonicalization_failure_maps_to_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(value: object) -> bytes:
        raise ValueError("synthetic canonicalization failure")

    monkeypatch.setitem(sys.modules, "rfc8785", SimpleNamespace(dumps=fail))
    result = validate_integrity(base_bundle())
    assert {issue.code for issue in result.issues} == {NdebIssueCode.CANONICALIZATION_FAILED}


def test_large_integer_canonicalizer_rejection_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    huge = 1 << 200

    def fail_on_large(value: object) -> bytes:
        assert str(huge) in repr(value)
        raise ValueError("integer outside canonicalizer domain")

    monkeypatch.setitem(sys.modules, "rfc8785", SimpleNamespace(dumps=fail_on_large))
    bundle = base_bundle()
    bundle["extensions"] = {"com.example/large": {"value": huge}}
    result = validate_integrity(bundle)
    assert {issue.code for issue in result.issues} == {NdebIssueCode.CANONICALIZATION_FAILED}
