"""RAG Engine — FastAPI Application Entry Point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.api.routes import health, ingest, query, study

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ───────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load heavy resources on startup."""
    logger.info("Loading embedding model …")
    from app.core.embeddings import get_embedding_model
    get_embedding_model()  # warm-up
    logger.info("Embedding model ready.")

    logger.info("Loading vector store …")
    from app.core.vector_store import get_vector_store
    get_vector_store()  # warm-up
    logger.info("Vector store ready.")

    yield  # ← application serves requests between startup and shutdown

    logger.info("Shutting down RAG Engine.")


# ── App factory ─────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Plug & Play Retrieval-Augmented Generation API",
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
app.include_router(study.router)

# ── Static files & SPA fallback ─────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["Root"])
async def root():
    """Serve the chat UI."""
    return FileResponse(str(STATIC_DIR / "index.html"))
