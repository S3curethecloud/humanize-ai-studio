from __future__ import annotations

import json

import pytest

from app.v3.ndeb.contracts import NdebIssueCode
from app.v3.ndeb.parser import NdebParseFailure, parse_candidate


def failure(data: bytes) -> NdebIssueCode:
    with pytest.raises(NdebParseFailure) as caught:
        parse_candidate(data)
    return caught.value.code


def nested(depth: int) -> bytes:
    return ("[" * depth + "0" + "]" * depth).encode()


def test_empty_is_malformed() -> None:
    assert failure(b"") is NdebIssueCode.JSON_MALFORMED


def test_invalid_utf8() -> None:
    assert failure(b"\xff") is NdebIssueCode.UTF8_INVALID


def test_bom_is_rejected() -> None:
    assert failure(b"\xef\xbb\xbf{}") is NdebIssueCode.UTF8_BOM_PROHIBITED


def test_duplicate_root_member() -> None:
    assert failure(b'{"a":1,"a":2}') is NdebIssueCode.JSON_DUPLICATE_MEMBER


def test_duplicate_nested_member() -> None:
    assert failure(b'{"x":{"a":1,"a":2}}') is NdebIssueCode.JSON_DUPLICATE_MEMBER


@pytest.mark.parametrize("token", [b"NaN", b"Infinity", b"-Infinity"])
def test_nonfinite_number(token: bytes) -> None:
    assert failure(b'{"x":' + token + b'}') is NdebIssueCode.JSON_NONFINITE_NUMBER


def test_depth_33_is_rejected() -> None:
    assert failure(nested(33)) is NdebIssueCode.NESTING_DEPTH_EXCEEDED


def test_depth_32_gets_past_nesting_guard() -> None:
    with pytest.raises(NdebParseFailure) as caught:
        parse_candidate(nested(32))
    assert caught.value.code is NdebIssueCode.SCHEMA_STRUCTURE_INVALID


def test_collection_cardinality_over_limit() -> None:
    data = json.dumps({"x": list(range(4097))}, separators=(",", ":")).encode()
    assert failure(data) is NdebIssueCode.COLLECTION_CARDINALITY_EXCEEDED


def test_depth_31_gets_past_nesting_guard() -> None:
    with pytest.raises(NdebParseFailure) as caught:
        parse_candidate(nested(31))
    assert caught.value.code is NdebIssueCode.SCHEMA_STRUCTURE_INVALID



def test_malformed_json_token_stream() -> None:
    assert failure(b'{"x":]') is NdebIssueCode.JSON_MALFORMED


def test_finite_syntax_exponent_overflow_is_nonfinite_error() -> None:
    assert failure(b'{"x":1e999}') is NdebIssueCode.JSON_NONFINITE_NUMBER


def test_bundle_size_exact_boundary() -> None:
    data = b" " * (8_388_608 - 2) + b"{}"
    assert len(data) == 8_388_608
    assert parse_candidate(data) == {}


def test_bundle_size_over_boundary() -> None:
    assert failure(b" " * 8_388_609) is NdebIssueCode.INPUT_TOO_LARGE


def test_mapping_cardinality_4096_boundary() -> None:
    inner = {f"k{index:04d}": index for index in range(4096)}
    data = json.dumps({"x": inner}, separators=(",", ":")).encode()
    parsed = parse_candidate(data)
    assert len(parsed["x"]) == 4096


def test_mapping_cardinality_4097_rejected() -> None:
    inner = {f"k{index:04d}": index for index in range(4097)}
    data = json.dumps({"x": inner}, separators=(",", ":")).encode()
    assert failure(data) is NdebIssueCode.COLLECTION_CARDINALITY_EXCEEDED


def test_sequence_cardinality_4096_boundary() -> None:
    data = json.dumps({"x": list(range(4096))}, separators=(",", ":")).encode()
    parsed = parse_candidate(data)
    assert len(parsed["x"]) == 4096


def test_string_exact_1mib_boundary() -> None:
    data = json.dumps({"x": "a" * 1_048_576}, separators=(",", ":")).encode()
    parsed = parse_candidate(data)
    assert len(parsed["x"].encode("utf-8")) == 1_048_576


def test_string_over_1mib_boundary() -> None:
    data = json.dumps({"x": "a" * 1_048_577}, separators=(",", ":")).encode()
    assert failure(data) is NdebIssueCode.STRING_SIZE_EXCEEDED


def _node_boundary_payload(extra: int = 0) -> bytes:
    payload: dict[str, list[int]] = {}
    for index in range(24):
        payload[f"k{index:02d}"] = [0] * 3997
    payload["k24"] = [0] * (4021 + extra)
    return json.dumps(payload, separators=(",", ":")).encode()


def test_total_json_nodes_100000_boundary() -> None:
    assert len(parse_candidate(_node_boundary_payload())) == 25


def test_total_json_nodes_100001_rejected() -> None:
    assert failure(_node_boundary_payload(1)) is NdebIssueCode.JSON_NODE_COUNT_EXCEEDED
