from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.v2.domain.eval_ops import (
    EvaluationMetric,
)


ENTERPRISE_WORKSPACE_EVALUATION_OPERATION_VERSION: Literal[
    "enterprise-workspace-evaluation-operation-v1"
] = "enterprise-workspace-evaluation-operation-v1"

ENTERPRISE_EVALUATION_EVIDENCE_BINDING_VERSION: Literal[
    "enterprise-workspace-evaluation-evidence-binding-v1"
] = "enterprise-workspace-evaluation-evidence-binding-v1"


class EnterpriseEvaluationEvidenceKind(StrEnum):
    RUN = "run"
    GATE = "gate"


class EnterpriseEvaluationEvidenceBindingStatus(StrEnum):
    RESERVED = "reserved"
    RECORDED = "recorded"


class EnterpriseEvaluationOperationStatus(StrEnum):
    OPEN = "open"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EnterpriseWorkspaceEvaluationEvidenceBinding(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    binding_version: Literal[
        "enterprise-workspace-evaluation-evidence-binding-v1"
    ] = ENTERPRISE_EVALUATION_EVIDENCE_BINDING_VERSION

    binding_id: str = Field(
        min_length=1,
        max_length=200,
    )
    operation_id: str = Field(
        min_length=1,
        max_length=200,
    )
    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )
    evidence_id: str = Field(
        min_length=1,
        max_length=200,
    )

    evidence_kind: EnterpriseEvaluationEvidenceKind

    run_id: str = Field(
        min_length=1,
        max_length=200,
    )
    gate_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    status: EnterpriseEvaluationEvidenceBindingStatus

    created_at: datetime
    recorded_at: datetime | None = None

    @field_validator(
        "binding_id",
        "operation_id",
        "workspace_id",
        "evidence_id",
        "run_id",
        mode="before",
    )
    @classmethod
    def normalize_required_identifier(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return value.strip()

    @field_validator(
        "gate_id",
        mode="before",
    )
    @classmethod
    def normalize_optional_identifier(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        return value.strip()

    @model_validator(mode="after")
    def require_binding_integrity(
        self,
    ) -> EnterpriseWorkspaceEvaluationEvidenceBinding:
        self._require_timestamp_integrity()
        self._require_kind_integrity()
        self._require_state_integrity()
        return self

    def _require_timestamp_integrity(
        self,
    ) -> None:
        if (
            self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise ValueError(
                "enterprise evaluation evidence binding "
                "created_at must be timezone-aware"
            )

        if self.recorded_at is None:
            return

        if (
            self.recorded_at.tzinfo is None
            or self.recorded_at.utcoffset() is None
        ):
            raise ValueError(
                "enterprise evaluation evidence binding "
                "recorded_at must be timezone-aware"
            )

        if self.recorded_at < self.created_at:
            raise ValueError(
                "enterprise evaluation evidence binding "
                "recorded_at must not precede created_at"
            )

    def _require_kind_integrity(
        self,
    ) -> None:
        if (
            self.evidence_kind
            is EnterpriseEvaluationEvidenceKind.RUN
        ):
            if self.gate_id is not None:
                raise ValueError(
                    "run evaluation evidence binding "
                    "cannot contain gate_id"
                )

            return

        if self.gate_id is None:
            raise ValueError(
                "gate evaluation evidence binding "
                "requires gate_id"
            )

    def _require_state_integrity(
        self,
    ) -> None:
        if (
            self.status
            is EnterpriseEvaluationEvidenceBindingStatus.RESERVED
        ):
            if self.recorded_at is not None:
                raise ValueError(
                    "reserved evaluation evidence binding "
                    "cannot contain recorded_at"
                )

            return

        if self.recorded_at is None:
            raise ValueError(
                "recorded evaluation evidence binding "
                "requires recorded_at"
            )


class EnterpriseWorkspaceEvaluationOperation(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    operation_version: Literal[
        "enterprise-workspace-evaluation-operation-v1"
    ] = ENTERPRISE_WORKSPACE_EVALUATION_OPERATION_VERSION

    operation_id: str = Field(
        min_length=1,
        max_length=200,
    )
    workspace_id: str = Field(
        min_length=1,
        max_length=200,
    )
    actor_user_id: str = Field(
        min_length=1,
        max_length=200,
    )

    run_id: str = Field(
        min_length=1,
        max_length=200,
    )
    dataset_id: str = Field(
        min_length=1,
        max_length=200,
    )
    dataset_version: str = Field(
        min_length=1,
        max_length=200,
    )
    target_id: str = Field(
        min_length=1,
        max_length=200,
    )

    requested_metrics: tuple[
        EvaluationMetric,
        ...,
    ] = Field(
        min_length=1,
    )

    evidence_bindings: tuple[
        EnterpriseWorkspaceEvaluationEvidenceBinding,
        ...,
    ] = ()

    status: EnterpriseEvaluationOperationStatus = (
        EnterpriseEvaluationOperationStatus.OPEN
    )

    created_at: datetime
    updated_at: datetime

    revision: int = Field(
        ge=1,
    )

    @field_validator(
        "operation_id",
        "workspace_id",
        "actor_user_id",
        "run_id",
        "dataset_id",
        "dataset_version",
        "target_id",
        mode="before",
    )
    @classmethod
    def normalize_required_identifier(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return value.strip()

    @model_validator(mode="after")
    def require_operation_integrity(
        self,
    ) -> EnterpriseWorkspaceEvaluationOperation:
        self._require_timestamp_integrity()
        self._require_metric_integrity()
        self._require_binding_integrity()
        self._require_status_integrity()
        return self

    def _require_timestamp_integrity(
        self,
    ) -> None:
        for field_name, value in (
            ("created_at", self.created_at),
            ("updated_at", self.updated_at),
        ):
            if (
                value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError(
                    "enterprise evaluation operation "
                    f"{field_name} must be timezone-aware"
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "enterprise evaluation operation "
                "updated_at must not precede created_at"
            )

    def _require_metric_integrity(
        self,
    ) -> None:
        if (
            len(set(self.requested_metrics))
            != len(self.requested_metrics)
        ):
            raise ValueError(
                "enterprise evaluation operation "
                "requested metrics must be unique"
            )

    def _require_binding_integrity(
        self,
    ) -> None:
        binding_ids = tuple(
            binding.binding_id
            for binding in self.evidence_bindings
        )

        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError(
                "enterprise evaluation operation "
                "binding IDs must be unique"
            )

        evidence_ids = tuple(
            binding.evidence_id
            for binding in self.evidence_bindings
        )

        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError(
                "enterprise evaluation operation "
                "evidence IDs must be unique"
            )

        run_bindings = []

        gate_ids: list[str] = []

        for binding in self.evidence_bindings:
            if binding.operation_id != self.operation_id:
                raise ValueError(
                    "enterprise evaluation evidence binding "
                    "operation identity must match operation"
                )

            if binding.workspace_id != self.workspace_id:
                raise ValueError(
                    "enterprise evaluation evidence binding "
                    "workspace identity must match operation"
                )

            if binding.run_id != self.run_id:
                raise ValueError(
                    "enterprise evaluation evidence binding "
                    "run identity must match operation"
                )

            if binding.created_at < self.created_at:
                raise ValueError(
                    "enterprise evaluation evidence binding "
                    "cannot precede operation creation"
                )

            if binding.created_at > self.updated_at:
                raise ValueError(
                    "enterprise evaluation evidence binding "
                    "cannot postdate operation update"
                )

            if (
                binding.recorded_at is not None
                and binding.recorded_at > self.updated_at
            ):
                raise ValueError(
                    "enterprise evaluation evidence binding "
                    "recorded_at cannot postdate operation update"
                )

            if (
                binding.evidence_kind
                is EnterpriseEvaluationEvidenceKind.RUN
            ):
                run_bindings.append(binding)
                continue

            if binding.gate_id is None:
                raise ValueError(
                    "gate evaluation evidence binding "
                    "requires gate_id"
                )

            gate_ids.append(
                binding.gate_id
            )

        if len(run_bindings) > 1:
            raise ValueError(
                "enterprise evaluation operation "
                "can contain at most one run evidence binding"
            )

        if len(set(gate_ids)) != len(gate_ids):
            raise ValueError(
                "enterprise evaluation operation "
                "gate evidence bindings require distinct gate IDs"
            )

    def _require_status_integrity(
        self,
    ) -> None:
        if (
            self.status
            is not EnterpriseEvaluationOperationStatus.SUCCEEDED
        ):
            return

        run_bindings = tuple(
            binding
            for binding in self.evidence_bindings
            if (
                binding.evidence_kind
                is EnterpriseEvaluationEvidenceKind.RUN
            )
        )

        if (
            len(run_bindings) != 1
            or run_bindings[0].status
            is not EnterpriseEvaluationEvidenceBindingStatus.RECORDED
        ):
            raise ValueError(
                "successful enterprise evaluation operation "
                "requires one recorded run evidence binding"
            )

        if any(
            binding.status
            is not EnterpriseEvaluationEvidenceBindingStatus.RECORDED
            for binding in self.evidence_bindings
        ):
            raise ValueError(
                "successful enterprise evaluation operation "
                "requires all evidence bindings to be recorded"
            )
