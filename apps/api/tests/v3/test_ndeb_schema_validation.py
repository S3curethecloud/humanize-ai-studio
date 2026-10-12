from __future__ import annotations

import copy

from jsonschema import Draft202012Validator

from app.v3.ndeb.contracts import NdebIssueCode
from app.v3.ndeb.schema_validation import load_pinned_schema, validate_structure
from tests.v3.test_ndeb_validator import base_bundle


def codes(result: object) -> set[NdebIssueCode]:
    return {issue.code for issue in result.issues}  # type: ignore[attr-defined]


def test_schema_loads_and_check_schema_passes() -> None:
    Draft202012Validator.check_schema(load_pinned_schema())


def test_unknown_top_level_field_is_structural_error() -> None:
    bundle = base_bundle()
    bundle["unknown"] = True
    result = validate_structure(bundle)
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID in codes(result)


def test_missing_required_top_level_classification_is_specific_error() -> None:
    bundle = base_bundle()
    del bundle["classification"]
    result = validate_structure(bundle)
    assert result.issues == (
        result.issues[0].__class__(NdebIssueCode.CLASSIFICATION_INVALID, "/classification"),
    )


def test_unknown_optional_extension_object_is_structurally_allowed() -> None:
    bundle = base_bundle()
    bundle["extensions"] = {"com.example/foo": {"future": "value"}}
    result = validate_structure(bundle)
    assert not result.issues


def test_unsupported_algorithm_is_partitioned() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    result = validate_structure(bundle)
    assert result.unsupported_integrity_contract
    assert result.issues[0].code is NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED
    assert all(issue.code is not NdebIssueCode.SCHEMA_STRUCTURE_INVALID for issue in result.issues)


def test_all_three_unsupported_selectors_partition() -> None:
    bundle = base_bundle()
    integrity = bundle["integrity"]  # type: ignore[assignment]
    integrity["algorithm"] = "sha-512"
    integrity["canonicalization"] = "OTHER"
    integrity["identity_material_version"] = 2
    result = validate_structure(bundle)
    assert result.unsupported_integrity_contract
    assert len(result.issues) == 3
    assert {issue.code for issue in result.issues} == {NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED}


def test_wrong_type_selector_disqualifies_partition() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = 1  # type: ignore[index]
    result = validate_structure(bundle)
    assert not result.unsupported_integrity_contract
    assert NdebIssueCode.INTEGRITY_METADATA_INVALID in codes(result)


def test_malformed_digest_disqualifies_partition() -> None:
    bundle = base_bundle()
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    bundle["integrity"]["content_digest_sha256"] = "bad"  # type: ignore[index]
    result = validate_structure(bundle)
    assert not result.unsupported_integrity_contract
    assert NdebIssueCode.INTEGRITY_METADATA_INVALID in codes(result)


def test_unknown_integrity_member_disqualifies_partition() -> None:
    bundle = copy.deepcopy(base_bundle())
    bundle["integrity"]["algorithm"] = "sha-512"  # type: ignore[index]
    bundle["integrity"]["extra"] = 1  # type: ignore[index]
    result = validate_structure(bundle)
    assert not result.unsupported_integrity_contract
    assert NdebIssueCode.INTEGRITY_METADATA_INVALID in codes(result)


def test_schema_identity_metadata_and_refs_are_exact() -> None:
    schema = load_pinned_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:nexus:ndeb:schema:1.0.0"

    refs: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "$ref":
                    assert isinstance(child, str)
                    refs.append(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema)
    assert refs
    assert all(ref.startswith("#") for ref in refs)


def test_invalid_bundle_id_lexical_form_fails_structure() -> None:
    bundle = base_bundle()
    bundle["bundle_id"] = "not-a-bundle-id"
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID in codes(validate_structure(bundle))


def test_invalid_sha256_lexical_form_is_integrity_metadata_error() -> None:
    bundle = base_bundle()
    bundle["integrity"]["content_digest_sha256"] = "ABC"  # type: ignore[index]
    assert NdebIssueCode.INTEGRITY_METADATA_INVALID in codes(validate_structure(bundle))


def test_invalid_extension_name_fails_structure() -> None:
    bundle = base_bundle()
    bundle["extensions"] = {"invalid": {}}
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID in codes(validate_structure(bundle))


def test_normative_null_fails_structure_where_schema_expresses_it() -> None:
    bundle = base_bundle()
    bundle["tenant_id"] = None
    assert NdebIssueCode.SCHEMA_STRUCTURE_INVALID in codes(validate_structure(bundle))


def test_missing_root_integrity_is_partitioned_without_generic_schema_issue() -> None:
    bundle = base_bundle()
    del bundle["integrity"]
    result = validate_structure(bundle)
    assert result.issues == (
        result.issues[0].__class__(NdebIssueCode.INTEGRITY_METADATA_INVALID, "/integrity"),
    )


def test_missing_integrity_and_classification_emit_both_specific_partitions() -> None:
    bundle = base_bundle()
    del bundle["integrity"]
    del bundle["classification"]
    result = validate_structure(bundle)
    assert {issue.code for issue in result.issues} == {
        NdebIssueCode.INTEGRITY_METADATA_INVALID,
        NdebIssueCode.CLASSIFICATION_INVALID,
    }
    assert {issue.json_pointer for issue in result.issues} == {
        "/integrity",
        "/classification",
    }




def test_missing_classification_plus_unrelated_required_member_preserves_generic_error() -> None:
    bundle = base_bundle()
    del bundle["classification"]
    del bundle["tenant_id"]
    result = validate_structure(bundle)
    assert {issue.code for issue in result.issues} == {
        NdebIssueCode.CLASSIFICATION_INVALID,
        NdebIssueCode.SCHEMA_STRUCTURE_INVALID,
    }
    assert any(
        issue.code is NdebIssueCode.CLASSIFICATION_INVALID
        and issue.json_pointer == "/classification"
        for issue in result.issues
    )
    assert any(
        issue.code is NdebIssueCode.SCHEMA_STRUCTURE_INVALID
        and issue.json_pointer == ""
        for issue in result.issues
    )


def test_classification_wrong_type_is_specific_error() -> None:
    bundle = base_bundle()
    bundle["classification"] = "internal"
    result = validate_structure(bundle)
    assert codes(result) == {NdebIssueCode.CLASSIFICATION_INVALID}
    assert {issue.json_pointer for issue in result.issues} == {"/classification"}


def test_classification_authority_ref_malformed_is_specific_error() -> None:
    bundle = base_bundle()
    bundle["classification"]["authority_ref"] = {}  # type: ignore[index]
    result = validate_structure(bundle)
    assert codes(result) == {NdebIssueCode.CLASSIFICATION_INVALID}
    assert all(
        issue.json_pointer.startswith("/classification/authority_ref") for issue in result.issues
    )


def test_manifest_classification_malformed_is_specific_error() -> None:
    bundle = base_bundle()
    bundle["evidence_manifest"] = [
        {
            "evidence_id": "e-1",
            "evidence_family": "risks",
            "record_ref": {"object_type": "record", "object_id": "r-1", "object_version": 1},
            "classification": "internal",
            "provenance_refs": ["p-1"],
            "artifact_refs": [],
        }
    ]
    result = validate_structure(bundle)
    assert NdebIssueCode.CLASSIFICATION_INVALID in codes(result)
    assert any(
        issue.json_pointer == "/evidence_manifest/0/classification" for issue in result.issues
    )


def test_evidence_classification_malformed_is_specific_error() -> None:
    bundle = base_bundle()
    bundle["evidence"]["risks"] = [  # type: ignore[index]
        {
            "evidence_id": "e-1",
            "record_type": "risk",
            "record_id": "r-1",
            "record_version": 1,
            "source_ref": {"object_type": "record", "object_id": "r-1", "object_version": 1},
            "classification": "internal",
            "provenance_refs": ["p-1"],
            "artifact_refs": [],
            "material": {"title": "t", "risk_statement": "r", "severity": "high", "status": "open"},
        }
    ]
    result = validate_structure(bundle)
    assert NdebIssueCode.CLASSIFICATION_INVALID in codes(result)
    assert any(issue.json_pointer == "/evidence/risks/0/classification" for issue in result.issues)


def test_missing_root_provenance_is_specific_error() -> None:
    bundle = base_bundle()
    del bundle["provenance"]
    result = validate_structure(bundle)
    assert codes(result) == {NdebIssueCode.PROVENANCE_INVALID}
    assert {issue.json_pointer for issue in result.issues} == {"/provenance"}


def test_provenance_wrong_type_is_specific_error() -> None:
    bundle = base_bundle()
    bundle["provenance"] = "bad"
    result = validate_structure(bundle)
    assert codes(result) == {NdebIssueCode.PROVENANCE_INVALID}
    assert {issue.json_pointer for issue in result.issues} == {"/provenance"}


def test_malformed_provenance_entry_is_specific_error() -> None:
    bundle = base_bundle()
    bundle["provenance"] = [{"provenance_id": "p-1"}]
    result = validate_structure(bundle)
    assert codes(result) == {NdebIssueCode.PROVENANCE_INVALID}
    assert all(issue.json_pointer.startswith("/provenance/0/") for issue in result.issues)


def test_malformed_evidence_provenance_refs_is_specific_error() -> None:
    bundle = base_bundle()
    bundle["evidence"]["risks"] = [  # type: ignore[index]
        {
            "evidence_id": "e-1",
            "record_type": "risk",
            "record_id": "r-1",
            "record_version": 1,
            "source_ref": {"object_type": "record", "object_id": "r-1", "object_version": 1},
            "classification": base_bundle()["classification"],
            "provenance_refs": "p-1",
            "artifact_refs": [],
            "material": {"title": "t", "risk_statement": "r", "severity": "high", "status": "open"},
        }
    ]
    result = validate_structure(bundle)
    assert NdebIssueCode.PROVENANCE_INVALID in codes(result)
    assert any(issue.json_pointer == "/evidence/risks/0/provenance_refs" for issue in result.issues)


def test_missing_provenance_plus_unrelated_required_member_preserves_generic_error() -> None:
    bundle = base_bundle()
    del bundle["provenance"]
    del bundle["tenant_id"]
    result = validate_structure(bundle)
    assert {issue.code for issue in result.issues} == {
        NdebIssueCode.PROVENANCE_INVALID,
        NdebIssueCode.SCHEMA_STRUCTURE_INVALID,
    }
    assert any(issue.json_pointer == "/provenance" for issue in result.issues)
    assert any(
        issue.code is NdebIssueCode.SCHEMA_STRUCTURE_INVALID and issue.json_pointer == ""
        for issue in result.issues
    )
