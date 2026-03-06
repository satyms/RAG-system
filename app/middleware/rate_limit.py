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


# ── Determine storage backend ────────────────────────────────
def _resolve_storage_uri() -> str:
    """Use Redis when available, otherwise fall back to in-memory storage."""
    if not settings.CACHE_ENABLED:
        return "memory://"
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        logger.info("Rate limiter: using Redis backend")
        return settings.REDIS_URL
    except Exception:
        logger.warning("Rate limiter: Redis unreachable — falling back to in-memory storage")
        return "memory://"


# ── Limiter instance ─────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri=_resolve_storage_uri(),
)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded errors."""
    detail = getattr(exc, "detail", str(exc))
    logger.warning(
        "Rate limit exceeded",
        extra={
            "client_ip": request.client.host if request.client else "unknown",
            "path": request.url.path,
            "limit": detail,
        },
    )
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {detail}"},
    )


def setup_rate_limiting(app: FastAPI) -> None:
    """Attach rate limiting middleware and exception handler to the app."""
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Guard against ConnectionError leaking through slowapi when Redis dies mid-request
    async def _connection_error_handler(request: Request, exc: ConnectionError):
        logger.warning("Rate limiter connection error on %s — allowing request", request.url.path)
        return JSONResponse(status_code=429, content={"detail": "Rate limiter unavailable, try again"})

    app.add_exception_handler(ConnectionError, _connection_error_handler)
    logger.info("Rate limiting enabled (default: %s)", settings.RATE_LIMIT_DEFAULT)
