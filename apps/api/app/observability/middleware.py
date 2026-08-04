from __future__ import annotations

import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.types import ASGIApp

from app.observability.context import (
    reset_request_id,
    set_request_id,
)
from app.observability.metrics import metrics_registry

logger = logging.getLogger("humanize.request")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = _resolve_request_id(request.headers.get("X-Request-ID"))
        token = set_request_id(request_id)
        started_at = perf_counter()
        response: Response | None = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "event_fields": {
                        "event": "request_failed",
                        "method": request.method,
                        "path": request.url.path,
                    }
                },
            )
            raise
        finally:
            duration_seconds = perf_counter() - started_at
            route = _resolve_route(request)

            metrics_registry.record_request(
                method=request.method,
                route=route,
                status=status_code,
                duration_seconds=duration_seconds,
            )

            logger.info(
                "request_completed",
                extra={
                    "event_fields": {
                        "event": "request_completed",
                        "method": request.method,
                        "route": route,
                        "status": status_code,
                        "duration_ms": round(
                            duration_seconds * 1000,
                            3,
                        ),
                    }
                },
            )

            reset_request_id(token)


def _resolve_request_id(
    supplied_request_id: str | None,
) -> str:
    if (
        supplied_request_id is not None
        and _REQUEST_ID_PATTERN.fullmatch(supplied_request_id) is not None
    ):
        return supplied_request_id

    return f"request_{uuid4().hex}"


def _resolve_route(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)

    if isinstance(route_path, str):
        return route_path

    return request.url.path
