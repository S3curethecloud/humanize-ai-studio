from __future__ import annotations

import copy

import pytest

from app.v3.ndeb.contracts import NdebIssueCode, NdebValidationIssue
from app.v3.ndeb.semantic_validation import validate_semantics
from tests.v3.test_ndeb_validator import base_bundle, classification, source_ref


def codes(bundle: dict[str, object]) -> set[NdebIssueCode]:
    return {issue.code for issue in validate_semantics(bundle)}


def test_empty_evidence_bundle_has_semantic_closure() -> None:
    assert not validate_semantics(base_bundle())


def test_snapshot_temporal_order_violation() -> None:
    bundle = base_bundle()
    bundle["approved_snapshot"]["captured_at"] = "2026-01-01T00:00:02Z"  # type: ignore[index]
    assert NdebIssueCode.TEMPORAL_ORDER_VIOLATION in codes(bundle)


def test_invalid_calendar_timestamp() -> None:
    bundle = base_bundle()
    bundle["approved_snapshot"]["captured_at"] = "2026-13-99T00:00:00Z"  # type: ignore[index]
    assert NdebIssueCode.TIMESTAMP_INVALID in codes(bundle)


def test_nonempty_required_extensions_fails_closed() -> None:
    bundle = base_bundle()
    bundle["required_extensions"] = ["com.example/foo"]
    bundle["extensions"] = {"com.example/foo": {}}
    assert NdebIssueCode.REQUIRED_EXTENSION_UNSUPPORTED in codes(bundle)


def test_dangling_approval_ref_fails_closure() -> None:
    bundle = base_bundle()
    bundle["approved_snapshot"]["approval_refs"] = ["missing"]  # type: ignore[index]
    assert NdebIssueCode.REFERENTIAL_CLOSURE_INVALID in codes(bundle)


def test_manifest_equality_mismatch_is_rejected_dimension() -> None:
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
            "record_ref": source_ref("different"),
            "classification": classification(),
            "provenance_refs": ["p-1"],
            "artifact_refs": [],
        }
    ]
    assert NdebIssueCode.MANIFEST_EVIDENCE_MISMATCH in codes(bundle)


def test_normative_null_is_error_dimension() -> None:
    bundle = copy.deepcopy(base_bundle())
    bundle["extensions"] = {"com.example/foo": {"x": None}}
    assert NdebIssueCode.NORMATIVE_NULL_PROHIBITED in codes(bundle)


def _risk(evidence_id: str, provenance_id: str = "p-1") -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "record_type": "risk",
        "record_id": f"record-{evidence_id}",
        "record_version": 1,
        "source_ref": source_ref(f"source-{evidence_id}"),
        "classification": classification(),
        "provenance_refs": [provenance_id],
        "artifact_refs": [],
        "material": {
            "title": "Risk",
            "risk_statement": "Statement",
            "severity": "high",
            "status": "open",
        },
    }


def _provenance(provenance_id: str, evidence_id: str) -> dict[str, object]:
    return {
        "provenance_id": provenance_id,
        "subject_ref": {"subject_type": "evidence", "subject_id": evidence_id},
        "source_refs": [source_ref("source")],
        "recorded_at": "2026-01-01T00:00:00Z",
    }


def test_evidence_ordering_violation() -> None:
    bundle = base_bundle()
    bundle["evidence"]["risks"] = [_risk("e-2", "p-2"), _risk("e-1", "p-1")]  # type: ignore[index]
    bundle["provenance"] = [_provenance("p-1", "e-1"), _provenance("p-2", "e-2")]
    assert NdebIssueCode.SEMANTIC_ORDERING_VIOLATION in codes(bundle)


def test_global_evidence_identity_duplicate_across_families() -> None:
    bundle = base_bundle()
    risk = _risk("e-1", "p-1")
    architecture = {
        **risk,
        "record_type": "architecture_decision",
        "material": {
            "title": "Decision",
            "decision": "Do it",
            "rationale": "Reason",
            "status": "accepted",
        },
    }
    bundle["evidence"]["risks"] = [risk]  # type: ignore[index]
    bundle["evidence"]["architecture_decisions"] = [architecture]  # type: ignore[index]
    bundle["provenance"] = [_provenance("p-1", "e-1")]
    observed = codes(bundle)
    assert NdebIssueCode.SEMANTIC_DUPLICATE_IDENTITY in observed
    assert NdebIssueCode.REFERENTIAL_CLOSURE_INVALID in observed


def test_provenance_subject_ref_must_resolve() -> None:
    bundle = base_bundle()
    bundle["provenance"] = [_provenance("p-1", "missing")]
    assert NdebIssueCode.PROVENANCE_INVALID in codes(bundle)


def test_required_extension_key_must_resolve() -> None:
    bundle = base_bundle()
    bundle["required_extensions"] = ["com.example/foo"]
    observed = codes(bundle)
    assert NdebIssueCode.REFERENTIAL_CLOSURE_INVALID in observed
    assert NdebIssueCode.REQUIRED_EXTENSION_UNSUPPORTED in observed


def _artifact(artifact_id: str) -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "artifact_type": "report",
        "media_type": "application/json",
        "sha256": "1" * 64,
        "size_bytes": 1,
    }


def _risk_with_refs(
    evidence_id: str,
    *,
    provenance_refs: list[str],
    artifact_refs: list[str],
) -> dict[str, object]:
    item = _risk(evidence_id, provenance_refs[0] if provenance_refs else "p-1")
    item["provenance_refs"] = provenance_refs
    item["artifact_refs"] = artifact_refs
    return item


def _manifest_for(
    item: dict[str, object], *, provenance_refs: list[str], artifact_refs: list[str]
) -> dict[str, object]:
    return {
        "evidence_id": item["evidence_id"],
        "evidence_family": "risks",
        "record_ref": item["source_ref"],
        "classification": item["classification"],
        "provenance_refs": provenance_refs,
        "artifact_refs": artifact_refs,
    }


def test_manifest_dangling_provenance_ref_has_exact_closure_pointer() -> None:
    bundle = base_bundle()
    item = _risk_with_refs("e-1", provenance_refs=["p-1"], artifact_refs=[])
    bundle["evidence"]["risks"] = [item]  # type: ignore[index]
    bundle["provenance"] = [_provenance("p-1", "e-1")]
    bundle["evidence_manifest"] = [
        _manifest_for(item, provenance_refs=["missing"], artifact_refs=[])
    ]
    observed = validate_semantics(bundle)
    assert NdebValidationIssue(
        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
        "/evidence_manifest/0/provenance_refs/0",
    ) in observed
    assert NdebIssueCode.MANIFEST_EVIDENCE_MISMATCH in {issue.code for issue in observed}


def test_manifest_dangling_artifact_ref_has_exact_closure_pointer() -> None:
    bundle = base_bundle()
    item = _risk_with_refs("e-1", provenance_refs=["p-1"], artifact_refs=[])
    bundle["evidence"]["risks"] = [item]  # type: ignore[index]
    bundle["provenance"] = [_provenance("p-1", "e-1")]
    bundle["evidence_manifest"] = [
        _manifest_for(item, provenance_refs=["p-1"], artifact_refs=["missing-artifact"])
    ]
    observed = validate_semantics(bundle)
    assert NdebValidationIssue(
        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
        "/evidence_manifest/0/artifact_refs/0",
    ) in observed
    assert NdebIssueCode.MANIFEST_EVIDENCE_MISMATCH in {issue.code for issue in observed}


def test_evidence_dangling_refs_use_array_index_pointers() -> None:
    bundle = base_bundle()
    item = _risk_with_refs(
        "e-1",
        provenance_refs=["missing-provenance"],
        artifact_refs=["missing-artifact"],
    )
    bundle["evidence"]["risks"] = [item]  # type: ignore[index]
    observed = validate_semantics(bundle)
    assert NdebValidationIssue(
        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
        "/evidence/risks/0/provenance_refs/0",
    ) in observed
    assert NdebValidationIssue(
        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
        "/evidence/risks/0/artifact_refs/0",
    ) in observed


def test_primary_artifact_membership_uses_nfc_equivalence() -> None:
    bundle = base_bundle()
    composed = "é"
    decomposed = "e\u0301"
    item = {
        "evidence_id": "e-1",
        "record_type": "operational_artifact",
        "record_id": "record-e-1",
        "record_version": 1,
        "source_ref": source_ref("source-e-1"),
        "classification": classification(),
        "provenance_refs": ["p-1"],
        "artifact_refs": [decomposed],
        "material": {
            "purpose": "proof",
            "observation_summary": "observed",
            "observed_at": "2026-01-01T00:00:00Z",
            "primary_artifact_ref": composed,
        },
    }
    bundle["evidence"]["operational_artifacts"] = [item]  # type: ignore[index]
    bundle["provenance"] = [_provenance("p-1", "e-1")]
    bundle["artifacts"] = [_artifact(composed)]
    bundle["evidence_manifest"] = [
        {
            "evidence_id": "e-1",
            "evidence_family": "operational_artifacts",
            "record_ref": item["source_ref"],
            "classification": item["classification"],
            "provenance_refs": ["p-1"],
            "artifact_refs": [decomposed],
        }
    ]
    observed = validate_semantics(bundle)
    assert NdebValidationIssue(
        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
        "/evidence/operational_artifacts/0/material/primary_artifact_ref",
    ) not in observed


def test_primary_artifact_non_equivalent_membership_has_exact_pointer() -> None:
    bundle = base_bundle()
    item = {
        "evidence_id": "e-1",
        "record_type": "operational_artifact",
        "record_id": "record-e-1",
        "record_version": 1,
        "source_ref": source_ref("source-e-1"),
        "classification": classification(),
        "provenance_refs": ["p-1"],
        "artifact_refs": ["artifact-2"],
        "material": {
            "purpose": "proof",
            "observation_summary": "observed",
            "observed_at": "2026-01-01T00:00:00Z",
            "primary_artifact_ref": "artifact-1",
        },
    }
    bundle["evidence"]["operational_artifacts"] = [item]  # type: ignore[index]
    bundle["provenance"] = [_provenance("p-1", "e-1")]
    bundle["artifacts"] = [_artifact("artifact-1"), _artifact("artifact-2")]
    bundle["evidence_manifest"] = [
        {
            "evidence_id": "e-1",
            "evidence_family": "operational_artifacts",
            "record_ref": item["source_ref"],
            "classification": item["classification"],
            "provenance_refs": ["p-1"],
            "artifact_refs": ["artifact-2"],
        }
    ]
    observed = validate_semantics(bundle)
    assert NdebValidationIssue(
        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
        "/evidence/operational_artifacts/0/material/primary_artifact_ref",
    ) in observed




_EVIDENCE_FAMILIES = (
    "architecture_decisions",
    "agent_catalog",
    "tool_catalog",
    "model_inventory",
    "security_controls",
    "evaluations",
    "deployment_evidence",
    "operational_artifacts",
    "risks",
)


def _closed_risk_bundle() -> tuple[dict[str, object], dict[str, object]]:
    bundle = base_bundle()
    item = _risk_with_refs("e-1", provenance_refs=["p-1"], artifact_refs=["a-1"])
    bundle["evidence"]["risks"] = [item]  # type: ignore[index]
    bundle["provenance"] = [_provenance("p-1", "e-1")]
    bundle["artifacts"] = [_artifact("a-1")]
    bundle["evidence_manifest"] = [
        _manifest_for(item, provenance_refs=["p-1"], artifact_refs=["a-1"])
    ]
    return bundle, item


def test_reference_fixture_contains_all_nine_evidence_families() -> None:
    evidence = base_bundle()["evidence"]
    assert isinstance(evidence, dict)
    assert tuple(evidence) == _EVIDENCE_FAMILIES


def test_manifest_cardinality_and_one_to_one_join_are_enforced() -> None:
    bundle = base_bundle()
    bundle["evidence"]["risks"] = [_risk("e-1")]  # type: ignore[index]
    observed = validate_semantics(bundle)
    assert NdebValidationIssue(
        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
        "/evidence_manifest",
    ) in observed


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("evidence_family", "architecture_decisions"),
        ("record_ref", source_ref("different-source")),
        (
            "classification",
            {"value": "confidential", "authority_ref": source_ref("classification-policy")},
        ),
        ("provenance_refs", ["p-2"]),
        ("artifact_refs", ["a-2"]),
    ],
)
def test_each_manifest_joined_field_mismatch_is_detected(field: str, replacement: object) -> None:
    bundle, _ = _closed_risk_bundle()
    if field == "provenance_refs":
        bundle["provenance"] = [_provenance("p-1", "e-1"), _provenance("p-2", "e-1")]
    if field == "artifact_refs":
        bundle["artifacts"] = [_artifact("a-1"), _artifact("a-2")]
    bundle["evidence_manifest"][0][field] = replacement  # type: ignore[index]
    assert NdebIssueCode.MANIFEST_EVIDENCE_MISMATCH in codes(bundle)


@pytest.mark.parametrize(
    ("collection", "identity_key"),
    [("artifacts", "artifact_id"), ("provenance", "provenance_id"), ("approvals", "approval_id")],
)
def test_top_level_semantic_identity_duplicates(collection: str, identity_key: str) -> None:
    bundle = base_bundle()
    bundle[collection] = [{identity_key: "dup"}, {identity_key: "dup"}]
    assert NdebIssueCode.SEMANTIC_DUPLICATE_IDENTITY in codes(bundle)


@pytest.mark.parametrize("family", _EVIDENCE_FAMILIES)
def test_every_evidence_family_enforces_evidence_id_ordering(family: str) -> None:
    bundle = base_bundle()
    bundle["evidence"][family] = [{"evidence_id": "b"}, {"evidence_id": "a"}]  # type: ignore[index]
    assert NdebIssueCode.SEMANTIC_ORDERING_VIOLATION in codes(bundle)


@pytest.mark.parametrize(
    "collection",
    ["evidence_manifest", "artifacts", "provenance", "approvals"],
)
def test_top_level_set_like_object_collections_enforce_ordering(collection: str) -> None:
    key = {
        "evidence_manifest": "evidence_id",
        "artifacts": "artifact_id",
        "provenance": "provenance_id",
        "approvals": "approval_id",
    }[collection]
    bundle = base_bundle()
    bundle[collection] = [{key: "b"}, {key: "a"}]
    assert NdebIssueCode.SEMANTIC_ORDERING_VIOLATION in codes(bundle)


def test_required_extensions_ordering() -> None:
    bundle = base_bundle()
    bundle["required_extensions"] = ["com.z/x", "com.a/x"]
    bundle["extensions"] = {"com.z/x": {}, "com.a/x": {}}
    assert NdebIssueCode.SEMANTIC_ORDERING_VIOLATION in codes(bundle)


def test_snapshot_approval_refs_ordering() -> None:
    bundle = base_bundle()
    bundle["approved_snapshot"]["approval_refs"] = ["b", "a"]  # type: ignore[index]
    assert NdebIssueCode.SEMANTIC_ORDERING_VIOLATION in codes(bundle)


def test_evidence_and_manifest_reference_arrays_enforce_ordering() -> None:
    bundle, item = _closed_risk_bundle()
    item["provenance_refs"] = ["p-2", "p-1"]
    item["artifact_refs"] = ["a-2", "a-1"]
    bundle["provenance"] = [_provenance("p-1", "e-1"), _provenance("p-2", "e-1")]
    bundle["artifacts"] = [_artifact("a-1"), _artifact("a-2")]
    manifest = bundle["evidence_manifest"][0]  # type: ignore[index]
    manifest["provenance_refs"] = ["p-2", "p-1"]
    manifest["artifact_refs"] = ["a-2", "a-1"]
    observed = validate_semantics(bundle)
    pointers = {
        issue.json_pointer
        for issue in observed
        if issue.code is NdebIssueCode.SEMANTIC_ORDERING_VIOLATION
    }
    assert "/evidence/risks/0/provenance_refs" in pointers
    assert "/evidence/risks/0/artifact_refs" in pointers
    assert "/evidence_manifest/0/provenance_refs" in pointers
    assert "/evidence_manifest/0/artifact_refs" in pointers


def test_provenance_source_refs_ordering() -> None:
    bundle = base_bundle()
    bundle["provenance"] = [
        {
            "provenance_id": "p-1",
            "subject_ref": {"subject_type": "approved_snapshot", "subject_id": "snapshot-1"},
            "source_refs": [source_ref("z"), source_ref("a")],
            "recorded_at": "2026-01-01T00:00:00Z",
        }
    ]
    assert NdebIssueCode.SEMANTIC_ORDERING_VIOLATION in codes(bundle)


def test_nfc_aware_ordering() -> None:
    bundle = base_bundle()
    bundle["artifacts"] = [_artifact("é"), _artifact("z")]
    assert NdebIssueCode.SEMANTIC_ORDERING_VIOLATION in codes(bundle)


def test_nfc_aware_duplicate_semantic_identity() -> None:
    bundle = base_bundle()
    bundle["artifacts"] = [_artifact("é"), _artifact("e\u0301")]
    assert NdebIssueCode.SEMANTIC_DUPLICATE_IDENTITY in codes(bundle)


def test_valid_arbitrary_precision_timestamp() -> None:
    bundle = base_bundle()
    bundle["approved_snapshot"]["captured_at"] = "2026-01-01T00:00:00.12345678901234567890Z"  # type: ignore[index]
    bundle["approved_snapshot"]["approved_at"] = "2026-01-01T00:00:00.12345678901234567891Z"  # type: ignore[index]
    observed = codes(bundle)
    assert NdebIssueCode.TIMESTAMP_INVALID not in observed
    assert NdebIssueCode.TEMPORAL_ORDER_VIOLATION not in observed


def test_temporal_equality_with_different_fraction_widths() -> None:
    bundle = base_bundle()
    bundle["approved_snapshot"]["captured_at"] = "2026-01-01T00:00:00.1Z"  # type: ignore[index]
    bundle["approved_snapshot"]["approved_at"] = "2026-01-01T00:00:00.1000000Z"  # type: ignore[index]
    assert NdebIssueCode.TEMPORAL_ORDER_VIOLATION not in codes(bundle)


def test_high_precision_temporal_order_violation_beyond_microseconds() -> None:
    bundle = base_bundle()
    bundle["approved_snapshot"]["captured_at"] = "2026-01-01T00:00:00.0000001Z"  # type: ignore[index]
    bundle["approved_snapshot"]["approved_at"] = "2026-01-01T00:00:00.0000000Z"  # type: ignore[index]
    assert NdebIssueCode.TEMPORAL_ORDER_VIOLATION in codes(bundle)


def test_all_non_snapshot_timestamp_locations_are_validated() -> None:
    bundle = base_bundle()
    bundle["approvals"][0]["approved_at"] = "2026-99-01T00:00:00Z"  # type: ignore[index]
    bundle["provenance"] = [
        {
            "provenance_id": "p-1",
            "subject_ref": {"subject_type": "approved_snapshot", "subject_id": "snapshot-1"},
            "source_refs": [source_ref("source")],
            "recorded_at": "2026-99-01T00:00:00Z",
        }
    ]
    for family, field in (
        ("evaluations", "measured_at"),
        ("deployment_evidence", "deployed_at"),
        ("operational_artifacts", "observed_at"),
    ):
        bundle["evidence"][family] = [  # type: ignore[index]
            {
                "evidence_id": f"e-{family}",
                "provenance_refs": [],
                "artifact_refs": [],
                "material": {field: "2026-99-01T00:00:00Z"},
            }
        ]
    observed = validate_semantics(bundle)
    pointers = {
        issue.json_pointer for issue in observed if issue.code is NdebIssueCode.TIMESTAMP_INVALID
    }
    assert "/approvals/0/approved_at" in pointers
    assert "/provenance/0/recorded_at" in pointers
    assert "/evidence/evaluations/0/material/measured_at" in pointers
    assert "/evidence/deployment_evidence/0/material/deployed_at" in pointers
    assert "/evidence/operational_artifacts/0/material/observed_at" in pointers


def test_unknown_optional_extension_remains_semantically_allowed() -> None:
    bundle = base_bundle()
    bundle["extensions"] = {"com.example/future": {"opaque": "value"}}
    assert not validate_semantics(bundle)
