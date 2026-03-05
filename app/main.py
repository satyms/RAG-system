"""RAG Engine — FastAPI Application Entry Point (Phase 3: Production Hardened)."""

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
from app.api.routes import evaluate as evaluate_route
from app.api.routes import auth as auth_route
from app.api.routes import documents as documents_route
from app.api.routes import agent_query as agent_query_route
from app.api.routes import feedback as feedback_route
from app.api.routes import review as review_route
from app.api.routes import adversarial as adversarial_route
from app.api.routes import monitoring as monitoring_route

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

# ── Logging ─────────────────────────────────────────────────
setup_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)


def _background_warmup() -> None:
    """Load embedding model + reranker + BM25 index + Qdrant collection in a thread."""
    try:
        logger.info("Background warm-up: loading embedding model …")
        from app.core.embeddings import get_embedding_model
        get_embedding_model()
        logger.info("Embedding model ready.")
    except Exception as exc:
        logger.warning("Embedding warm-up failed (will retry on first request): %s", exc)

    try:
        logger.info("Background warm-up: loading reranker …")
        from app.core.reranker import get_reranker
        get_reranker()
        logger.info("Reranker ready.")
    except Exception as exc:
        logger.warning("Reranker warm-up failed: %s", exc)

    try:
        logger.info("Background warm-up: connecting to Qdrant …")
        from app.core.vector_store import ensure_collection
        ensure_collection()
        logger.info("Qdrant collection ready.")
    except Exception as exc:
        logger.warning("Qdrant warm-up failed (ensure Qdrant Docker container is running): %s", exc)

    try:
        logger.info("Background warm-up: building BM25 index …")
        from app.core.bm25_search import build_bm25_index
        count = build_bm25_index()
        logger.info("BM25 index ready (%d documents).", count)
    except Exception as exc:
        logger.warning("BM25 index build failed (will retry after first ingest): %s", exc)

    # Warm up Redis connection
    try:
        from app.core.cache import is_redis_available
        if is_redis_available():
            logger.info("Redis cache connected.")
        else:
            logger.warning("Redis unavailable — caching disabled.")
    except Exception as exc:
        logger.warning("Redis warm-up failed: %s", exc)


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

    # 4. Start background evaluation scheduler (runs periodically)
    try:
        from app.core.scheduler import start_scheduler
        import os
        interval = int(os.environ.get("EVAL_INTERVAL_SECONDS", 86400))
        start_scheduler(interval_seconds=interval)
        logger.info("Background evaluation scheduler started (interval=%ds).", interval)
    except Exception as exc:
        logger.warning("Background evaluation scheduler failed to start: %s", exc)

    # 5. Initialize Prometheus metrics
    try:
        from app.middleware.metrics import setup_metrics
        setup_metrics(settings.APP_NAME, settings.APP_VERSION)
    except Exception as exc:
        logger.warning("Prometheus metrics init failed: %s", exc)

    logger.info("RAG Engine started — accepting requests.")
    yield  # ── Application serves requests ───────────────────

    # ── Shutdown ─────────────────────────────────────────────
    try:
        from app.core.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
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

# ── Middleware stack (order matters: outermost first) ────────

# 1. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Request-ID middleware
from app.middleware.request_id import RequestIDMiddleware
app.add_middleware(RequestIDMiddleware)

# 3. Rate limiting
from app.middleware.rate_limit import setup_rate_limiting
setup_rate_limiting(app)

# 4. Prometheus HTTP instrumentation
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health", "/static"],
    ).instrument(app).expose(app, endpoint="/metrics", tags=["Monitoring"])
    logger.info("Prometheus /metrics endpoint enabled")
except Exception as exc:
    logger.warning("Prometheus instrumentator setup failed: %s", exc)

# ── Register routers ────────────────────────────────────────
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(evaluate_route.router)
app.include_router(auth_route.router)
app.include_router(documents_route.router)

# Phase 4 routes
app.include_router(agent_query_route.router)
app.include_router(feedback_route.router)
app.include_router(review_route.router)
app.include_router(adversarial_route.router)
app.include_router(monitoring_route.router)

# ── Static files & SPA fallback ─────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["Root"])
async def root():
    """Serve the chat UI."""
    return FileResponse(str(STATIC_DIR / "index.html"))
