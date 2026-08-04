from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="HumanizeAI Studio API",
    description=(
        "Voice-aware and meaning-preserving text reconstruction platform. "
        "Phase 0 uses a deterministic rewrite provider."
    ),
    version="0.1.0",
)

app.include_router(router)
