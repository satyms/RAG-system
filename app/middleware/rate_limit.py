"""Rate limiting — per-endpoint rate limits using slowapi."""

from __future__ import annotations

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

# ── Limiter instance ─────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=settings.REDIS_URL if settings.CACHE_ENABLED else "memory://",
)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded errors."""
    logger.warning(
        "Rate limit exceeded",
        extra={
            "client_ip": request.client.host if request.client else "unknown",
            "path": request.url.path,
            "limit": str(exc.detail),
        },
    )
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


def setup_rate_limiting(app: FastAPI) -> None:
    """Attach rate limiting middleware and exception handler to the app."""
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting enabled (default: %s)", settings.RATE_LIMIT_DEFAULT)
