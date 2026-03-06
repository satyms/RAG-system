"""Health-check endpoint — verifies app, Qdrant, Postgres, Redis, and LLM."""

import logging

from fastapi import APIRouter

from app.config import settings
from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    """Deep health check — tests Qdrant, Postgres, Redis, and LLM connectivity."""

    qdrant_status = "unknown"
    db_status = "unknown"
    redis_status = "unknown"
    llm_status = "unknown"

    # Check Qdrant
    try:
        from app.core.vector_store import get_qdrant_client
        client = get_qdrant_client()
        client.get_collections()
        qdrant_status = "ok"
    except Exception as exc:
        qdrant_status = f"error: {exc}"
        logger.error("Qdrant health check failed: %s", exc)

    # Check Postgres
    try:
        from app.db.session import async_session
        from sqlalchemy import text
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"
        logger.error("Postgres health check failed: %s", exc)

    # Check Redis
    try:
        from app.core.cache import is_redis_available
        if is_redis_available():
            redis_status = "ok"
        else:
            redis_status = "unavailable"
    except Exception as exc:
        redis_status = f"error: {exc}"
        logger.error("Redis health check failed: %s", exc)

    # Check LLM (lightweight — verify Ollama is reachable)
    try:
        import httpx
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.status_code == 200:
            llm_status = f"ok (ollama @ {settings.OLLAMA_BASE_URL}, model={settings.OLLAMA_MODEL})"
        else:
            llm_status = f"error: Ollama returned {resp.status_code}"
    except Exception as exc:
        llm_status = f"error: {exc}"

    overall = "ok"
    if qdrant_status != "ok" or db_status != "ok":
        overall = "degraded"
    if qdrant_status.startswith("error") and db_status.startswith("error"):
        overall = "unhealthy"

    return HealthResponse(
        status=overall,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        qdrant=qdrant_status,
        database=db_status,
        redis=redis_status,
        llm=llm_status,
    )

