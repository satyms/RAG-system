"""Health-check endpoint — verifies app, Qdrant, and Postgres."""

import logging

from fastapi import APIRouter

from app.config import settings
from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    """Deep health check — tests Qdrant and Postgres connectivity."""

    qdrant_status = "unknown"
    db_status = "unknown"

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

    overall = "ok" if qdrant_status == "ok" and db_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        qdrant=qdrant_status,
        database=db_status,
    )

