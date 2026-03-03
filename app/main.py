"""RAG Engine — FastAPI Application Entry Point."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.utils.logging_config import setup_logging
from app.api.routes import health, ingest, query

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

# ── Logging ─────────────────────────────────────────────────
setup_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)


def _background_warmup() -> None:
    """Load embedding model + Qdrant collection in a thread (non-blocking)."""
    try:
        logger.info("Background warm-up: loading embedding model …")
        from app.core.embeddings import get_embedding_model
        get_embedding_model()
        logger.info("Embedding model ready.")
    except Exception as exc:
        logger.warning("Embedding warm-up failed (will retry on first request): %s", exc)

    try:
        logger.info("Background warm-up: connecting to Qdrant …")
        from app.core.vector_store import ensure_collection
        ensure_collection()
        logger.info("Qdrant collection ready.")
    except Exception as exc:
        logger.warning("Qdrant warm-up failed (ensure Qdrant Docker container is running): %s", exc)


# ── Lifespan (startup / shutdown) ───────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bootstrap resources on startup — models load in background so server is immediately ready."""

    # ── Startup ──────────────────────────────────────────────
    # 1. PostgreSQL tables (fast, just DDL)
    try:
        logger.info("Initialising database …")
        from app.db.session import init_db
        await init_db()
        logger.info("Database ready.")
    except Exception as exc:
        logger.warning("DB init failed (ensure Postgres Docker container is running): %s", exc)

    # 2. Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Model + Qdrant warm-up off the main thread so server starts immediately
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _background_warmup)

    logger.info("RAG Engine started — accepting requests.")
    yield  # ── Application serves requests ───────────────────

    # ── Shutdown ─────────────────────────────────────────────
    try:
        from app.db.session import close_db
        await close_db()
    except Exception:
        pass
    logger.info("Shutdown complete.")


# ── App factory ─────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production RAG API powered by Qdrant + Gemini",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ────────────────────────────────────────
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router)

# ── Static files & SPA fallback ─────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["Root"])
async def root():
    """Serve the chat UI."""
    return FileResponse(str(STATIC_DIR / "index.html"))
