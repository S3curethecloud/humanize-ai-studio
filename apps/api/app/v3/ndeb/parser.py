"""Bounded raw-byte and JSON parsing for NDEB candidates."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from .contracts import (
    MAX_BUNDLE_BYTES,
    MAX_COLLECTION_CARDINALITY,
    MAX_NESTING_DEPTH,
    MAX_STRING_OR_FIELD_SIZE_BYTES,
    MAX_TOTAL_JSON_NODES,
    NdebIssueCode,
)


@dataclass(frozen=True)
class NdebParseFailure(Exception):
    code: NdebIssueCode
    json_pointer: str = ""


class _DuplicateMember(Exception):
    pass


class _NonFiniteNumber(Exception):
    pass


def _scan_nesting(text: str) -> None:
    depth = 0
    in_string = False
    escape = False
    for char in text:
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > MAX_NESTING_DEPTH:
                raise NdebParseFailure(NdebIssueCode.NESTING_DEPTH_EXCEEDED)
        elif char in "]}":
            depth -= 1


def _object_pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise _DuplicateMember(key)
        obj[key] = value
    return obj


def _reject_nonfinite(value: str) -> None:
    raise _NonFiniteNumber(value)


def _walk_resources(root: Any) -> None:
    node_count = 0
    stack: list[Any] = [root]
    while stack:
        value = stack.pop()
        node_count += 1
        if node_count > MAX_TOTAL_JSON_NODES:
            raise NdebParseFailure(NdebIssueCode.JSON_NODE_COUNT_EXCEEDED)
        if isinstance(value, dict):
            if len(value) > MAX_COLLECTION_CARDINALITY:
                raise NdebParseFailure(NdebIssueCode.COLLECTION_CARDINALITY_EXCEEDED)
            for key, child in value.items():
                node_count += 1
                if node_count > MAX_TOTAL_JSON_NODES:
                    raise NdebParseFailure(NdebIssueCode.JSON_NODE_COUNT_EXCEEDED)
                if len(key.encode("utf-8")) > MAX_STRING_OR_FIELD_SIZE_BYTES:
                    raise NdebParseFailure(NdebIssueCode.STRING_SIZE_EXCEEDED)
                stack.append(child)
        elif isinstance(value, list):
            if len(value) > MAX_COLLECTION_CARDINALITY:
                raise NdebParseFailure(NdebIssueCode.COLLECTION_CARDINALITY_EXCEEDED)
            stack.extend(reversed(value))
        elif isinstance(value, float) and not math.isfinite(value):
            raise NdebParseFailure(NdebIssueCode.JSON_NONFINITE_NUMBER)
        elif isinstance(value, str):
            if len(value.encode("utf-8")) > MAX_STRING_OR_FIELD_SIZE_BYTES:
                raise NdebParseFailure(NdebIssueCode.STRING_SIZE_EXCEEDED)


def parse_candidate(candidate_bytes: bytes) -> dict[str, Any]:
    if len(candidate_bytes) > MAX_BUNDLE_BYTES:
        raise NdebParseFailure(NdebIssueCode.INPUT_TOO_LARGE)
    if candidate_bytes.startswith(b"\xef\xbb\xbf"):
        raise NdebParseFailure(NdebIssueCode.UTF8_BOM_PROHIBITED)
    try:
        text = candidate_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise NdebParseFailure(NdebIssueCode.UTF8_INVALID) from exc
    _scan_nesting(text)
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs_no_duplicates,
            parse_constant=_reject_nonfinite,
        )
    except _DuplicateMember as exc:
        raise NdebParseFailure(NdebIssueCode.JSON_DUPLICATE_MEMBER) from exc
    except _NonFiniteNumber as exc:
        raise NdebParseFailure(NdebIssueCode.JSON_NONFINITE_NUMBER) from exc
    except json.JSONDecodeError as exc:
        raise NdebParseFailure(NdebIssueCode.JSON_MALFORMED) from exc
    _walk_resources(value)
    if not isinstance(value, dict):
        raise NdebParseFailure(NdebIssueCode.SCHEMA_STRUCTURE_INVALID)
    return value
