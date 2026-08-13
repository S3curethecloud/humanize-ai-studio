from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import (
    UTC,
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaDimension,
    EnterpriseQuotaWindow,
    EnterpriseWorkspaceQuotaLimit,
)
from app.v2.services.enterprise_quota_decision_service import (
    EnterpriseQuotaDecisionEvidence,
    EnterpriseQuotaDecisionOutcome,
    EnterpriseQuotaDecisionService,
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

SERVICE = EnterpriseQuotaDecisionService()


def _limit(
    *,
    quota_limit_id: str = "limit_test",
    workspace_id: str = "workspace_test",
    dimension: EnterpriseQuotaDimension = (EnterpriseQuotaDimension.REWRITE_REQUESTS),
    window: EnterpriseQuotaWindow = WINDOW,
    limit: int = 10,
) -> EnterpriseWorkspaceQuotaLimit:
    return EnterpriseWorkspaceQuotaLimit(
        quota_limit_id=quota_limit_id,
        workspace_id=workspace_id,
        dimension=dimension,
        window=window,
        limit=limit,
    )


def _evaluate(
    *,
    workspace_id: str = "workspace_test",
    dimension: EnterpriseQuotaDimension = (EnterpriseQuotaDimension.REWRITE_REQUESTS),
    window: EnterpriseQuotaWindow = WINDOW,
    limit: EnterpriseWorkspaceQuotaLimit | None = None,
    current_usage: int = 0,
    requested_quantity: int = 1,
) -> EnterpriseQuotaDecisionEvidence:
    return SERVICE.evaluate(
        workspace_id=workspace_id,
        dimension=dimension,
        window=window,
        limit=limit,
        current_usage=current_usage,
        requested_quantity=requested_quantity,
    )


def test_decision_outcome_vocabulary_is_frozen() -> None:
    assert tuple(EnterpriseQuotaDecisionOutcome) == (
        EnterpriseQuotaDecisionOutcome.ALLOW,
        (EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED),
        (EnterpriseQuotaDecisionOutcome.NO_LIMIT_CONFIGURED),
    )


def test_below_limit_is_allowed() -> None:
    decision = _evaluate(
        limit=_limit(limit=10),
        current_usage=4,
        requested_quantity=5,
    )

    assert decision.outcome is EnterpriseQuotaDecisionOutcome.ALLOW
    assert decision.allowed is True
    assert decision.projected_usage == 9


def test_exact_limit_boundary_is_allowed() -> None:
    decision = _evaluate(
        limit=_limit(limit=10),
        current_usage=6,
        requested_quantity=4,
    )

    assert decision.outcome is EnterpriseQuotaDecisionOutcome.ALLOW
    assert decision.allowed is True
    assert decision.projected_usage == 10


def test_over_limit_is_denied() -> None:
    decision = _evaluate(
        limit=_limit(limit=10),
        current_usage=7,
        requested_quantity=4,
    )

    assert decision.outcome is (EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED)
    assert decision.allowed is False
    assert decision.projected_usage == 11


def test_existing_usage_over_limit_remains_denied() -> None:
    decision = _evaluate(
        limit=_limit(limit=10),
        current_usage=11,
        requested_quantity=0,
    )

    assert decision.outcome is (EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED)
    assert decision.allowed is False
    assert decision.projected_usage == 11


def test_zero_limit_allows_zero_projected_usage() -> None:
    decision = _evaluate(
        limit=_limit(limit=0),
        current_usage=0,
        requested_quantity=0,
    )

    assert decision.outcome is EnterpriseQuotaDecisionOutcome.ALLOW
    assert decision.allowed is True
    assert decision.projected_usage == 0


def test_zero_limit_denies_positive_request() -> None:
    decision = _evaluate(
        limit=_limit(limit=0),
        current_usage=0,
        requested_quantity=1,
    )

    assert decision.outcome is (EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED)
    assert decision.allowed is False


def test_no_limit_configured_is_explicit_and_fail_closed() -> None:
    decision = _evaluate(
        limit=None,
        current_usage=7,
        requested_quantity=3,
    )

    assert decision.outcome is (EnterpriseQuotaDecisionOutcome.NO_LIMIT_CONFIGURED)
    assert decision.allowed is False
    assert decision.quota_limit_id is None
    assert decision.configured_limit is None
    assert decision.current_usage == 7
    assert decision.requested_quantity == 3
    assert decision.projected_usage == 10


def test_decision_evidence_contains_full_limit_context() -> None:
    limit = _limit(
        quota_limit_id="limit_requests_daily",
        limit=25,
    )

    decision = _evaluate(
        limit=limit,
        current_usage=12,
        requested_quantity=5,
    )

    assert decision.workspace_id == "workspace_test"
    assert decision.dimension is (EnterpriseQuotaDimension.REWRITE_REQUESTS)
    assert decision.window == WINDOW
    assert decision.quota_limit_id == "limit_requests_daily"
    assert decision.configured_limit == 25
    assert decision.current_usage == 12
    assert decision.requested_quantity == 5
    assert decision.projected_usage == 17
    assert decision.outcome is EnterpriseQuotaDecisionOutcome.ALLOW


def test_decision_evidence_is_immutable() -> None:
    decision = _evaluate(
        limit=_limit(),
    )

    with pytest.raises(FrozenInstanceError):
        decision.projected_usage = 999  # type: ignore[misc]


@pytest.mark.parametrize(
    (
        "current_usage",
        "requested_quantity",
        "expected_projected",
    ),
    (
        (0, 0, 0),
        (0, 5, 5),
        (8, 0, 8),
        (8, 5, 13),
        (1_000_000, 2_000_000, 3_000_000),
    ),
)
def test_projected_usage_is_exact_integer_addition(
    current_usage: int,
    requested_quantity: int,
    expected_projected: int,
) -> None:
    decision = _evaluate(
        limit=None,
        current_usage=current_usage,
        requested_quantity=requested_quantity,
    )

    assert decision.projected_usage == expected_projected
    assert isinstance(
        decision.projected_usage,
        int,
    )


@pytest.mark.parametrize(
    "current_usage",
    (-1, -100),
)
def test_negative_current_usage_is_rejected(
    current_usage: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="current_usage must be non-negative",
    ):
        _evaluate(
            limit=_limit(),
            current_usage=current_usage,
        )


@pytest.mark.parametrize(
    "requested_quantity",
    (-1, -100),
)
def test_negative_requested_quantity_is_rejected(
    requested_quantity: int,
) -> None:
    with pytest.raises(
        ValueError,
        match=("requested_quantity must be non-negative"),
    ):
        _evaluate(
            limit=_limit(),
            requested_quantity=(requested_quantity),
        )


@pytest.mark.parametrize(
    "current_usage",
    (1.5, True),
)
def test_non_integer_current_usage_is_rejected(
    current_usage: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="current_usage must be an integer",
    ):
        _evaluate(
            limit=_limit(),
            current_usage=current_usage,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "requested_quantity",
    (1.5, True),
)
def test_non_integer_requested_quantity_is_rejected(
    requested_quantity: object,
) -> None:
    with pytest.raises(
        TypeError,
        match=("requested_quantity must be an integer"),
    ):
        _evaluate(
            limit=_limit(),
            requested_quantity=requested_quantity,  # type: ignore[arg-type]
        )


def test_empty_workspace_id_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="workspace_id must not be empty",
    ):
        _evaluate(
            workspace_id="",
            limit=None,
        )


def test_limit_workspace_mismatch_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="workspace does not match",
    ):
        _evaluate(
            workspace_id="workspace_test",
            limit=_limit(
                workspace_id="workspace_other",
            ),
        )


def test_limit_dimension_mismatch_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="dimension does not match",
    ):
        _evaluate(
            dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
            limit=_limit(
                dimension=(EnterpriseQuotaDimension.INPUT_CHARACTERS),
            ),
        )


def test_limit_window_mismatch_is_rejected() -> None:
    other_window = EnterpriseQuotaWindow(
        window_start=WINDOW.window_end,
        window_end=(WINDOW.window_end + timedelta(days=1)),
    )

    with pytest.raises(
        ValueError,
        match="window does not match",
    ):
        _evaluate(
            window=WINDOW,
            limit=_limit(
                window=other_window,
            ),
        )


def test_equivalent_timezone_limit_window_matches() -> None:
    offset = timezone(timedelta(hours=-7))

    equivalent_window = EnterpriseQuotaWindow(
        window_start=(WINDOW.window_start.astimezone(offset)),
        window_end=(WINDOW.window_end.astimezone(offset)),
    )

    decision = _evaluate(
        window=equivalent_window,
        limit=_limit(
            window=WINDOW,
            limit=10,
        ),
        current_usage=4,
        requested_quantity=2,
    )

    assert decision.outcome is EnterpriseQuotaDecisionOutcome.ALLOW


@pytest.mark.parametrize(
    "dimension",
    tuple(EnterpriseQuotaDimension),
)
def test_all_frozen_dimensions_use_same_decision_invariant(
    dimension: EnterpriseQuotaDimension,
) -> None:
    limit = _limit(
        dimension=dimension,
        limit=100,
    )

    allowed = _evaluate(
        dimension=dimension,
        limit=limit,
        current_usage=75,
        requested_quantity=25,
    )
    denied = _evaluate(
        dimension=dimension,
        limit=limit,
        current_usage=75,
        requested_quantity=26,
    )

    assert allowed.outcome is EnterpriseQuotaDecisionOutcome.ALLOW
    assert denied.outcome is (EnterpriseQuotaDecisionOutcome.DENY_LIMIT_EXCEEDED)


def test_service_does_not_require_repository() -> None:
    service = EnterpriseQuotaDecisionService()

    decision = service.evaluate(
        workspace_id="workspace_test",
        dimension=(EnterpriseQuotaDimension.REWRITE_REQUESTS),
        window=WINDOW,
        limit=_limit(limit=10),
        current_usage=4,
        requested_quantity=5,
    )

    assert decision.outcome is EnterpriseQuotaDecisionOutcome.ALLOW


def test_decision_does_not_mutate_limit() -> None:
    limit = _limit(limit=10)

    before = limit.model_dump()

    _evaluate(
        limit=limit,
        current_usage=4,
        requested_quantity=5,
    )

    assert limit.model_dump() == before
