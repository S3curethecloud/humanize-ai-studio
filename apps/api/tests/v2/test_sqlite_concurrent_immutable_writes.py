from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

from app.v2.domain.eval_dataset import (
    EvaluationCaseInput,
    EvaluationDataset,
    EvaluationDatasetCase,
)
from app.v2.domain.eval_ops import (
    EvaluationDatasetIdentity,
    EvaluationMetric,
    EvaluationMetricResult,
    EvaluationRunIdentity,
    EvaluationRunOutcome,
    EvaluationRunRecord,
)
from app.v2.domain.provider_routing import (
    ModelIdentity,
    ProviderCapability,
    ProviderIdentity,
    ProviderModelCapabilities,
    ProviderModelTarget,
    RoutingCandidate,
    RoutingDecision,
    RoutingDecisionReason,
    RoutingDecisionStatus,
    RoutingPolicy,
)
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceAttemptOutcome,
    RoutingEvidenceExecutionOutcome,
    RoutingEvidenceRecord,
    RoutingExecutionAttemptEvidence,
)
from app.v2.repositories.eval_dataset import (
    SQLiteEvaluationDatasetRepository,
)
from app.v2.repositories.eval_run import (
    SQLiteEvaluationRunRepository,
)
from app.v2.repositories.provider_catalog import (
    SQLiteProviderCatalogRepository,
)
from app.v2.repositories.routing_eval_evidence import (
    SQLiteEvaluationEvidenceRepository,
    SQLiteRoutingEvidenceRepository,
)


def _target() -> ProviderModelTarget:
    return ProviderModelTarget(
        target_id="concurrent-target",
        provider=ProviderIdentity(
            provider_id="provider-a",
            display_name="Provider A",
        ),
        model=ModelIdentity(
            provider_id="provider-a",
            model_id="model-a",
        ),
        capabilities=ProviderModelCapabilities(
            capabilities=frozenset(
                {
                    ProviderCapability.REWRITE,
                }
            )
        ),
        enabled=True,
    )


def _dataset() -> EvaluationDataset:
    return EvaluationDataset(
        identity=EvaluationDatasetIdentity(
            dataset_id="concurrent-dataset",
            dataset_version="v1",
        ),
        cases=(
            EvaluationDatasetCase(
                case_id="case-001",
                input=EvaluationCaseInput(
                    text="Concurrent dataset source.",
                ),
            ),
        ),
    )


def _run() -> EvaluationRunRecord:
    return EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id="concurrent-run",
            dataset=EvaluationDatasetIdentity(
                dataset_id="concurrent-dataset",
                dataset_version="v1",
            ),
            target_id="concurrent-target",
        ),
        outcome=EvaluationRunOutcome.SUCCEEDED,
        evaluated_case_count=1,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=EvaluationMetric.NATURALNESS,
                value=0.95,
            ),
        ),
    )


def _routing_policy() -> RoutingPolicy:
    return RoutingPolicy(
        policy_id="concurrent-policy",
        ordered_target_ids=(
            "concurrent-target",
        ),
    )


def _routing_decision() -> RoutingDecision:
    return RoutingDecision(
        policy_id="concurrent-policy",
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="concurrent-target",
        candidates=(
            RoutingCandidate(
                target_id="concurrent-target",
                eligible=True,
            ),
        ),
    )


def _routing_evidence() -> RoutingEvidenceRecord:
    return RoutingEvidenceRecord(
        evidence_id="concurrent-routing-evidence",
        policy=_routing_policy(),
        decision=_routing_decision(),
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.SUCCEEDED
        ),
        executed_target_id="concurrent-target",
        attempts=(
            RoutingExecutionAttemptEvidence(
                target_id="concurrent-target",
                outcome=(
                    RoutingEvidenceAttemptOutcome.SUCCEEDED
                ),
            ),
        ),
        observed_at=datetime(
            2026,
            8,
            18,
            7,
            0,
            tzinfo=UTC,
        ),
    )


def _evaluation_evidence() -> EvaluationEvidenceRecord:
    return EvaluationEvidenceRecord(
        evidence_id="concurrent-evaluation-evidence",
        run=_run(),
        gate_result=None,
        observed_at=datetime(
            2026,
            8,
            18,
            7,
            1,
            tzinfo=UTC,
        ),
    )


def _race_identical_create(
    *,
    first_create: Callable[[], object],
    second_create: Callable[[], object],
) -> list[tuple[str, object]]:
    barrier = Barrier(2)

    def worker(
        create: Callable[[], object],
    ) -> tuple[str, object]:
        barrier.wait()

        try:
            return (
                "created",
                create(),
            )
        except ValueError as exc:
            return (
                "rejected",
                str(exc),
            )

    with ThreadPoolExecutor(
        max_workers=2,
    ) as executor:
        futures = (
            executor.submit(
                worker,
                first_create,
            ),
            executor.submit(
                worker,
                second_create,
            ),
        )

        return [
            future.result()
            for future in futures
        ]


def _assert_exactly_one_winner(
    outcomes: list[tuple[str, object]],
) -> None:
    assert sorted(
        outcome
        for outcome, _ in outcomes
    ) == [
        "created",
        "rejected",
    ]


def test_provider_catalog_concurrent_same_identity_has_one_winner(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "provider-catalog.db"
    )

    first = SQLiteProviderCatalogRepository(
        database_path=database,
    )
    second = SQLiteProviderCatalogRepository(
        database_path=database,
    )
    target = _target()

    outcomes = _race_identical_create(
        first_create=lambda: first.create(
            target
        ),
        second_create=lambda: second.create(
            target
        ),
    )

    _assert_exactly_one_winner(outcomes)

    reopened = SQLiteProviderCatalogRepository(
        database_path=database,
    )

    assert (
        reopened.get(
            target.target_id
        )
        == target
    )


def test_eval_dataset_concurrent_same_identity_has_one_winner(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "evaluation-dataset.db"
    )

    first = SQLiteEvaluationDatasetRepository(
        database_path=database,
    )
    second = SQLiteEvaluationDatasetRepository(
        database_path=database,
    )
    dataset = _dataset()

    outcomes = _race_identical_create(
        first_create=lambda: first.create(
            dataset
        ),
        second_create=lambda: second.create(
            dataset
        ),
    )

    _assert_exactly_one_winner(outcomes)

    reopened = SQLiteEvaluationDatasetRepository(
        database_path=database,
    )

    assert (
        reopened.get(
            dataset.identity
        )
        == dataset
    )


def test_eval_run_concurrent_same_identity_has_one_winner(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "evaluation-run.db"
    )

    first = SQLiteEvaluationRunRepository(
        database_path=database,
    )
    second = SQLiteEvaluationRunRepository(
        database_path=database,
    )
    run = _run()

    outcomes = _race_identical_create(
        first_create=lambda: first.create(
            run
        ),
        second_create=lambda: second.create(
            run
        ),
    )

    _assert_exactly_one_winner(outcomes)

    reopened = SQLiteEvaluationRunRepository(
        database_path=database,
    )

    assert (
        reopened.get(
            run.identity.run_id
        )
        == run
    )


def test_routing_evidence_concurrent_same_identity_has_one_winner(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "routing-evidence.db"
    )

    first = SQLiteRoutingEvidenceRepository(
        database_path=database,
    )
    second = SQLiteRoutingEvidenceRepository(
        database_path=database,
    )
    record = _routing_evidence()

    outcomes = _race_identical_create(
        first_create=lambda: first.create(
            record
        ),
        second_create=lambda: second.create(
            record
        ),
    )

    _assert_exactly_one_winner(outcomes)

    reopened = SQLiteRoutingEvidenceRepository(
        database_path=database,
    )

    assert (
        reopened.get(
            record.evidence_id
        )
        == record
    )


def test_evaluation_evidence_concurrent_same_identity_has_one_winner(
    tmp_path: Path,
) -> None:
    database = (
        tmp_path
        / "evaluation-evidence.db"
    )

    first = SQLiteEvaluationEvidenceRepository(
        database_path=database,
    )
    second = SQLiteEvaluationEvidenceRepository(
        database_path=database,
    )
    record = _evaluation_evidence()

    outcomes = _race_identical_create(
        first_create=lambda: first.create(
            record
        ),
        second_create=lambda: second.create(
            record
        ),
    )

    _assert_exactly_one_winner(outcomes)

    reopened = SQLiteEvaluationEvidenceRepository(
        database_path=database,
    )

    assert (
        reopened.get(
            record.evidence_id
        )
        == record
    )
