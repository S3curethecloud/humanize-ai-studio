from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from app.v3.ndeb.contracts import MAX_CANONICAL_BYTES, NdebIssueCode
from app.v3.ndeb.integrity import canonical_bytes, validate_integrity
from app.v3.ndeb.parser import NdebParseFailure, parse_candidate
from tests.v3.test_ndeb_validator import base_bundle


def failure(data: bytes) -> NdebIssueCode:
    with pytest.raises(NdebParseFailure) as caught:
        parse_candidate(data)
    return caught.value.code


def test_bundle_size_over_limit() -> None:
    assert failure(b" " * 8_388_609) is NdebIssueCode.INPUT_TOO_LARGE


def test_collection_at_4096_reaches_root_contract_check() -> None:
    data = json.dumps({"x": list(range(4096))}, separators=(",", ":")).encode()
    parsed = parse_candidate(data)
    assert len(parsed["x"]) == 4096


def test_collection_4097_rejected() -> None:
    data = json.dumps({"x": list(range(4097))}, separators=(",", ":")).encode()
    assert failure(data) is NdebIssueCode.COLLECTION_CARDINALITY_EXCEEDED


def test_string_over_1mib_rejected() -> None:
    data = json.dumps({"x": "a" * 1_048_577}, separators=(",", ":")).encode()
    assert failure(data) is NdebIssueCode.STRING_SIZE_EXCEEDED


def test_bundle_size_exact_boundary_is_accepted_by_size_guard() -> None:
    data = b" " * (8_388_608 - 2) + b"{}"
    assert len(data) == 8_388_608
    assert parse_candidate(data) == {}


def test_string_exact_1mib_boundary_is_accepted() -> None:
    data = json.dumps({"x": "a" * 1_048_576}, separators=(",", ":")).encode()
    parsed = parse_candidate(data)
    assert len(parsed["x"].encode()) == 1_048_576


def _node_boundary_payload(extra: int = 0) -> bytes:
    payload: dict[str, list[int]] = {}
    for index in range(24):
        payload[f"k{index:02d}"] = [0] * 3997
    payload["k24"] = [0] * (4021 + extra)
    return json.dumps(payload, separators=(",", ":")).encode()


def test_total_json_nodes_exact_boundary_is_accepted() -> None:
    parsed = parse_candidate(_node_boundary_payload())
    assert len(parsed) == 25


def test_total_json_nodes_over_boundary_is_rejected() -> None:
    assert failure(_node_boundary_payload(1)) is NdebIssueCode.JSON_NODE_COUNT_EXCEEDED



def _nested(depth: int) -> bytes:
    return ("[" * depth + "0" + "]" * depth).encode()


def test_nesting_depth_exact_boundary_reaches_root_contract_check() -> None:
    with pytest.raises(NdebParseFailure) as caught:
        parse_candidate(_nested(32))
    assert caught.value.code is NdebIssueCode.SCHEMA_STRUCTURE_INVALID


def test_nesting_depth_over_boundary_is_rejected() -> None:
    assert failure(_nested(33)) is NdebIssueCode.NESTING_DEPTH_EXCEEDED


def test_canonical_bytes_over_limit_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(dumps=lambda value: b"x" * (MAX_CANONICAL_BYTES + 1))
    monkeypatch.setitem(sys.modules, "rfc8785", fake)
    result = validate_integrity(base_bundle())
    assert {issue.code for issue in result.issues} == {NdebIssueCode.CANONICAL_SIZE_EXCEEDED}
    assert result.computed_digest_sha256 is None



def test_canonical_bytes_exact_boundary_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = SimpleNamespace(dumps=lambda value: b"x" * MAX_CANONICAL_BYTES)
    monkeypatch.setitem(sys.modules, "rfc8785", fake)
    assert len(canonical_bytes(base_bundle())) == MAX_CANONICAL_BYTES
