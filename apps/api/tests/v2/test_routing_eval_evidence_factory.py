from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.v2.config.persistence import (
    PersistenceBackend,
    V2PersistenceSettings,
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
from app.v2.repositories.routing_eval_evidence import (
    InMemoryEvaluationEvidenceRepository,
    InMemoryRoutingEvidenceRepository,
    SQLiteEvaluationEvidenceRepository,
    SQLiteRoutingEvidenceRepository,
)
from app.v2.services.routing_eval_evidence_factory import (
    ExternalRoutingEvalEvidencePersistenceUnavailableError,
    RoutingEvalEvidenceRepositoryBundle,
    build_routing_eval_evidence_repositories,
)


def _settings(
    *,
    backend: PersistenceBackend,
    sqlite_path: Path | None = None,
    database_url: str | None = None,
) -> V2PersistenceSettings:
    return V2PersistenceSettings(
        backend=backend,
        sqlite_path=sqlite_path,
        database_url=database_url,
    )


def _routing_record(
    evidence_id: str,
) -> RoutingEvidenceRecord:
    policy = RoutingPolicy(
        policy_id="policy-1",
        ordered_target_ids=("target-a",),
    )

    decision = RoutingDecision(
        policy_id="policy-1",
        status=RoutingDecisionStatus.SELECTED,
        reason=RoutingDecisionReason.PRIMARY_SELECTED,
        selected_target_id="target-a",
        candidates=(
            RoutingCandidate(
                target_id="target-a",
                eligible=True,
            ),
        ),
    )

    return RoutingEvidenceRecord(
        evidence_id=evidence_id,
        policy=policy,
        decision=decision,
        execution_outcome=(
            RoutingEvidenceExecutionOutcome.SUCCEEDED
        ),
        executed_target_id="target-a",
        attempts=(
            RoutingExecutionAttemptEvidence(
                target_id="target-a",
                outcome=(
                    RoutingEvidenceAttemptOutcome.SUCCEEDED
                ),
            ),
        ),
        observed_at=datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=UTC,
        ),
    )


def _evaluation_record(
    evidence_id: str,
    run_id: str,
) -> EvaluationEvidenceRecord:
    run = EvaluationRunRecord(
        identity=EvaluationRunIdentity(
            run_id=run_id,
            dataset=EvaluationDatasetIdentity(
                dataset_id="dataset-1",
                dataset_version="v1",
            ),
            target_id="target-a",
        ),
        outcome=EvaluationRunOutcome.SUCCEEDED,
        evaluated_case_count=1,
        failed_case_count=0,
        metric_results=(
            EvaluationMetricResult(
                metric=(
                    EvaluationMetric.PROVIDER_ERROR_RATE
                ),
                value=0.0,
            ),
        ),
    )

    return EvaluationEvidenceRecord(
        evidence_id=evidence_id,
        run=run,
        observed_at=datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=UTC,
        ),
    )


def test_memory_factory_returns_bundle() -> None:
    bundle = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.MEMORY,
        )
    )

    assert isinstance(
        bundle,
        RoutingEvalEvidenceRepositoryBundle,
    )
    assert isinstance(
        bundle.routing,
        InMemoryRoutingEvidenceRepository,
    )
    assert isinstance(
        bundle.evaluation,
        InMemoryEvaluationEvidenceRepository,
    )


def test_memory_repositories_are_independent() -> None:
    bundle = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.MEMORY,
        )
    )

    routing_record = _routing_record("shared-id")
    evaluation_record = _evaluation_record(
        "shared-id",
        "run-1",
    )

    bundle.routing.create(routing_record)
    bundle.evaluation.create(evaluation_record)

    assert (
        bundle.routing.get("shared-id")
        == routing_record
    )
    assert (
        bundle.evaluation.get("shared-id")
        == evaluation_record
    )


def test_memory_factory_calls_settings_validation() -> None:
    settings = _settings(
        backend=PersistenceBackend.SQLITE,
        sqlite_path=None,
    )

    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_SQLITE_PATH",
    ):
        build_routing_eval_evidence_repositories(
            settings
        )


def test_sqlite_factory_returns_expected_adapters(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "evidence.db"

    bundle = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.SQLITE,
            sqlite_path=database_path,
        )
    )

    assert isinstance(
        bundle.routing,
        SQLiteRoutingEvidenceRepository,
    )
    assert isinstance(
        bundle.evaluation,
        SQLiteEvaluationEvidenceRepository,
    )


def test_sqlite_routing_and_evaluation_share_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "shared-evidence.db"

    bundle = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.SQLITE,
            sqlite_path=database_path,
        )
    )

    routing_record = _routing_record("routing-1")
    evaluation_record = _evaluation_record(
        "evaluation-1",
        "run-1",
    )

    bundle.routing.create(routing_record)
    bundle.evaluation.create(evaluation_record)

    reopened = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.SQLITE,
            sqlite_path=database_path,
        )
    )

    assert (
        reopened.routing.get("routing-1")
        == routing_record
    )
    assert (
        reopened.evaluation.get("evaluation-1")
        == evaluation_record
    )


def test_sqlite_identity_namespaces_remain_separate(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "identity.db"

    bundle = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.SQLITE,
            sqlite_path=database_path,
        )
    )

    routing_record = _routing_record("shared-id")
    evaluation_record = _evaluation_record(
        "shared-id",
        "run-shared",
    )

    bundle.routing.create(routing_record)
    bundle.evaluation.create(evaluation_record)

    assert (
        bundle.routing.get("shared-id")
        == routing_record
    )
    assert (
        bundle.evaluation.get("shared-id")
        == evaluation_record
    )


def test_factory_instances_do_not_share_memory_state() -> None:
    first = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.MEMORY,
        )
    )
    second = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.MEMORY,
        )
    )

    first.routing.create(
        _routing_record("routing-1")
    )
    first.evaluation.create(
        _evaluation_record(
            "evaluation-1",
            "run-1",
        )
    )

    assert second.routing.get("routing-1") is None
    assert (
        second.evaluation.get("evaluation-1")
        is None
    )


def test_sqlite_factory_requires_path() -> None:
    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_SQLITE_PATH",
    ):
        build_routing_eval_evidence_repositories(
            _settings(
                backend=PersistenceBackend.SQLITE,
            )
        )


def test_external_backend_fails_closed() -> None:
    with pytest.raises(
        ExternalRoutingEvalEvidencePersistenceUnavailableError,
        match="no external evidence adapter",
    ):
        build_routing_eval_evidence_repositories(
            _settings(
                backend=PersistenceBackend.EXTERNAL,
                database_url=(
                    "postgresql://example.invalid/evidence"
                ),
            )
        )


def test_external_without_database_url_fails_validation_first() -> None:
    with pytest.raises(
        ValueError,
        match="HUMANIZE_V2_DATABASE_URL",
    ):
        build_routing_eval_evidence_repositories(
            _settings(
                backend=PersistenceBackend.EXTERNAL,
                database_url=None,
            )
        )


def test_bundle_is_frozen() -> None:
    bundle = build_routing_eval_evidence_repositories(
        _settings(
            backend=PersistenceBackend.MEMORY,
        )
    )

    with pytest.raises(
        AttributeError,
    ):
        bundle.routing = InMemoryRoutingEvidenceRepository()
