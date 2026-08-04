from fastapi import APIRouter

from app.domain.models import RewriteRequest, RewriteResponse
from app.workflows.rewrite_workflow import RewriteWorkflow

router = APIRouter()
workflow = RewriteWorkflow()


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "humanize-ai-studio-api",
        "mode": "deterministic",
    }


@router.post("/api/v1/rewrites", response_model=RewriteResponse)
def create_rewrite(request: RewriteRequest) -> RewriteResponse:
    return workflow.execute(request)
