"""Request-ID middleware — attaches a unique ID to every request for tracing."""

from __future__ import annotations

import uuid
import logging
import time
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ── Context variable for request ID ─────────────────────────
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Assigns a unique X-Request-ID to every incoming request.
    Injects it into response headers and a context variable
    so structured logs can reference it.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Honour client-supplied ID or generate one
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(rid)

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            request_id_ctx.reset(token)

        response.headers["X-Request-ID"] = rid

        # Structured access log
        logger.info(
            "request completed",
            extra={
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": elapsed_ms,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )
        return response
