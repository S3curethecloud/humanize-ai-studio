from fastapi import APIRouter

from app.core.settings import Settings
from app.domain.models import RewriteRequest, RewriteResponse
from app.providers.registry import build_rewrite_provider
from app.workflows.rewrite_workflow import RewriteWorkflow

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
        "configured_provider": settings.rewrite_provider.value,
        "active_provider": provider.provider_name,
    }


@router.get("/ready")
def ready() -> dict[str, str]:
    return {
        "status": "ready",
        "service": "humanize-ai-studio-api",
        "configured_provider": settings.rewrite_provider.value,
        "active_provider": provider.provider_name,
    }


@router.post("/api/v1/rewrites", response_model=RewriteResponse)
def create_rewrite(request: RewriteRequest) -> RewriteResponse:
    return workflow.execute(request)
