from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.v2.domain.enterprise_quota import (
    ENTERPRISE_QUOTA_ACCOUNTING_VERSION,
    ENTERPRISE_QUOTA_CONTRACT_VERSION,
    ENTERPRISE_QUOTA_LIMIT_VERSION,
    EnterpriseQuotaAccountingEntry,
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
    quota_dimensions_for_operation,
)

NOW = datetime(
    2026,
    8,
    13,
    8,
    0,
    tzinfo=UTC,
)

WINDOW = EnterpriseQuotaWindow(
    window_start=NOW,
    window_end=NOW + timedelta(days=1),
)


def _entry(
    **updates: object,
) -> EnterpriseQuotaAccountingEntry:
    values: dict[str, object] = {
        "accounting_entry_id": "quota_entry_test",
        "accounting_group_id": "rewrite_test",
        "workspace_id": "workspace_test",
        "operation": EnterpriseQuotaOperation.SINGLE_REWRITE,
        "dimension": EnterpriseQuotaDimension.REWRITE_REQUESTS,
        "quantity": 1,
        "window": WINDOW,
        "occurred_at": NOW,
    }

    values.update(updates)

    return EnterpriseQuotaAccountingEntry(**values)


def test_quota_contract_versions_are_frozen() -> None:
    assert ENTERPRISE_QUOTA_CONTRACT_VERSION == "enterprise-quota-v1"
    assert ENTERPRISE_QUOTA_LIMIT_VERSION == "enterprise-quota-limit-v1"
    assert ENTERPRISE_QUOTA_ACCOUNTING_VERSION == "enterprise-quota-accounting-v1"


def test_quota_dimension_vocabulary_is_frozen() -> None:
    assert tuple(EnterpriseQuotaDimension) == (
        EnterpriseQuotaDimension.REWRITE_REQUESTS,
        EnterpriseQuotaDimension.INPUT_CHARACTERS,
        EnterpriseQuotaDimension.OUTPUT_CHARACTERS,
        EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS,
    )


def test_quota_operation_vocabulary_is_frozen() -> None:
    assert tuple(EnterpriseQuotaOperation) == (
        EnterpriseQuotaOperation.SINGLE_REWRITE,
        EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
        EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
    )


def test_single_rewrite_dimension_contract_is_frozen() -> None:
    assert quota_dimensions_for_operation(EnterpriseQuotaOperation.SINGLE_REWRITE) == frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.OUTPUT_CHARACTERS,
        }
    )


def test_multi_candidate_dimension_contract_is_frozen() -> None:
    assert quota_dimensions_for_operation(
        EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE
    ) == frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.OUTPUT_CHARACTERS,
            EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        }
    )


def test_long_document_dimension_contract_is_frozen() -> None:
    assert quota_dimensions_for_operation(
        EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE
    ) == frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.OUTPUT_CHARACTERS,
            EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS,
        }
    )


def test_quota_window_is_immutable_and_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EnterpriseQuotaWindow.model_validate(
            {
                **WINDOW.model_dump(),
                "unexpected": True,
            }
        )

    with pytest.raises(ValidationError):
        WINDOW.window_end = NOW  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name",
    (
        "window_start",
        "window_end",
    ),
)
def test_quota_window_requires_timezone_aware_bounds(
    field_name: str,
) -> None:
    values = {
        "window_start": NOW,
        "window_end": NOW + timedelta(days=1),
    }
    values[field_name] = datetime(
        2026,
        8,
        13,
        8,
        0,
    )

    with pytest.raises(
        ValidationError,
        match="must be timezone-aware",
    ):
        EnterpriseQuotaWindow(**values)


def test_quota_window_requires_positive_duration() -> None:
    with pytest.raises(
        ValidationError,
        match="window_end must be after window_start",
    ):
        EnterpriseQuotaWindow(
            window_start=NOW,
            window_end=NOW,
        )


def test_quota_window_is_half_open() -> None:
    assert WINDOW.contains(NOW)
    assert WINDOW.contains(NOW + timedelta(hours=12))
    assert not WINDOW.contains(NOW + timedelta(days=1))


def test_quota_window_contains_requires_aware_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="must be timezone-aware",
    ):
        WINDOW.contains(
            datetime(
                2026,
                8,
                13,
                9,
                0,
            )
        )


def test_workspace_limit_is_immutable_and_forbids_extra_fields() -> None:
    limit = EnterpriseWorkspaceQuotaLimit(
        quota_limit_id="limit_test",
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        window=WINDOW,
        limit=100,
    )

    with pytest.raises(ValidationError):
        EnterpriseWorkspaceQuotaLimit.model_validate(
            {
                **limit.model_dump(),
                "unexpected": True,
            }
        )

    with pytest.raises(ValidationError):
        limit.limit = 200  # type: ignore[misc]


def test_workspace_limit_can_be_zero() -> None:
    limit = EnterpriseWorkspaceQuotaLimit(
        quota_limit_id="limit_zero",
        workspace_id="workspace_test",
        dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
        window=WINDOW,
        limit=0,
    )

    assert limit.limit == 0


def test_workspace_limit_rejects_negative_integer() -> None:
    with pytest.raises(ValidationError):
        EnterpriseWorkspaceQuotaLimit(
            quota_limit_id="limit_negative",
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            window=WINDOW,
            limit=-1,
        )


def test_workspace_limit_rejects_fractional_quantity() -> None:
    with pytest.raises(ValidationError):
        EnterpriseWorkspaceQuotaLimit(
            quota_limit_id="limit_fractional",
            workspace_id="workspace_test",
            dimension=EnterpriseQuotaDimension.REWRITE_REQUESTS,
            window=WINDOW,
            limit=1.5,
        )


def test_accounting_entry_is_immutable_and_forbids_extra_fields() -> None:
    entry = _entry()

    with pytest.raises(ValidationError):
        EnterpriseQuotaAccountingEntry.model_validate(
            {
                **entry.model_dump(),
                "unexpected": True,
            }
        )

    with pytest.raises(ValidationError):
        entry.quantity = 2  # type: ignore[misc]


def test_accounting_quantity_can_be_zero() -> None:
    assert _entry(quantity=0).quantity == 0


def test_accounting_quantity_rejects_negative_integer() -> None:
    with pytest.raises(ValidationError):
        _entry(quantity=-1)


def test_accounting_quantity_rejects_fractional_value() -> None:
    with pytest.raises(ValidationError):
        _entry(quantity=1.5)


def test_accounting_timestamp_requires_timezone() -> None:
    with pytest.raises(
        ValidationError,
        match="occurred_at must be timezone-aware",
    ):
        _entry(
            occurred_at=datetime(
                2026,
                8,
                13,
                9,
                0,
            )
        )


def test_accounting_timestamp_must_be_inside_window() -> None:
    with pytest.raises(
        ValidationError,
        match="inside the accounting window",
    ):
        _entry(
            occurred_at=WINDOW.window_end,
        )


@pytest.mark.parametrize(
    "dimension",
    tuple(quota_dimensions_for_operation(EnterpriseQuotaOperation.SINGLE_REWRITE)),
)
def test_single_rewrite_accepts_only_supported_dimensions(
    dimension: EnterpriseQuotaDimension,
) -> None:
    entry = _entry(
        operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
        dimension=dimension,
    )

    assert entry.dimension is dimension


@pytest.mark.parametrize(
    "dimension",
    (
        EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS,
    ),
)
def test_single_rewrite_rejects_complex_dimensions(
    dimension: EnterpriseQuotaDimension,
) -> None:
    with pytest.raises(
        ValidationError,
        match="not valid for the operation",
    ):
        _entry(
            operation=EnterpriseQuotaOperation.SINGLE_REWRITE,
            dimension=dimension,
        )


@pytest.mark.parametrize(
    "dimension",
    tuple(quota_dimensions_for_operation(EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE)),
)
def test_multi_candidate_accepts_supported_dimensions(
    dimension: EnterpriseQuotaDimension,
) -> None:
    entry = _entry(
        operation=EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
        dimension=dimension,
    )

    assert entry.dimension is dimension


def test_multi_candidate_rejects_long_document_sections() -> None:
    with pytest.raises(
        ValidationError,
        match="not valid for the operation",
    ):
        _entry(
            operation=EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
            dimension=EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS,
        )


@pytest.mark.parametrize(
    "dimension",
    tuple(quota_dimensions_for_operation(EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE)),
)
def test_long_document_accepts_supported_dimensions(
    dimension: EnterpriseQuotaDimension,
) -> None:
    entry = _entry(
        operation=EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
        dimension=dimension,
    )

    assert entry.dimension is dimension


def test_long_document_rejects_candidate_dimension() -> None:
    with pytest.raises(
        ValidationError,
        match="not valid for the operation",
    ):
        _entry(
            operation=EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE,
            dimension=EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        )


def test_accounting_preserves_workspace_operation_and_group_identity() -> None:
    entry = _entry(
        accounting_entry_id="entry_123",
        accounting_group_id="rewrite_456",
        workspace_id="workspace_789",
        operation=EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE,
        dimension=EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        quantity=3,
    )

    assert entry.accounting_entry_id == "entry_123"
    assert entry.accounting_group_id == "rewrite_456"
    assert entry.workspace_id == "workspace_789"
    assert entry.operation is EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE
    assert entry.dimension is EnterpriseQuotaDimension.CANDIDATES_GENERATED
    assert entry.quantity == 3


def test_accounting_contract_contains_no_token_dimension() -> None:
    assert all("token" not in dimension.value for dimension in EnterpriseQuotaDimension)
