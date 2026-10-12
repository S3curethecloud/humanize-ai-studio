"""Pinned Draft-2020-12 structural validation and R1R1 error partition."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .contracts import (
    EXPECTED_SCHEMA_GIT_BLOB,
    SUPPORTED_SCHEMA_DOCUMENT_ID,
    SUPPORTED_SCHEMA_DRAFT,
    NdebIssueCode,
    NdebValidationIssue,
)

_INTEGRITY_KEYS = frozenset(
    {"algorithm", "canonicalization", "identity_material_version", "content_digest_sha256"}
)
_SELECTOR_PATHS = {
    ("integrity", "algorithm"),
    ("integrity", "canonicalization"),
    ("integrity", "identity_material_version"),
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SchemaValidationResult:
    issues: tuple[NdebValidationIssue, ...]
    unsupported_integrity_contract: bool


def _json_pointer(path: Iterable[Any]) -> str:
    parts = []
    for part in path:
        text = str(part).replace("~", "~0").replace("/", "~1")
        parts.append(text)
    return "" if not parts else "/" + "/".join(parts)


def _git_blob_sha(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def _refs_are_local(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "$ref" and (not isinstance(child, str) or not child.startswith("#")):
                return False
            if not _refs_are_local(child):
                return False
    elif isinstance(value, list):
        return all(_refs_are_local(child) for child in value)
    return True


def load_pinned_schema() -> dict[str, Any]:
    data = resources.files("app.v3.ndeb").joinpath("resources/ndeb.schema.json").read_bytes()
    if _git_blob_sha(data) != EXPECTED_SCHEMA_GIT_BLOB:
        raise ValueError("schema blob identity mismatch")
    schema = json.loads(data)
    if schema.get("$schema") != SUPPORTED_SCHEMA_DRAFT:
        raise ValueError("schema draft mismatch")
    if schema.get("$id") != SUPPORTED_SCHEMA_DOCUMENT_ID:
        raise ValueError("schema document id mismatch")
    if not _refs_are_local(schema):
        raise ValueError("external schema reference prohibited")
    Draft202012Validator.check_schema(schema)
    _schema_mapping = schema
    if not isinstance(_schema_mapping, dict):
        raise TypeError("NDEB schema must decode to an object")
    return _schema_mapping


def _integrity_metadata_well_formed_except_selectors(candidate: dict[str, Any]) -> bool:
    integrity = candidate.get("integrity")
    if not isinstance(integrity, dict):
        return False
    if set(integrity) != _INTEGRITY_KEYS:
        return False
    if not isinstance(integrity.get("algorithm"), str):
        return False
    if not isinstance(integrity.get("canonicalization"), str):
        return False
    version = integrity.get("identity_material_version")
    if not isinstance(version, int) or isinstance(version, bool):
        return False
    digest = integrity.get("content_digest_sha256")
    return isinstance(digest, str) and _SHA256_RE.fullmatch(digest) is not None


def _is_integrity_error(error: ValidationError) -> bool:
    path = tuple(error.absolute_path)
    return bool(path) and path[0] == "integrity"


def _is_classification_path(path: tuple[Any, ...]) -> bool:
    return "classification" in path


def _is_provenance_path(path: tuple[Any, ...]) -> bool:
    return bool(path) and (path[0] == "provenance" or "provenance_refs" in path)


def _missing_required_fields(error: ValidationError) -> tuple[str, ...]:
    if error.validator != "required":
        return ()
    if not isinstance(error.instance, dict):
        return ()
    required = error.validator_value
    if not isinstance(required, (list, tuple)):
        return ()
    return tuple(
        name
        for name in required
        if isinstance(name, str) and name not in error.instance
    )


def _append_required_partition_issues(
    issues: list[NdebValidationIssue],
    error: ValidationError,
) -> bool:
    missing = _missing_required_fields(error)
    if not missing:
        return False

    parent_path = tuple(error.absolute_path)
    parent_pointer = _json_pointer(parent_path)
    generic_required_missing = False

    for name in missing:
        missing_path = parent_path + (name,)
        pointer = _json_pointer(missing_path)

        if not parent_path and name == "integrity":
            issues.append(
                NdebValidationIssue(NdebIssueCode.INTEGRITY_METADATA_INVALID, "/integrity")
            )
            continue

        if name == "classification" or _is_classification_path(parent_path):
            issues.append(NdebValidationIssue(NdebIssueCode.CLASSIFICATION_INVALID, pointer))
            continue

        if name in {"provenance", "provenance_refs"} or _is_provenance_path(parent_path):
            issues.append(NdebValidationIssue(NdebIssueCode.PROVENANCE_INVALID, pointer))
            continue

        generic_required_missing = True

    if generic_required_missing:
        issues.append(
            NdebValidationIssue(NdebIssueCode.SCHEMA_STRUCTURE_INVALID, parent_pointer)
        )
    return True

def _sort_key(error: ValidationError) -> tuple[tuple[str, ...], str, str]:
    return tuple(str(x) for x in error.absolute_path), str(error.validator), error.message


def validate_structure(candidate: dict[str, Any]) -> SchemaValidationResult:
    try:
        schema = load_pinned_schema()
    except (OSError, ValueError, json.JSONDecodeError):
        return SchemaValidationResult(
            issues=(NdebValidationIssue(NdebIssueCode.SCHEMA_RESOURCE_IDENTITY_MISMATCH, ""),),
            unsupported_integrity_contract=False,
        )

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(candidate), key=_sort_key)

    integrity_errors = [error for error in errors if _is_integrity_error(error)]
    well_formed = _integrity_metadata_well_formed_except_selectors(candidate)
    qualified = bool(integrity_errors) and well_formed and all(
        error.validator == "const" and tuple(error.absolute_path) in _SELECTOR_PATHS
        for error in integrity_errors
    )

    issues: list[NdebValidationIssue] = []
    for error in errors:
        path = tuple(error.absolute_path)
        pointer = _json_pointer(path)

        if _append_required_partition_issues(issues, error):
            continue

        if qualified and error in integrity_errors:
            issues.append(
                NdebValidationIssue(NdebIssueCode.INTEGRITY_CONTRACT_UNSUPPORTED, pointer)
            )
            continue

        if _is_integrity_error(error):
            issues.append(NdebValidationIssue(NdebIssueCode.INTEGRITY_METADATA_INVALID, pointer))
            continue

        if _is_classification_path(path):
            issues.append(NdebValidationIssue(NdebIssueCode.CLASSIFICATION_INVALID, pointer))
            continue

        if _is_provenance_path(path):
            issues.append(NdebValidationIssue(NdebIssueCode.PROVENANCE_INVALID, pointer))
            continue

        issues.append(NdebValidationIssue(NdebIssueCode.SCHEMA_STRUCTURE_INVALID, pointer))

    deduped = tuple(sorted(set(issues), key=lambda item: (item.code.value, item.json_pointer)))
    return SchemaValidationResult(
        issues=deduped,
        unsupported_integrity_contract=qualified,
    )
