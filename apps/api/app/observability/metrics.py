from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from threading import Lock

from app.domain.models import RewriteResponse


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

    def render_prometheus(self) -> str:
        with self._lock:
            request_counts = dict(self._request_counts)
            duration_sums = dict(self._request_duration_sum)
            duration_counts = dict(self._request_duration_count)
            rewrite_decisions = dict(self._rewrite_decisions)
            provider_executions = dict(self._provider_executions)
            fallback_outcomes = dict(self._fallback_outcomes)

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
            lines.append(f'humanize_rewrite_fallback_total{{used="{used}"}} {value}')

        return "\n".join(lines) + "\n"

    def reset_for_tests(self) -> None:
        with self._lock:
            self._request_counts.clear()
            self._request_duration_sum.clear()
            self._request_duration_count.clear()
            self._rewrite_decisions.clear()
            self._provider_executions.clear()
            self._fallback_outcomes.clear()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


metrics_registry = MetricsRegistry()
