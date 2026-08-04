from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.core.settings import Settings
from app.domain.models import (
    RewriteRequest,
    RewriteResponse,
)
from app.observability.context import get_request_id
from app.observability.metrics import metrics_registry
from app.providers.registry import build_rewrite_provider
from app.workflows.rewrite_workflow import RewriteWorkflow

logger = logging.getLogger("humanize.rewrite")

settings = Settings.from_environment()
provider = build_rewrite_provider(settings)
workflow = RewriteWorkflow(provider=provider)

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "humanize-ai-studio-api",
        "mode": settings.rewrite_provider.value,
        "configured_provider": (settings.rewrite_provider.value),
        "active_provider": provider.provider_name,
    }


@router.get("/ready")
def ready() -> dict[str, str]:
    return {
        "status": "ready",
        "service": "humanize-ai-studio-api",
        "configured_provider": (settings.rewrite_provider.value),
        "active_provider": provider.provider_name,
    }


@router.get(
    "/metrics",
    response_class=PlainTextResponse,
)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        content=metrics_registry.render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


@router.post(
    "/api/v1/rewrites",
    response_model=RewriteResponse,
)
def create_rewrite(
    request: RewriteRequest,
) -> RewriteResponse:
    response = workflow.execute(request)

    metrics_registry.record_rewrite(response)

    logger.info(
        "rewrite_completed",
        extra={
            "event_fields": {
                "event": "rewrite_completed",
                "request_id": get_request_id(),
                "trace_id": response.trace_id,
                "decision": (response.rewrite_necessity.decision),
                "provider_required": (response.rewrite_necessity.provider_required),
                "actual_provider": (response.provider_execution.actual_provider_name),
                "fallback_used": (response.provider_execution.fallback_used),
                "provider_latency_ms": (response.provider_execution.latency_ms),
                "total_tokens": (response.provider_execution.usage.total_tokens),
                "verification_decision": (response.verification.decision),
                "editorial_decision": (response.editorial_quality.decision),
            }
        },
    )

    return response
