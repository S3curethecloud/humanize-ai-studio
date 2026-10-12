"""Normative NDEB semantic validation not fully expressed by JSON Schema."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from .contracts import NdebIssueCode, NdebValidationIssue

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
_TIMESTAMP_RE = re.compile(
    r"^(?P<whole>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.(?P<fraction>[0-9]+))?Z$"
)


def _issue(code: NdebIssueCode, pointer: str) -> NdebValidationIssue:
    return NdebValidationIssue(code, pointer)


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _normalize_for_compare(value: Any) -> Any:
    if isinstance(value, str):
        return _nfc(value)
    if isinstance(value, list):
        return [_normalize_for_compare(item) for item in value]
    if isinstance(value, dict):
        return {_nfc(str(key)): _normalize_for_compare(child) for key, child in value.items()}
    return value


def _walk_nulls(value: Any, path: tuple[Any, ...] = ()) -> Iterable[str]:
    if value is None:
        yield _pointer(path)
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_nulls(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_nulls(child, path + (index,))


def _pointer(path: tuple[Any, ...]) -> str:
    if not path:
        return ""
    return "/" + "/".join(
        str(part).replace("~", "~0").replace("/", "~1") for part in path
    )


def _parse_timestamp(value: Any) -> tuple[datetime, str] | None:
    if not isinstance(value, str):
        return None
    match = _TIMESTAMP_RE.fullmatch(value)
    if match is None:
        return None
    try:
        whole = datetime.fromisoformat(match.group("whole") + "+00:00")
    except ValueError:
        return None
    return whole, match.group("fraction") or ""


def _timestamp_is_after(
    left: tuple[datetime, str],
    right: tuple[datetime, str],
) -> bool:
    left_whole, left_fraction = left
    right_whole, right_fraction = right
    if left_whole != right_whole:
        return left_whole > right_whole
    width = max(len(left_fraction), len(right_fraction))
    return left_fraction.ljust(width, "0") > right_fraction.ljust(width, "0")


def _check_sorted_unique_strings(
    values: Any,
    pointer: str,
    issues: list[NdebValidationIssue],
) -> None:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        return
    keys = [_nfc(value) for value in values]
    if keys != sorted(keys):
        issues.append(_issue(NdebIssueCode.SEMANTIC_ORDERING_VIOLATION, pointer))
    if len(keys) != len(set(keys)):
        issues.append(_issue(NdebIssueCode.SEMANTIC_DUPLICATE_IDENTITY, pointer))


def _check_sorted_unique_objects(
    values: Any,
    pointer: str,
    key_name: str,
    issues: list[NdebValidationIssue],
) -> None:
    if not isinstance(values, list):
        return
    keys = [item.get(key_name) for item in values if isinstance(item, dict)]
    if len(keys) != len(values) or not all(isinstance(key, str) for key in keys):
        return
    string_keys = [key for key in keys if isinstance(key, str)]
    normalized = [_nfc(key) for key in string_keys]
    if normalized != sorted(normalized):
        issues.append(_issue(NdebIssueCode.SEMANTIC_ORDERING_VIOLATION, pointer))
    if len(normalized) != len(set(normalized)):
        issues.append(_issue(NdebIssueCode.SEMANTIC_DUPLICATE_IDENTITY, pointer))


def _source_ref_key(value: Any) -> tuple[str, str, int, str] | None:
    if not isinstance(value, dict):
        return None
    object_type = value.get("object_type")
    object_id = value.get("object_id")
    object_version = value.get("object_version")
    relation = value.get("relation", "")
    if not isinstance(object_type, str) or not isinstance(object_id, str):
        return None
    if not isinstance(object_version, int) or isinstance(object_version, bool):
        return None
    if not isinstance(relation, str):
        return None
    return (_nfc(object_type), _nfc(object_id), object_version, _nfc(relation))


def validate_semantics(candidate: dict[str, Any]) -> tuple[NdebValidationIssue, ...]:
    issues: list[NdebValidationIssue] = []

    for pointer in _walk_nulls(candidate):
        issues.append(_issue(NdebIssueCode.NORMATIVE_NULL_PROHIBITED, pointer))

    snapshot = candidate.get("approved_snapshot")
    if isinstance(snapshot, dict):
        captured = _parse_timestamp(snapshot.get("captured_at"))
        approved = _parse_timestamp(snapshot.get("approved_at"))
        if captured is None:
            issues.append(_issue(NdebIssueCode.TIMESTAMP_INVALID, "/approved_snapshot/captured_at"))
        if approved is None:
            issues.append(_issue(NdebIssueCode.TIMESTAMP_INVALID, "/approved_snapshot/approved_at"))
        if (
            captured is not None
            and approved is not None
            and _timestamp_is_after(captured, approved)
        ):
            issues.append(_issue(NdebIssueCode.TEMPORAL_ORDER_VIOLATION, "/approved_snapshot"))
        _check_sorted_unique_strings(
            snapshot.get("approval_refs"), "/approved_snapshot/approval_refs", issues
        )

    timestamp_locations = (
        ("approvals", "approved_at"),
        ("provenance", "recorded_at"),
    )
    for array_name, field in timestamp_locations:
        values = candidate.get(array_name)
        if isinstance(values, list):
            for index, item in enumerate(values):
                if (
                    isinstance(item, dict)
                    and field in item
                    and _parse_timestamp(item.get(field)) is None
                ):
                    issues.append(
                        _issue(NdebIssueCode.TIMESTAMP_INVALID, f"/{array_name}/{index}/{field}")
                    )

    evidence = candidate.get("evidence")
    evidence_by_id: dict[str, tuple[str, int, dict[str, Any]]] = {}
    all_evidence_ids: list[str] = []
    if isinstance(evidence, dict):
        for family in _EVIDENCE_FAMILIES:
            items = evidence.get(family)
            _check_sorted_unique_objects(items, f"/evidence/{family}", "evidence_id", issues)
            if not isinstance(items, list):
                continue
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                evidence_id = item.get("evidence_id")
                if isinstance(evidence_id, str):
                    normalized_id = _nfc(evidence_id)
                    all_evidence_ids.append(normalized_id)
                    if normalized_id in evidence_by_id:
                        issues.append(
                            _issue(
                                NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
                                f"/evidence/{family}/{index}/evidence_id",
                            )
                        )
                    else:
                        evidence_by_id[normalized_id] = (family, index, item)
                _check_sorted_unique_strings(
                    item.get("provenance_refs"),
                    f"/evidence/{family}/{index}/provenance_refs",
                    issues,
                )
                _check_sorted_unique_strings(
                    item.get("artifact_refs"),
                    f"/evidence/{family}/{index}/artifact_refs",
                    issues,
                )
                material = item.get("material")
                for field in ("measured_at", "deployed_at", "observed_at"):
                    if (
                        isinstance(material, dict)
                        and field in material
                        and _parse_timestamp(material[field]) is None
                    ):
                        issues.append(
                            _issue(
                                NdebIssueCode.TIMESTAMP_INVALID,
                                f"/evidence/{family}/{index}/material/{field}",
                            )
                        )
    if len(all_evidence_ids) != len(set(all_evidence_ids)):
        issues.append(_issue(NdebIssueCode.SEMANTIC_DUPLICATE_IDENTITY, "/evidence"))

    manifest = candidate.get("evidence_manifest")
    _check_sorted_unique_objects(manifest, "/evidence_manifest", "evidence_id", issues)
    if isinstance(manifest, list):
        if len(manifest) != len(evidence_by_id):
            issues.append(_issue(NdebIssueCode.REFERENTIAL_CLOSURE_INVALID, "/evidence_manifest"))
        seen_manifest: set[str] = set()
        for index, entry in enumerate(manifest):
            if not isinstance(entry, dict) or not isinstance(entry.get("evidence_id"), str):
                continue
            evidence_id = _nfc(entry["evidence_id"])
            if evidence_id in seen_manifest:
                issues.append(
                    _issue(
                        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
                        f"/evidence_manifest/{index}/evidence_id",
                    )
                )
                continue
            seen_manifest.add(evidence_id)
            joined = evidence_by_id.get(evidence_id)
            if joined is None:
                issues.append(
                    _issue(
                        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
                        f"/evidence_manifest/{index}/evidence_id",
                    )
                )
                continue
            family, _, item = joined
            expected = {
                "evidence_family": family,
                "record_ref": item.get("source_ref"),
                "classification": item.get("classification"),
                "provenance_refs": item.get("provenance_refs"),
                "artifact_refs": item.get("artifact_refs"),
            }
            actual = {key: entry.get(key) for key in expected}
            if _normalize_for_compare(actual) != _normalize_for_compare(expected):
                issues.append(
                    _issue(NdebIssueCode.MANIFEST_EVIDENCE_MISMATCH, f"/evidence_manifest/{index}")
                )
            _check_sorted_unique_strings(
                entry.get("provenance_refs"), f"/evidence_manifest/{index}/provenance_refs", issues
            )
            _check_sorted_unique_strings(
                entry.get("artifact_refs"), f"/evidence_manifest/{index}/artifact_refs", issues
            )

    artifacts = candidate.get("artifacts")
    provenance = candidate.get("provenance")
    approvals = candidate.get("approvals")
    _check_sorted_unique_objects(artifacts, "/artifacts", "artifact_id", issues)
    _check_sorted_unique_objects(provenance, "/provenance", "provenance_id", issues)
    _check_sorted_unique_objects(approvals, "/approvals", "approval_id", issues)

    def id_set(values: Any, name: str, pointer: str) -> set[str]:
        if not isinstance(values, list):
            return set()
        keys = [
            _nfc(item[name])
            for item in values
            if isinstance(item, dict) and isinstance(item.get(name), str)
        ]
        if len(keys) != len(set(keys)):
            issues.append(_issue(NdebIssueCode.REFERENTIAL_CLOSURE_INVALID, pointer))
        return set(keys)

    artifact_ids = id_set(artifacts, "artifact_id", "/artifacts")
    provenance_ids = id_set(provenance, "provenance_id", "/provenance")
    approval_ids = id_set(approvals, "approval_id", "/approvals")

    if isinstance(manifest, list):
        for manifest_index, entry in enumerate(manifest):
            if not isinstance(entry, dict):
                continue
            for field, valid_ids in (
                ("provenance_refs", provenance_ids),
                ("artifact_refs", artifact_ids),
            ):
                values = entry.get(field)
                if not isinstance(values, list):
                    continue
                for ref_index, ref in enumerate(values):
                    if isinstance(ref, str) and _nfc(ref) not in valid_ids:
                        issues.append(
                            _issue(
                                NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
                                f"/evidence_manifest/{manifest_index}/{field}/{ref_index}",
                            )
                        )

    if isinstance(snapshot, dict) and isinstance(snapshot.get("approval_refs"), list):
        for index, approval_id in enumerate(snapshot["approval_refs"]):
            if isinstance(approval_id, str) and _nfc(approval_id) not in approval_ids:
                issues.append(
                    _issue(
                        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
                        f"/approved_snapshot/approval_refs/{index}",
                    )
                )

    for family, item_index, item in evidence_by_id.values():
        for field, valid_ids in (
            ("provenance_refs", provenance_ids),
            ("artifact_refs", artifact_ids),
        ):
            values = item.get(field)
            if isinstance(values, list):
                for ref_index, ref in enumerate(values):
                    if isinstance(ref, str) and _nfc(ref) not in valid_ids:
                        issues.append(
                            _issue(
                                NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
                                f"/evidence/{family}/{item_index}/{field}/{ref_index}",
                            )
                        )
        if family == "operational_artifacts":
            material = item.get("material")
            primary = material.get("primary_artifact_ref") if isinstance(material, dict) else None
            refs = item.get("artifact_refs")
            if isinstance(primary, str):
                normalized_refs = (
                    {_nfc(ref) for ref in refs if isinstance(ref, str)}
                    if isinstance(refs, list)
                    else set()
                )
                if _nfc(primary) not in artifact_ids or _nfc(primary) not in normalized_refs:
                    issues.append(
                        _issue(
                            NdebIssueCode.REFERENTIAL_CLOSURE_INVALID,
                            f"/evidence/{family}/{item_index}/material/primary_artifact_ref",
                        )
                    )

    if isinstance(provenance, list):
        snapshot_id = snapshot.get("snapshot_id") if isinstance(snapshot, dict) else None
        for index, entry in enumerate(provenance):
            if not isinstance(entry, dict):
                continue
            source_refs = entry.get("source_refs")
            if isinstance(source_refs, list):
                keys = [_source_ref_key(value) for value in source_refs]
                if all(key is not None for key in keys):
                    complete = [key for key in keys if key is not None]
                    if complete != sorted(complete):
                        issues.append(
                            _issue(
                                NdebIssueCode.SEMANTIC_ORDERING_VIOLATION,
                                f"/provenance/{index}/source_refs",
                            )
                        )
                    if len(complete) != len(set(complete)):
                        issues.append(
                            _issue(
                                NdebIssueCode.SEMANTIC_DUPLICATE_IDENTITY,
                                f"/provenance/{index}/source_refs",
                            )
                        )
            subject = entry.get("subject_ref")
            if isinstance(subject, dict):
                subject_type = subject.get("subject_type")
                subject_id = subject.get("subject_id")
                valid = False
                if isinstance(subject_id, str):
                    normalized = _nfc(subject_id)
                    if subject_type == "evidence":
                        valid = normalized in evidence_by_id
                    elif subject_type == "artifact":
                        valid = normalized in artifact_ids
                    elif subject_type == "approval":
                        valid = normalized in approval_ids
                    elif subject_type == "approved_snapshot" and isinstance(snapshot_id, str):
                        valid = normalized == _nfc(snapshot_id)
                if not valid:
                    issues.append(
                        _issue(NdebIssueCode.PROVENANCE_INVALID, f"/provenance/{index}/subject_ref")
                    )

    required_extensions = candidate.get("required_extensions")
    extensions = candidate.get("extensions")
    _check_sorted_unique_strings(required_extensions, "/required_extensions", issues)
    if isinstance(required_extensions, list):
        extension_keys = set(extensions) if isinstance(extensions, dict) else set()
        for index, name in enumerate(required_extensions):
            if isinstance(name, str) and name not in extension_keys:
                issues.append(
                    _issue(
                        NdebIssueCode.REFERENTIAL_CLOSURE_INVALID, f"/required_extensions/{index}"
                    )
                )
        if required_extensions:
            issues.append(
                _issue(NdebIssueCode.REQUIRED_EXTENSION_UNSUPPORTED, "/required_extensions")
            )

    return tuple(sorted(set(issues), key=lambda item: (item.code.value, item.json_pointer)))
