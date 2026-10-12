from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import get_args, get_origin, get_type_hints

import pytest

from app.v3.ndeb import NdebAuthorizedContext, NdebDisposition, NdebIssueCode, validate_ndeb_bundle
from app.v3.ndeb.contracts import JsonValue, NdebValidationResult


def source_ref(name: str) -> dict[str, object]:
    return {"object_type": "record", "object_id": name, "object_version": 1}


def classification() -> dict[str, object]:
    return {"value": "internal", "authority_ref": source_ref("classification-policy")}


def base_bundle() -> dict[str, object]:
    zero = "0" * 64
    return {
        "schema_id": "urn:nexus:ndeb",
        "schema_version": "1.0.0",
        "bundle_id": f"ndeb:sha256:{zero}",
        "tenant_id": "tenant-a",
        "engagement_id": "engagement-a",
        "approved_snapshot": {
            "snapshot_id": "snapshot-1",
            "source_state_revision": {
                "authority": "nexus",
                "revision_type": "commit",
                "revision_id": "rev-1",
            },
            "captured_at": "2026-01-01T00:00:00Z",
            "approved_at": "2026-01-01T00:00:01Z",
            "approval_refs": ["approval-1"],
        },
        "classification": classification(),
        "evidence_manifest": [],
        "evidence": {
            "architecture_decisions": [],
            "agent_catalog": [],
            "tool_catalog": [],
            "model_inventory": [],
            "security_controls": [],
            "evaluations": [],
            "deployment_evidence": [],
            "operational_artifacts": [],
            "risks": [],
        },
        "artifacts": [],
        "provenance": [],
        "approvals": [
            {
                "approval_id": "approval-1",
                "approval_type": "architecture",
                "state": "approved",
                "source_ref": source_ref("approval-source"),
                "approved_at": "2026-01-01T00:00:01Z",
            }
        ],
        "required_extensions": [],
        "extensions": {},
        "integrity": {
            "algorithm": "sha-256",
            "canonicalization": "RFC8785+NFC",
            "identity_material_version": 1,
            "content_digest_sha256": zero,
        },
    }


def valid_bundle() -> dict[str, object]:
    pytest.importorskip("rfc8785")
    from app.v3.ndeb.integrity import compute_digest_sha256

    bundle = base_bundle()
    digest = compute_digest_sha256(bundle)
    bundle["integrity"]["content_digest_sha256"] = digest  # type: ignore[index]
    bundle["bundle_id"] = f"ndeb:sha256:{digest}"
    return bundle


def encoded(bundle: dict[str, object]) -> bytes:
    return json.dumps(bundle, separators=(",", ":"), ensure_ascii=False).encode()


def context() -> NdebAuthorizedContext:
    return NdebAuthorizedContext("tenant-a", "engagement-a")


def codes(result: object) -> set[NdebIssueCode]:
    return {issue.code for issue in result.issues}  # type: ignore[attr-defined]


def test_fully_valid_bundle_is_validated() -> None:
    result = validate_ndeb_bundle(candidate_bytes=encoded(valid_bundle()), context=context())
    assert result.disposition is NdebDisposition.VALIDATED
    assert result.issues == ()
    assert isinstance(result.validated_bundle, MappingProxyType)
    assert result.computed_digest_sha256 is not None


@pytest.mark.parametrize("version", ["2.0.0", "0.9.0"])
def test_unsupported_schema_version_is_terminal_rejected(version: str) -> None:
    bundle = base_bundle()
    bundle["schema_version"] = version
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert codes(result) == {NdebIssueCode.SCHEMA_VERSION_UNSUPPORTED}


def test_unsupported_schema_identity_is_terminal_rejected() -> None:
    bundle = base_bundle()
    bundle["schema_id"] = "urn:nexus:ndeb:future"
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert codes(result) == {NdebIssueCode.SCHEMA_IDENTITY_UNSUPPORTED}


@pytest.mark.parametrize(
    ("field", "value", "pointer"),
    [
        ("algorithm", "sha-512", "/integrity/algorithm"),
        ("canonicalization", "OTHER", "/integrity/canonicalization"),
        ("identity_material_version", 2, "/integrity/identity_material_version"),
    ],
)
def test_unsupported_integrity_selector_is_rejected(
    field: str, value: object, pointer: str
) -> None:
    bundle = base_bundle()
    bundle["integrity"][field] = value  # type: ignore[index]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert result.issues == (
        result.issues[0].__class__(NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED, pointer),
    )


def test_all_unsupported_integrity_selectors_are_three_rejections() -> None:
    bundle = base_bundle()
    integrity = bundle["integrity"]  # type: ignore[assignment]
    integrity["algorithm"] = "sha-512"
    integrity["canonicalization"] = "OTHER"
    integrity["identity_material_version"] = 2
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert codes(result) == {NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED}
    assert {issue.json_pointer for issue in result.issues} == {
        "/integrity/algorithm",
        "/integrity/canonicalization",
        "/integrity/identity_material_version",
    }


def test_wrong_type_integrity_selector_is_error() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = 123  # type: ignore[index]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.INTEGRITY_METADATA_INVALID in codes(result)
    assert NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED not in codes(result)


def test_unsupported_selector_plus_malformed_digest_is_error() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    bundle["integrity"]["content_digest_sha256"] = "bad"  # type: ignore[index]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.INTEGRITY_METADATA_INVALID in codes(result)


def test_unsupported_selector_plus_unknown_integrity_member_is_error() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    bundle["integrity"]["extra"] = "x"  # type: ignore[index]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.INTEGRITY_METADATA_INVALID in codes(result)


def test_unrelated_structural_error_dominates_unsupported_integrity() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    del bundle["tenant_id"]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED in codes(result)
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID in codes(result)


def test_tenant_mismatch_is_rejected() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext("tenant-b", "engagement-a"),
    )
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.TENANT_SCOPE_MISMATCH in codes(result)


def test_engagement_context_unavailable_is_error() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext("tenant-a", None),
    )
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.ENGAGEMENT_CONTEXT_UNAVAILABLE in codes(result)


def test_classification_context_mismatch_is_rejected() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    different = MappingProxyType(
        {
            "value": "confidential",
            "authority_ref": MappingProxyType(source_ref("classification-policy")),
        }
    )
    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext("tenant-a", "engagement-a", different),
    )
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.CLASSIFICATION_CONTEXT_MISMATCH in codes(result)


def test_issue_ordering_is_deterministic() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    bundle["integrity"]["canonicalization"] = "OTHER"  # type: ignore[index]
    first = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    second = validate_ndeb_bundle(candidate_bytes=encoded(copy.deepcopy(bundle)), context=context())
    assert first == second


def test_missing_root_integrity_is_error_without_generic_schema_issue() -> None:
    bundle = base_bundle()
    del bundle["integrity"]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert result.issues == (
        result.issues[0].__class__(NdebIssueCode.INTEGRITY_METADATA_INVALID, "/integrity"),
    )


def test_missing_root_integrity_and_classification_preserve_error_partitions() -> None:
    bundle = base_bundle()
    del bundle["integrity"]
    del bundle["classification"]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert {issue.code for issue in result.issues} == {
        NdebIssueCode.INTEGRITY_METADATA_INVALID,
        NdebIssueCode.CLASSIFICATION_INVALID,
    }


def test_manifest_dangling_provenance_ref_is_error_and_dominates_mismatch() -> None:
    bundle = base_bundle()
    item = {
        "evidence_id": "e-1",
        "record_type": "risk",
        "record_id": "r-1",
        "record_version": 1,
        "source_ref": source_ref("risk-source"),
        "classification": classification(),
        "provenance_refs": ["p-1"],
        "artifact_refs": [],
        "material": {"title": "t", "risk_statement": "r", "severity": "high", "status": "open"},
    }
    bundle["evidence"]["risks"] = [item]  # type: ignore[index]
    bundle["provenance"] = [
        {
            "provenance_id": "p-1",
            "subject_ref": {"subject_type": "evidence", "subject_id": "e-1"},
            "source_refs": [source_ref("src")],
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    ]
    bundle["evidence_manifest"] = [
        {
            "evidence_id": "e-1",
            "evidence_family": "risks",
            "record_ref": item["source_ref"],
            "classification": item["classification"],
            "provenance_refs": ["missing"],
            "artifact_refs": [],
        }
    ]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.REFERENTIAL_CLOSURE_INVALID in codes(result)
    assert NdebIssueCode.MANIFEST_EVIDENCE_MISMATCH in codes(result)
    assert any(
        issue.code is NdebIssueCode.REFERENTIAL_CLOSURE_INVALID
        and issue.json_pointer == "/evidence_manifest/0/provenance_refs/0"
        for issue in result.issues
    )




def _short_circuit_integrity(bundle: dict[str, object]) -> None:
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]


def test_malformed_parse_is_error() -> None:
    result = validate_ndeb_bundle(candidate_bytes=b'{', context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert codes(result) == {NdebIssueCode.JSON_MALFORMED}


def test_generic_structural_invalid_is_error() -> None:
    bundle = base_bundle()
    del bundle["tenant_id"]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID in codes(result)


def test_required_extension_unsupported_is_error() -> None:
    bundle = base_bundle()
    bundle["required_extensions"] = ["com.example/future"]
    bundle["extensions"] = {"com.example/future": {}}
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.REQUIRED_EXTENSION_UNSUPPORTED in codes(result)


def test_referential_closure_unavailable_is_error() -> None:
    bundle = base_bundle()
    bundle["approved_snapshot"]["approval_refs"] = ["missing"]  # type: ignore[index]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.REFERENTIAL_CLOSURE_INVALID in codes(result)


def test_semantic_ordering_violation_is_rejected() -> None:
    bundle = base_bundle()
    _short_circuit_integrity(bundle)
    bundle["required_extensions"] = ["com.z/x", "com.a/x"]
    bundle["extensions"] = {"com.z/x": {}, "com.a/x": {}}
    # Required extensions are ERROR-class, so use approval_refs ordering instead.
    bundle["required_extensions"] = []
    bundle["extensions"] = {}
    bundle["approved_snapshot"]["approval_refs"] = ["approval-2", "approval-1"]  # type: ignore[index]
    bundle["approvals"] = [
        {
            "approval_id": "approval-1",
            "approval_type": "architecture",
            "state": "approved",
            "source_ref": source_ref("approval-source-1"),
        },
        {
            "approval_id": "approval-2",
            "approval_type": "architecture",
            "state": "approved",
            "source_ref": source_ref("approval-source-2"),
        },
    ]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.SEMANTIC_ORDERING_VIOLATION in codes(result)


def test_manifest_equality_mismatch_is_rejected() -> None:
    bundle = base_bundle()
    _short_circuit_integrity(bundle)
    item = {
        "evidence_id": "e-1",
        "record_type": "risk",
        "record_id": "r-1",
        "record_version": 1,
        "source_ref": source_ref("risk-source"),
        "classification": classification(),
        "provenance_refs": ["p-1"],
        "artifact_refs": [],
        "material": {"title": "t", "risk_statement": "r", "severity": "high", "status": "open"},
    }
    bundle["evidence"]["risks"] = [item]  # type: ignore[index]
    bundle["provenance"] = [
        {
            "provenance_id": "p-1",
            "subject_ref": {"subject_type": "evidence", "subject_id": "e-1"},
            "source_refs": [source_ref("src")],
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    ]
    bundle["evidence_manifest"] = [
        {
            "evidence_id": "e-1",
            "evidence_family": "risks",
            "record_ref": source_ref("different"),
            "classification": item["classification"],
            "provenance_refs": ["p-1"],
            "artifact_refs": [],
        }
    ]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.MANIFEST_EVIDENCE_MISMATCH in codes(result)


def test_integrity_digest_mismatch_is_rejected() -> None:
    pytest.importorskip("rfc8785")
    from app.v3.ndeb.integrity import compute_digest_sha256

    bundle = base_bundle()
    digest = compute_digest_sha256(bundle)
    bundle["bundle_id"] = f"ndeb:sha256:{digest}"
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert codes(result) == {NdebIssueCode.INTEGRITY_DIGEST_MISMATCH}


def test_bundle_id_mismatch_is_rejected() -> None:
    pytest.importorskip("rfc8785")
    from app.v3.ndeb.integrity import compute_digest_sha256

    bundle = base_bundle()
    digest = compute_digest_sha256(bundle)
    bundle["integrity"]["content_digest_sha256"] = digest  # type: ignore[index]
    bundle["bundle_id"] = "ndeb:sha256:" + "f" * 64
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert codes(result) == {NdebIssueCode.BUNDLE_ID_MISMATCH}


def test_tenant_context_unavailable_is_error() -> None:
    bundle = base_bundle()
    _short_circuit_integrity(bundle)
    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext(None, "engagement-a"),
    )
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.TENANT_CONTEXT_UNAVAILABLE in codes(result)


def test_engagement_mismatch_is_rejected() -> None:
    bundle = base_bundle()
    _short_circuit_integrity(bundle)
    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext("tenant-a", "engagement-b"),
    )
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.ENGAGEMENT_SCOPE_MISMATCH in codes(result)


def test_classification_context_omitted_preserves_source_and_continues() -> None:
    bundle = base_bundle()
    _short_circuit_integrity(bundle)
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.CLASSIFICATION_CONTEXT_MISMATCH not in codes(result)


def test_classification_context_exact_match_continues() -> None:
    bundle = base_bundle()
    _short_circuit_integrity(bundle)
    exact = MappingProxyType(
        {
            "value": "internal",
            "authority_ref": MappingProxyType(source_ref("classification-policy")),
        }
    )
    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext("tenant-a", "engagement-a", exact),
    )
    assert result.disposition is NdebDisposition.REJECTED
    assert NdebIssueCode.CLASSIFICATION_CONTEXT_MISMATCH not in codes(result)


def test_repeat_invocation_produces_identical_result() -> None:
    bundle = base_bundle()
    _short_circuit_integrity(bundle)
    first = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    second = validate_ndeb_bundle(candidate_bytes=encoded(copy.deepcopy(bundle)), context=context())
    assert first == second


def test_diagnostics_do_not_include_raw_offending_value() -> None:
    secret = "raw-secret-value-never-emit"
    bundle = base_bundle()
    bundle["schema_id"] = secret
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    diagnostic_surface = " ".join(
        f"{issue.code.value} {issue.json_pointer}" for issue in result.issues
    )
    assert secret not in diagnostic_surface



def _contains_mapping_origin(annotation: object) -> bool:
    origin = get_origin(annotation)
    if origin is Mapping:
        return True
    return any(_contains_mapping_origin(arg) for arg in get_args(annotation))


def test_public_contract_uses_mapping_abstraction() -> None:
    assert _contains_mapping_origin(JsonValue)
    context_hint = get_type_hints(NdebAuthorizedContext)["classification"]
    result_hint = get_type_hints(NdebValidationResult)["validated_bundle"]
    assert _contains_mapping_origin(context_hint)
    assert _contains_mapping_origin(result_hint)


def test_ordinary_mapping_classification_context_is_accepted() -> None:
    bundle = base_bundle()
    _short_circuit_integrity(bundle)
    result = validate_ndeb_bundle(
        candidate_bytes=encoded(bundle),
        context=NdebAuthorizedContext(
            "tenant-a",
            "engagement-a",
            classification(),
        ),
    )
    assert NdebIssueCode.VALIDATOR_INTERNAL_ERROR not in codes(result)
    assert NdebIssueCode.CLASSIFICATION_CONTEXT_MISMATCH not in codes(result)


def test_missing_root_classification_is_classification_invalid_not_generic() -> None:
    bundle = base_bundle()
    del bundle["classification"]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.CLASSIFICATION_INVALID in codes(result)
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID not in codes(result)
    assert any(
        issue.code is NdebIssueCode.CLASSIFICATION_INVALID
        and issue.json_pointer == "/classification"
        for issue in result.issues
    )


def test_malformed_classification_is_classification_invalid_not_generic() -> None:
    bundle = base_bundle()
    bundle["classification"] = "internal"
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert codes(result) == {NdebIssueCode.CLASSIFICATION_INVALID}


def test_malformed_provenance_entry_is_provenance_invalid_not_generic() -> None:
    bundle = base_bundle()
    bundle["provenance"] = [{"provenance_id": "p-1"}]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.PROVENANCE_INVALID in codes(result)
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID not in codes(result)


def test_dangling_provenance_reference_remains_referential_closure_invalid() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    item = {
        "evidence_id": "e-1",
        "record_type": "risk",
        "record_id": "r-1",
        "record_version": 1,
        "source_ref": source_ref("risk-source"),
        "classification": classification(),
        "provenance_refs": ["missing"],
        "artifact_refs": [],
        "material": {"title": "t", "risk_statement": "r", "severity": "high", "status": "open"},
    }
    bundle["evidence"]["risks"] = [item]  # type: ignore[index]
    bundle["evidence_manifest"] = [
        {
            "evidence_id": "e-1",
            "evidence_family": "risks",
            "record_ref": item["source_ref"],
            "classification": item["classification"],
            "provenance_refs": ["missing"],
            "artifact_refs": [],
        }
    ]
    result = validate_ndeb_bundle(candidate_bytes=encoded(bundle), context=context())
    assert result.disposition is NdebDisposition.ERROR
    assert NdebIssueCode.REFERENTIAL_CLOSURE_INVALID in codes(result)
    assert NdebIssueCode.PROVENANCE_INVALID not in codes(result)
