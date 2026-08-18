from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from app.v2.domain.enterprise_quota import (
    EnterpriseQuotaAccountingEntry,
    EnterpriseQuotaDimension,
    EnterpriseQuotaOperation,
    EnterpriseQuotaWindow,
)
from app.v2.repositories.enterprise_quota import (
    EnterpriseQuotaAccountingRepository,
)
from app.v2.repositories.enterprise_quota_limits import (
    EnterpriseQuotaLimitRepository,
)
from app.v2.services.enterprise_quota_decision_service import (
    EnterpriseQuotaDecisionEvidence,
    EnterpriseQuotaDecisionService,
)

_PRE_EXECUTION_DIMENSIONS: dict[
    EnterpriseQuotaOperation,
    frozenset[EnterpriseQuotaDimension],
] = {
    EnterpriseQuotaOperation.SINGLE_REWRITE: frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
        }
    ),
    EnterpriseQuotaOperation.MULTI_CANDIDATE_REWRITE: frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.CANDIDATES_GENERATED,
        }
    ),
    EnterpriseQuotaOperation.LONG_DOCUMENT_REWRITE: frozenset(
        {
            EnterpriseQuotaDimension.REWRITE_REQUESTS,
            EnterpriseQuotaDimension.INPUT_CHARACTERS,
            EnterpriseQuotaDimension.LONG_DOCUMENT_SECTIONS,
        }
    ),
}


@dataclass(
    frozen=True,
    slots=True,
)
class EnterpriseQuotaEnforcementResult:
    consumed: bool
    workspace_id: str
    operation: EnterpriseQuotaOperation
    accounting_group_id: str
    window: EnterpriseQuotaWindow
    decisions: tuple[
        EnterpriseQuotaDecisionEvidence,
        ...,
    ]

    @property
    def allowed(self) -> bool:
        return self.consumed


class EnterpriseQuotaEnforcementService:
    def __init__(
        self,
        *,
        accounting: EnterpriseQuotaAccountingRepository,
        limits: EnterpriseQuotaLimitRepository,
        decision_service: EnterpriseQuotaDecisionService,
    ) -> None:
        self._accounting = accounting
        self._limits = limits
        self._decision_service = decision_service

    def enforce(
        self,
        *,
        workspace_id: str,
        operation: EnterpriseQuotaOperation,
        window: EnterpriseQuotaWindow,
        accounting_group_id: str,
        requested_quantities: Mapping[
            EnterpriseQuotaDimension,
            int,
        ],
        occurred_at: datetime,
    ) -> EnterpriseQuotaEnforcementResult:
        _require_workspace_id(workspace_id)
        _require_accounting_group_id(accounting_group_id)

        ordered_quantities = _validate_and_order_requested_quantities(
            operation=operation,
            requested_quantities=requested_quantities,
        )

        entries = tuple(
            EnterpriseQuotaAccountingEntry(
                accounting_entry_id=_accounting_entry_id(
                    accounting_group_id=accounting_group_id,
                    dimension=dimension,
                ),
                accounting_group_id=accounting_group_id,
                workspace_id=workspace_id,
                operation=operation,
                dimension=dimension,
                quantity=quantity,
                window=window,
                occurred_at=occurred_at,
            )
            for dimension, quantity in ordered_quantities
        )

        resolved_limits = tuple(
            limit
            for dimension, _quantity in ordered_quantities
            if (
                limit := self._limits.resolve_exact(
                    workspace_id=workspace_id,
                    dimension=dimension,
                    window=window,
                )
            )
            is not None
        )

        atomic_result = self._accounting.check_and_consume_group(
            entries=entries,
            limits=resolved_limits,
            decision_service=self._decision_service,
        )

        return EnterpriseQuotaEnforcementResult(
            consumed=atomic_result.consumed,
            workspace_id=workspace_id,
            operation=operation,
            accounting_group_id=accounting_group_id,
            window=window,
            decisions=atomic_result.decisions,
        )


def pre_execution_dimensions_for_operation(
    operation: EnterpriseQuotaOperation,
) -> frozenset[EnterpriseQuotaDimension]:
    return _PRE_EXECUTION_DIMENSIONS[operation]


def _validate_and_order_requested_quantities(
    *,
    operation: EnterpriseQuotaOperation,
    requested_quantities: Mapping[
        EnterpriseQuotaDimension,
        int,
    ],
) -> tuple[
    tuple[
        EnterpriseQuotaDimension,
        int,
    ],
    ...,
]:
    required_dimensions = _PRE_EXECUTION_DIMENSIONS[operation]
    provided_dimensions = frozenset(requested_quantities)

    if provided_dimensions != required_dimensions:
        missing = sorted(
            
                dimension.value
                for dimension in required_dimensions - provided_dimensions
            
        )
        unexpected = sorted(
            
                dimension.value
                for dimension in provided_dimensions - required_dimensions
            
        )

        raise ValueError(
            "enterprise quota enforcement quantities must exactly match "
            f"pre-execution dimensions; missing={missing}; "
            f"unexpected={unexpected}"
        )

    ordered: list[
        tuple[
            EnterpriseQuotaDimension,
            int,
        ]
    ] = []

    for dimension in sorted(
        required_dimensions,
        key=lambda value: value.value,
    ):
        quantity = requested_quantities[dimension]

        if not isinstance(quantity, int) or isinstance(quantity, bool):
            raise TypeError(
                "enterprise quota enforcement quantity must be an integer"
            )

        if quantity < 0:
            raise ValueError(
                "enterprise quota enforcement quantity must be non-negative"
            )

        ordered.append(
            (
                dimension,
                quantity,
            )
        )

    return tuple(ordered)


def _accounting_entry_id(
    *,
    accounting_group_id: str,
    dimension: EnterpriseQuotaDimension,
) -> str:
    digest = sha256(
        (
            f"enterprise-quota-accounting-entry-v1:"
            f"{accounting_group_id}:"
            f"{dimension.value}"
        ).encode()
    ).hexdigest()

    return f"quota_entry_{digest}"


def _require_workspace_id(
    workspace_id: str,
) -> None:
    if not workspace_id:
        raise ValueError(
            "enterprise quota enforcement workspace_id must not be empty"
        )


def _require_accounting_group_id(
    accounting_group_id: str,
) -> None:
    if not accounting_group_id:
        raise ValueError(
            "enterprise quota enforcement accounting_group_id must not be empty"
        )
