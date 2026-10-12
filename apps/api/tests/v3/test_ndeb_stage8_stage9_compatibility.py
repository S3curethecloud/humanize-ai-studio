from __future__ import annotations

import copy

import pytest

from app.v3.ndeb import NdebDisposition, NdebIssueCode, validate_ndeb_bundle
from tests.v3.test_ndeb_validator import (
    base_bundle,
    context,
    encoded,
    source_ref,
    valid_bundle,
)


def test_supported_canonical_case() -> None:
    result = validate_ndeb_bundle(candidate_bytes=encoded(valid_bundle()), context=context())
    assert result.disposition is NdebDisposition.VALIDATED


@pytest.mark.parametrize("version", ["2.0.0", "0.9.0"])
def test_future_and_historical_versions_are_rejected(version: str) -> None:
    bundle = base_bundle()
    bundle["schema_version"] = version
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert {issue.code for issue in result.issues} == {NdebIssueCode.SCHEMA_VERSION_UNSUPPORTED}


def test_unknown_optional_extension_may_validate() -> None:
    bundle = valid_bundle()
    bundle["extensions"] = {"com.example/future": {"opaque": "value"}}
    from app.v3.ndeb.integrity import compute_digest_sha256
    digest = compute_digest_sha256(bundle)
    bundle["integrity"]["content_digest_sha256"] = digest  # type: ignore[index]
    bundle["bundle_id"] = f"ndeb:sha256:{digest}"
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.VALIDATED


def test_required_unknown_extension_is_error() -> None:
    bundle = base_bundle()
    bundle["required_extensions"] = ["com.example/future"]
    bundle["extensions"] = {"com.example/future": {}}
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.REQUIRED_EXTENSION_UNSUPPORTED in {issue.code for issue in result.issues}


def test_identity_mismatch_is_rejected() -> None:
    bundle = valid_bundle()
    bundle["bundle_id"] = "ndeb:sha256:" + "f" * 64
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.BUNDLE_ID_MISMATCH in {issue.code for issue in result.issues}


def test_malformed_input_is_error() -> None:
    result = validate_ndeb_bundle(candidate_bytes=b"{", context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert {issue.code for issue in result.issues} == {NdebIssueCode.JSON_MALFORMED}


def test_error_precedence_over_rejected() -> None:
    bundle = copy.deepcopy(base_bundle())
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    del bundle["classification"]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR



def test_supported_governed_exact_version_case() -> None:
    bundle = valid_bundle()
    assert bundle["schema_version"] == "1.0.0"
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.VALIDATED


def test_incompatible_semantic_change_is_rejected() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    bundle["approved_snapshot"]["captured_at"] = "2026-01-01T00:00:00.0000001Z"  # type: ignore[index]
    bundle["approved_snapshot"]["approved_at"] = "2026-01-01T00:00:00.0000000Z"  # type: ignore[index]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.TEMPORAL_ORDER_VIOLATION in {issue.code for issue in result.issues}


def test_tenant_scope_mismatch_case() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    from app.v3.ndeb import NdebAuthorizedContext

    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext("tenant-b", "engagement-a"),
    )
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.TENANT_SCOPE_MISMATCH in {issue.code for issue in result.issues}


def test_engagement_scope_mismatch_case() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    from app.v3.ndeb import NdebAuthorizedContext

    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext("tenant-a", "engagement-b"),
    )
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.ENGAGEMENT_SCOPE_MISMATCH in {issue.code for issue in result.issues}


def test_policy_provenance_invalidity_case() -> None:
    bundle = base_bundle()
    bundle["provenance"] = [
        {
            "provenance_id": "p-1",
            "subject_ref": {"subject_type": "evidence", "subject_id": "missing"},
            "source_refs": [source_ref("source")],
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    ]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.PROVENANCE_INVALID in {issue.code for issue in result.issues}


def test_security_boundary_duplicate_member_is_error() -> None:
    raw = b'{"schema_id":"urn:nexus:ndeb","schema_id":"urn:nexus:ndeb"}'
    result = validate_ndeb_bundle(candidate_bytes=raw, context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert {issue.code for issue in result.issues} == {NdebIssueCode.JSON_DUPLICATE_MEMBER}


def test_stage9_error_precedence_with_semantic_rejection() -> None:
    bundle = copy.deepcopy(base_bundle())
    bundle["approved_snapshot"]["captured_at"] = "2026-01-01T00:00:02Z"  # type: ignore[index]
    bundle["approved_snapshot"]["approval_refs"] = ["missing"]  # type: ignore[index]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert NdebIssueCode.TEMPORAL_ORDER_VIOLATION in {issue.code for issue in result.issues}
    assert NdebIssueCode.REFERENTIAL_CLOSURE_INVALID in {issue.code for issue in result.issues}
    assert result.disposition is NdebDisposition.ERROR



def test_structurally_invalid_classification_maps_to_classification_invalid() -> None:
    bundle = base_bundle()
    bundle["classification"] = "invalid"
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.CLASSIFICATION_INVALID in {issue.code for issue in result.issues}
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID not in {issue.code for issue in result.issues}


def test_structurally_invalid_provenance_maps_to_provenance_invalid() -> None:
    bundle = base_bundle()
    bundle["provenance"] = [{"provenance_id": "p-1"}]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.PROVENANCE_INVALID in {issue.code for issue in result.issues}
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID not in {issue.code for issue in result.issues}
