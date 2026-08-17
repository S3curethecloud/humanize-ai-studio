from __future__ import annotations

import logging
from typing import Protocol

from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceRecord,
)

logger = logging.getLogger(
    "humanize.v2.routing_eval_evidence_telemetry"
)


class RoutingEvalEvidenceTelemetry(Protocol):
    def record_routing_evidence(
        self,
        record: RoutingEvidenceRecord,
    ) -> None: ...

    def record_evaluation_evidence(
        self,
        record: EvaluationEvidenceRecord,
    ) -> None: ...


def record_routing_telemetry_best_effort(
    *,
    telemetry: RoutingEvalEvidenceTelemetry | None,
    record: RoutingEvidenceRecord,
) -> None:
    if telemetry is None:
        return

    try:
        telemetry.record_routing_evidence(record)
    except Exception:
        logger.exception(
            "routing_evidence_telemetry_recording_failed"
        )


def record_evaluation_telemetry_best_effort(
    *,
    telemetry: RoutingEvalEvidenceTelemetry | None,
    record: EvaluationEvidenceRecord,
) -> None:
    if telemetry is None:
        return

    try:
        telemetry.record_evaluation_evidence(record)
    except Exception:
        logger.exception(
            "evaluation_evidence_telemetry_recording_failed"
        )
