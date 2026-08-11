from fastapi import FastAPI

from app.api.routes import router
from app.observability.logging import (
    configure_structured_logging,
)
from app.observability.middleware import (
    RequestObservabilityMiddleware,
)
from app.v2.api.routes import router as v2_router

configure_structured_logging()

app = FastAPI(
    title="HumanizeAI Studio API",
    description=("Voice-aware and meaning-preserving text reconstruction platform."),
    version="0.1.0",
)

app.add_middleware(RequestObservabilityMiddleware)
app.include_router(router)
app.include_router(v2_router)
