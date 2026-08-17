from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from threading import Lock

from app.domain.models import RewriteResponse
from app.v2.domain.routing_eval_evidence import (
    EvaluationEvidenceRecord,
    RoutingEvidenceRecord,
)


@dataclass(frozen=True)
class RequestMetricKey:
    method: str
    route: str
    status: int


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._request_counts: Counter[RequestMetricKey] = Counter()
        self._request_duration_sum: defaultdict[
            tuple[str, str],
            float,
        ] = defaultdict(float)
        self._request_duration_count: Counter[tuple[str, str]] = Counter()
        self._rewrite_decisions: Counter[str] = Counter()
        self._provider_executions: Counter[str] = Counter()
        self._fallback_outcomes: Counter[str] = Counter()

        self._v2_routing_decisions: Counter[
            tuple[str, str]
        ] = Counter()
        self._v2_routing_executions: Counter[
            tuple[str, str]
        ] = Counter()
        self._v2_routing_attempts: Counter[
            tuple[str, str]
        ] = Counter()

        self._v2_eval_runs: Counter[str] = Counter()
        self._v2_eval_cases: Counter[str] = Counter()
        self._v2_eval_gate_decisions: Counter[str] = Counter()
        self._v2_eval_metric_value_sum: defaultdict[
            str,
            float,
        ] = defaultdict(float)
        self._v2_eval_metric_value_count: Counter[
            str
        ] = Counter()

    def record_request(
        self,
        *,
        method: str,
        route: str,
        status: int,
        duration_seconds: float,
    ) -> None:
        request_key = RequestMetricKey(
            method=method,
            route=route,
            status=status,
        )
        duration_key = (method, route)

        with self._lock:
            self._request_counts[request_key] += 1
            self._request_duration_sum[duration_key] += duration_seconds
            self._request_duration_count[duration_key] += 1

    def record_rewrite(
        self,
        response: RewriteResponse,
    ) -> None:
        decision = response.rewrite_necessity.decision
        provider = response.provider_execution.actual_provider_name
        fallback = "true" if response.provider_execution.fallback_used else "false"

        with self._lock:
            self._rewrite_decisions[decision] += 1
            self._provider_executions[provider] += 1
            self._fallback_outcomes[fallback] += 1

    def record_routing_evidence(
        self,
        record: RoutingEvidenceRecord,
    ) -> None:
        decision_key = (
            record.decision.status.value,
            record.decision.reason.value,
        )
        execution_key = (
            record.execution_outcome.value,
            (
                "true"
                if record.execution_fallback_used
                else "false"
            ),
        )

        with self._lock:
            self._v2_routing_decisions[decision_key] += 1
            self._v2_routing_executions[execution_key] += 1

            for attempt in record.attempts:
                failure_category = (
                    attempt.failure_category.value
                    if attempt.failure_category is not None
                    else "none"
                )

                self._v2_routing_attempts[
                    (
                        attempt.outcome.value,
                        failure_category,
                    )
                ] += 1

    def record_evaluation_evidence(
        self,
        record: EvaluationEvidenceRecord,
    ) -> None:
        run = record.run

        with self._lock:
            self._v2_eval_runs[run.outcome.value] += 1
            self._v2_eval_cases["evaluated"] += (
                run.evaluated_case_count
            )
            self._v2_eval_cases["failed"] += (
                run.failed_case_count
            )

            for result in run.metric_results:
                metric = result.metric.value

                self._v2_eval_metric_value_sum[
                    metric
                ] += result.value
                self._v2_eval_metric_value_count[
                    metric
                ] += 1

            if record.gate_result is not None:
                self._v2_eval_gate_decisions[
                    record.gate_result.decision.value
                ] += 1

    def render_prometheus(self) -> str:
        with self._lock:
            request_counts = dict(self._request_counts)
            duration_sums = dict(self._request_duration_sum)
            duration_counts = dict(self._request_duration_count)
            rewrite_decisions = dict(self._rewrite_decisions)
            provider_executions = dict(self._provider_executions)
            fallback_outcomes = dict(self._fallback_outcomes)

            v2_routing_decisions = dict(
                self._v2_routing_decisions
            )
            v2_routing_executions = dict(
                self._v2_routing_executions
            )
            v2_routing_attempts = dict(
                self._v2_routing_attempts
            )
            v2_eval_runs = dict(self._v2_eval_runs)
            v2_eval_cases = dict(self._v2_eval_cases)
            v2_eval_gate_decisions = dict(
                self._v2_eval_gate_decisions
            )
            v2_eval_metric_value_sum = dict(
                self._v2_eval_metric_value_sum
            )
            v2_eval_metric_value_count = dict(
                self._v2_eval_metric_value_count
            )

        lines = [
            "# HELP humanize_http_requests_total Total HTTP requests.",
            "# TYPE humanize_http_requests_total counter",
        ]

        for key, value in sorted(
            request_counts.items(),
            key=lambda item: (
                item[0].route,
                item[0].method,
                item[0].status,
            ),
        ):
            lines.append(
                "humanize_http_requests_total"
                f'{{method="{_escape(key.method)}",'
                f'route="{_escape(key.route)}",'
                f'status="{key.status}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_http_request_duration_seconds HTTP request duration in seconds.",
                "# TYPE humanize_http_request_duration_seconds summary",
            ]
        )

        duration_keys = sorted(set(duration_sums) | set(duration_counts))

        for method, route in duration_keys:
            labels = f'method="{_escape(method)}",route="{_escape(route)}"'
            lines.append(
                "humanize_http_request_duration_seconds_sum"
                f"{{{labels}}} "
                f"{duration_sums.get((method, route), 0.0):.9f}"
            )
            lines.append(
                "humanize_http_request_duration_seconds_count"
                f"{{{labels}}} "
                f"{duration_counts.get((method, route), 0)}"
            )

        lines.extend(
            [
                "# HELP humanize_rewrite_decisions_total Rewrite routing decisions.",
                "# TYPE humanize_rewrite_decisions_total counter",
            ]
        )

        for decision, value in sorted(rewrite_decisions.items()):
            lines.append(
                f'humanize_rewrite_decisions_total{{decision="{_escape(decision)}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_provider_executions_total Actual rewrite-provider executions.",
                "# TYPE humanize_provider_executions_total counter",
            ]
        )

        for provider, value in sorted(provider_executions.items()):
            lines.append(
                f'humanize_provider_executions_total{{provider="{_escape(provider)}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_rewrite_fallback_total "
                "Rewrite outcomes grouped by fallback usage.",
                "# TYPE humanize_rewrite_fallback_total counter",
            ]
        )

        for used, value in sorted(fallback_outcomes.items()):
            lines.append(
                "humanize_rewrite_fallback_total"
                f'{{used="{used}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_v2_routing_decisions_total "
                "V2 provider-routing decisions.",
                "# TYPE humanize_v2_routing_decisions_total counter",
            ]
        )

        for (
            decision_status,
            reason,
        ), value in sorted(v2_routing_decisions.items()):
            lines.append(
                "humanize_v2_routing_decisions_total"
                f'{{status="{_escape(decision_status)}",'
                f'reason="{_escape(reason)}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_v2_routing_executions_total "
                "V2 provider-routing execution outcomes.",
                "# TYPE humanize_v2_routing_executions_total counter",
            ]
        )

        for (
            outcome,
            fallback_used,
        ), value in sorted(v2_routing_executions.items()):
            lines.append(
                "humanize_v2_routing_executions_total"
                f'{{outcome="{_escape(outcome)}",'
                f'fallback_used="{fallback_used}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_v2_routing_attempts_total "
                "V2 provider-routing execution attempts.",
                "# TYPE humanize_v2_routing_attempts_total counter",
            ]
        )

        for (
            outcome,
            failure_category,
        ), value in sorted(v2_routing_attempts.items()):
            lines.append(
                "humanize_v2_routing_attempts_total"
                f'{{outcome="{_escape(outcome)}",'
                "failure_category="
                f'"{_escape(failure_category)}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_v2_eval_runs_total "
                "V2 EvalOps runs by terminal outcome.",
                "# TYPE humanize_v2_eval_runs_total counter",
            ]
        )

        for outcome, value in sorted(v2_eval_runs.items()):
            lines.append(
                "humanize_v2_eval_runs_total"
                f'{{outcome="{_escape(outcome)}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_v2_eval_cases_total "
                "V2 EvalOps evaluated and failed case counts.",
                "# TYPE humanize_v2_eval_cases_total counter",
            ]
        )

        for outcome, value in sorted(v2_eval_cases.items()):
            lines.append(
                "humanize_v2_eval_cases_total"
                f'{{outcome="{_escape(outcome)}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_v2_eval_gate_decisions_total "
                "V2 EvalOps quality-gate decisions.",
                "# TYPE humanize_v2_eval_gate_decisions_total counter",
            ]
        )

        for decision, value in sorted(
            v2_eval_gate_decisions.items()
        ):
            lines.append(
                "humanize_v2_eval_gate_decisions_total"
                f'{{decision="{_escape(decision)}"}} {value}'
            )

        lines.extend(
            [
                "# HELP humanize_v2_eval_metric_value "
                "Aggregate values produced by V2 EvalOps metrics.",
                "# TYPE humanize_v2_eval_metric_value summary",
            ]
        )

        metric_names = sorted(
            set(v2_eval_metric_value_sum)
            | set(v2_eval_metric_value_count)
        )

        for metric in metric_names:
            label = f'metric="{_escape(metric)}"'

            lines.append(
                "humanize_v2_eval_metric_value_sum"
                f"{{{label}}} "
                f"{v2_eval_metric_value_sum.get(metric, 0.0):.9f}"
            )
            lines.append(
                "humanize_v2_eval_metric_value_count"
                f"{{{label}}} "
                f"{v2_eval_metric_value_count.get(metric, 0)}"
            )

        return "\n".join(lines) + "\n"

    def reset_for_tests(self) -> None:
        with self._lock:
            self._request_counts.clear()
            self._request_duration_sum.clear()
            self._request_duration_count.clear()
            self._rewrite_decisions.clear()
            self._provider_executions.clear()
            self._fallback_outcomes.clear()

            self._v2_routing_decisions.clear()
            self._v2_routing_executions.clear()
            self._v2_routing_attempts.clear()

            self._v2_eval_runs.clear()
            self._v2_eval_cases.clear()
            self._v2_eval_gate_decisions.clear()
            self._v2_eval_metric_value_sum.clear()
            self._v2_eval_metric_value_count.clear()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


metrics_registry = MetricsRegistry()
