from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.v2.domain.eval_ops import (
    EvaluationGateResult,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.domain.provider_routing import (
    RoutingDecision,
    RoutingDecisionStatus,
    RoutingFailureCategory,
    RoutingPolicy,
)

ROUTING_EVAL_EVIDENCE_VERSION: Literal[
    "routing-eval-evidence-v1"
] = "routing-eval-evidence-v1"


class RoutingEvidenceExecutionOutcome(StrEnum):
    NOT_EXECUTED = "not_executed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RoutingEvidenceAttemptOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    PROVIDER_ERROR = "provider_error"


class RoutingExecutionAttemptEvidence(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    evidence_version: Literal[
        "routing-eval-evidence-v1"
    ] = ROUTING_EVAL_EVIDENCE_VERSION

    target_id: str = Field(
        min_length=1,
        max_length=200,
    )
    outcome: RoutingEvidenceAttemptOutcome
    failure_category: RoutingFailureCategory | None = None

    @model_validator(mode="after")
    def require_attempt_integrity(
        self,
    ) -> RoutingExecutionAttemptEvidence:
        if (
            self.outcome
            is RoutingEvidenceAttemptOutcome.SUCCEEDED
        ):
            if self.failure_category is not None:
                raise ValueError(
                    "successful routing execution attempt "
                    "cannot contain failure_category"
                )

            return self

        if self.failure_category is None:
            raise ValueError(
                "provider-error routing execution attempt "
                "requires failure_category"
            )

        return self


class RoutingEvidenceRecord(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    evidence_version: Literal[
        "routing-eval-evidence-v1"
    ] = ROUTING_EVAL_EVIDENCE_VERSION

    evidence_id: str = Field(
        min_length=1,
        max_length=200,
    )
    policy: RoutingPolicy
    decision: RoutingDecision
    execution_outcome: RoutingEvidenceExecutionOutcome
    executed_target_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    execution_fallback_used: bool = False
    attempts: tuple[
        RoutingExecutionAttemptEvidence,
        ...,
    ] = ()
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def require_routing_evidence_integrity(
        self,
    ) -> RoutingEvidenceRecord:
        self._require_timestamp()
        self._require_policy_decision_integrity()

        if (
            self.decision.status
            is RoutingDecisionStatus.NO_ELIGIBLE_TARGET
        ):
            self._require_no_execution_for_unselected_decision()
            return self

        self._require_selected_execution_integrity()
        return self

    def _require_timestamp(
        self,
    ) -> None:
        if (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError(
                "routing evidence timestamp "
                "must be timezone-aware"
            )

    def _require_policy_decision_integrity(
        self,
    ) -> None:
        if self.decision.policy_id != self.policy.policy_id:
            raise ValueError(
                "routing evidence decision policy identity "
                "must match routing policy"
            )

        decision_target_ids = tuple(
            candidate.target_id
            for candidate in self.decision.candidates
        )

        if (
            decision_target_ids
            != self.policy.ordered_target_ids
        ):
            raise ValueError(
                "routing evidence decision candidate order "
                "must match routing policy target order"
            )

    def _require_no_execution_for_unselected_decision(
        self,
    ) -> None:
        if (
            self.execution_outcome
            is not RoutingEvidenceExecutionOutcome.NOT_EXECUTED
        ):
            raise ValueError(
                "no-eligible-target routing evidence "
                "cannot contain an execution outcome"
            )

        if self.executed_target_id is not None:
            raise ValueError(
                "no-eligible-target routing evidence "
                "cannot contain executed_target_id"
            )

        if self.attempts:
            raise ValueError(
                "no-eligible-target routing evidence "
                "cannot contain execution attempts"
            )

        if self.execution_fallback_used:
            raise ValueError(
                "no-eligible-target routing evidence "
                "cannot report execution fallback"
            )

    def _require_selected_execution_integrity(
        self,
    ) -> None:
        selected_target_id = self.decision.selected_target_id

        if selected_target_id is None:
            raise ValueError(
                "selected routing evidence requires "
                "selected_target_id"
            )

        if (
            self.execution_outcome
            is RoutingEvidenceExecutionOutcome.NOT_EXECUTED
        ):
            if self.executed_target_id is not None:
                raise ValueError(
                    "not-executed routing evidence cannot "
                    "contain executed_target_id"
                )

            if self.attempts:
                raise ValueError(
                    "not-executed routing evidence cannot "
                    "contain execution attempts"
                )

            if self.execution_fallback_used:
                raise ValueError(
                    "not-executed routing evidence cannot "
                    "report execution fallback"
                )

            return

        if not self.attempts:
            raise ValueError(
                "executed routing evidence requires "
                "at least one execution attempt"
            )

        eligible_execution_target_ids = tuple(
            candidate.target_id
            for candidate in self.decision.candidates
            if candidate.eligible
        )

        try:
            selected_index = (
                eligible_execution_target_ids.index(
                    selected_target_id
                )
            )
        except ValueError as exc:
            raise ValueError(
                "selected routing target must be an "
                "eligible execution candidate"
            ) from exc

        eligible_execution_target_ids = (
            eligible_execution_target_ids[
                selected_index:
            ]
        )

        attempt_target_ids = tuple(
            attempt.target_id
            for attempt in self.attempts
        )

        expected_attempt_target_ids = (
            eligible_execution_target_ids[
                : len(attempt_target_ids)
            ]
        )

        if (
            attempt_target_ids
            != expected_attempt_target_ids
        ):
            raise ValueError(
                "routing evidence execution attempts must "
                "follow eligible routing targets in order"
            )

        if attempt_target_ids[0] != selected_target_id:
            raise ValueError(
                "routing evidence first execution attempt "
                "must be the selected routing target"
            )

        expected_fallback_used = len(self.attempts) > 1

        if (
            self.execution_fallback_used
            is not expected_fallback_used
        ):
            raise ValueError(
                "routing evidence execution_fallback_used "
                "must match actual execution attempts"
            )

        if (
            self.execution_outcome
            is RoutingEvidenceExecutionOutcome.SUCCEEDED
        ):
            self._require_successful_execution()
            return

        self._require_failed_execution()

    def _require_successful_execution(
        self,
    ) -> None:
        final_attempt = self.attempts[-1]

        if (
            final_attempt.outcome
            is not RoutingEvidenceAttemptOutcome.SUCCEEDED
        ):
            raise ValueError(
                "successful routing evidence requires "
                "a successful final execution attempt"
            )

        if any(
            attempt.outcome
            is not RoutingEvidenceAttemptOutcome.PROVIDER_ERROR
            for attempt in self.attempts[:-1]
        ):
            raise ValueError(
                "routing evidence attempts before success "
                "must be provider errors"
            )

        if (
            self.executed_target_id
            != final_attempt.target_id
        ):
            raise ValueError(
                "successful routing evidence executed target "
                "must match the successful final attempt"
            )

    def _require_failed_execution(
        self,
    ) -> None:
        if self.executed_target_id is not None:
            raise ValueError(
                "failed routing execution evidence cannot "
                "contain executed_target_id"
            )

        if any(
            attempt.outcome
            is not RoutingEvidenceAttemptOutcome.PROVIDER_ERROR
            for attempt in self.attempts
        ):
            raise ValueError(
                "failed routing execution evidence requires "
                "provider-error attempts only"
            )


class EvaluationEvidenceRecord(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    evidence_version: Literal[
        "routing-eval-evidence-v1"
    ] = ROUTING_EVAL_EVIDENCE_VERSION

    evidence_id: str = Field(
        min_length=1,
        max_length=200,
    )
    run: EvaluationRunRecord
    gate_result: EvaluationGateResult | None = None
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @model_validator(mode="after")
    def require_evaluation_evidence_integrity(
        self,
    ) -> EvaluationEvidenceRecord:
        if (
            self.observed_at.tzinfo is None
            or self.observed_at.utcoffset() is None
        ):
            raise ValueError(
                "evaluation evidence timestamp "
                "must be timezone-aware"
            )

        if self.gate_result is None:
            return self

        if (
            self.run.outcome
            is not EvaluationRunOutcome.SUCCEEDED
        ):
            raise ValueError(
                "evaluation gate evidence requires "
                "a successful evaluation run"
            )

        if (
            self.gate_result.run_id
            != self.run.identity.run_id
        ):
            raise ValueError(
                "evaluation gate result run identity "
                "must match evidence run"
            )

        run_result_by_metric = {
            result.metric: result
            for result in self.run.metric_results
        }

        for gate_metric_result in (
            self.gate_result.metric_results
        ):
            run_metric_result = (
                run_result_by_metric.get(
                    gate_metric_result.metric
                )
            )

            if run_metric_result is None:
                raise ValueError(
                    "evaluation gate evidence metric "
                    "must exist in evaluation run"
                )

            if (
                run_metric_result.value
                != gate_metric_result.value
            ):
                raise ValueError(
                    "evaluation gate evidence metric value "
                    "must match evaluation run metric value"
                )

        return self
