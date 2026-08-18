from __future__ import annotations

from datetime import UTC, datetime

from app.core.settings import ProviderName, Settings
from app.domain.models import RewriteRequest
from app.v2.api.dependencies import V2Services
from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
)
from app.v2.config.provider_targets import (
    ProviderTargetDeclarationSettings,
)
from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationDataset,
    EvaluationDatasetCase,
)
from app.v2.domain.eval_execution import (
    EvaluationRunRequest,
)
from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationRunOutcome,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
    RoutingCandidateIneligibilityReason,
    RoutingDecisionStatus,
    RoutingPolicy,
    RoutingRequirement,
)
from app.v2.domain.routing_eval_evidence import (
    RoutingEvidenceExecutionOutcome,
)
from app.v2.services.governed_provider_routing_service import (
    ProviderRoutingNotExecutedResult,
)
from app.v2.services.provider_execution_factory import (
    DETERMINISTIC_MODEL_ID,
    DETERMINISTIC_PROVIDER_ID,
)

DISABLED_TARGET_ID = "disabled-deterministic-eval"


def _settings() -> Settings:
    return Settings(
        rewrite_provider=ProviderName.DETERMINISTIC,
        cloudflare_account_id=None,
        cloudflare_api_token=None,
        cloudflare_model="@cf/legacy/model",
        cloudflare_timeout_seconds=30.0,
        cloudflare_fallback_enabled=False,
    )


def _persistence() -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=PersistenceBackend.MEMORY,
        sqlite_path=None,
        database_url=None,
    )


def _disabled_target() -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id=DISABLED_TARGET_ID,
        provider=ProviderIdentity(
            provider_id=DETERMINISTIC_PROVIDER_ID,
            display_name="Disabled Deterministic Eval Target",
        ),
        model=ModelIdentity(
            provider_id=DETERMINISTIC_PROVIDER_ID,
            model_id=DETERMINISTIC_MODEL_ID,
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
        enabled=False,
    )


def _target_settings(
) -> ProviderTargetDeclarationSettings:
    return ProviderTargetDeclarationSettings(
        targets=(
            _disabled_target(),
        )
    )


def _dataset_identity() -> EvaluationDatasetIdentity:
    return EvaluationDatasetIdentity(
        dataset_id="v2-8-i2-disabled-target",
        dataset_version="v1",
    )


def _dataset() -> EvaluationDataset:
    return EvaluationDataset(
        identity=_dataset_identity(),
        cases=(
            EvaluationDatasetCase(
                case_id="disabled-target-case",
                input=EvaluationCaseInput(
                    text=(
                        "This evaluation deliberately measures "
                        "a disabled routing target."
                    ),
                ),
            ),
        ),
    )


def _observed_at(
    *,
    minute: int,
) -> datetime:
    return datetime(
        2026,
        8,
        18,
        5,
        minute,
        tzinfo=UTC,
    )


def test_disabled_target_is_eval_available_but_routing_ineligible(
) -> None:
    services = V2Services(
        persistence_settings=_persistence(),
        provider_settings=_settings(),
        provider_target_settings=_target_settings(),
    )

    target = services.provider_catalog.get(
        DISABLED_TARGET_ID
    )

    assert target == _disabled_target()
    assert target is not None
    assert target.enabled is False

    routing_result = (
        services.provider_routing.routing.route_and_execute(
            evidence_id="v2-8-i2-routing-evidence",
            policy=RoutingPolicy(
                policy_id="v2-8-i2-routing-policy",
                ordered_target_ids=(
                    DISABLED_TARGET_ID,
                ),
            ),
            requirement=RoutingRequirement(
                required_capabilities=frozenset(
                    {
                        ProviderCapability.REWRITE,
                    }
                )
            ),
            request=RewriteRequest(
                text=(
                    "Production routing must not execute "
                    "this disabled target."
                )
            ),
            observed_at=_observed_at(
                minute=1
            ),
        )
    )

    assert isinstance(
        routing_result,
        ProviderRoutingNotExecutedResult,
    )
    assert (
        routing_result.decision.status
        is RoutingDecisionStatus.NO_ELIGIBLE_TARGET
    )
    assert (
        routing_result.decision.selected_target_id
        is None
    )
    assert len(
        routing_result.decision.candidates
    ) == 1

    candidate = routing_result.decision.candidates[0]

    assert candidate.target_id == DISABLED_TARGET_ID
    assert candidate.eligible is False
    assert (
        RoutingCandidateIneligibilityReason.TARGET_DISABLED
        in candidate.ineligibility_reasons
    )

    assert (
        routing_result.evidence.execution_outcome
        is RoutingEvidenceExecutionOutcome.NOT_EXECUTED
    )
    assert (
        routing_result.evidence.executed_target_id
        is None
    )

    services.evaluation_ops_repositories.datasets.create(
        _dataset()
    )

    run = services.evaluation_ops.run_execution.execute(
        evidence_id="v2-8-i2-eval-evidence",
        request=EvaluationRunRequest(
            run_id="v2-8-i2-eval-run",
            dataset=_dataset_identity(),
            target_id=DISABLED_TARGET_ID,
            metrics=(
                EvaluationMetric.PROVIDER_ERROR_RATE,
            ),
        ),
        observed_at=_observed_at(
            minute=2
        ),
    )

    assert (
        run.identity.target_id
        == DISABLED_TARGET_ID
    )
    assert (
        run.outcome
        is EvaluationRunOutcome.SUCCEEDED
    )
    assert run.evaluated_case_count == 1
    assert run.failed_case_count == 0

    eval_evidence = (
        services.evaluation_evidence_query.get(
            evidence_id="v2-8-i2-eval-evidence"
        )
    )

    assert (
        eval_evidence.run.identity.target_id
        == DISABLED_TARGET_ID
    )
    assert (
        eval_evidence.run.outcome
        is EvaluationRunOutcome.SUCCEEDED
    )

    routing_evidence = (
        services.routing_evidence_query.get(
            evidence_id="v2-8-i2-routing-evidence"
        )
    )

    assert (
        routing_evidence.execution_outcome
        is RoutingEvidenceExecutionOutcome.NOT_EXECUTED
    )
    assert routing_evidence.executed_target_id is None
