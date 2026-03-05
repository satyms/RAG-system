"""Celery tasks — background ingestion, evaluation, and maintenance."""

from __future__ import annotations

import logging
import asyncio
from pathlib import Path

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code from synchronous Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Ingestion tasks ──────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.core.tasks.ingest_document",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def ingest_document_task(self, file_path: str, filename: str) -> dict:
    """
    Background task: ingest a single document through the full pipeline.

    Steps: parse → chunk → embed → store in Qdrant + Postgres → rebuild BM25.
    """
    try:
        from app.middleware.metrics import ACTIVE_TASKS, INGESTION_COUNT, CHUNKS_INGESTED
        ACTIVE_TASKS.inc()

        logger.info("Background ingestion started: %s (task_id=%s)", filename, self.request.id)

        async def _ingest():
            from app.db.session import async_session
            from app.core.ingestion import ingest_file

            async with async_session() as db:
                num_chunks, doc_id = await ingest_file(Path(file_path), db)
                return {"chunks": num_chunks, "document_id": doc_id}

        result = _run_async(_ingest())

        # Rebuild BM25 index
        try:
            from app.core.bm25_search import build_bm25_index
            build_bm25_index()
        except Exception:
            logger.warning("BM25 rebuild failed after background ingest")

        # Invalidate query cache since data changed
        try:
            from app.core.cache import invalidate_query_cache
            invalidate_query_cache()
        except Exception:
            pass

        INGESTION_COUNT.labels(status="success").inc()
        CHUNKS_INGESTED.inc(result["chunks"])
        ACTIVE_TASKS.dec()

        logger.info(
            "Background ingestion complete: %s — %d chunks",
            filename, result["chunks"],
        )
        return {
            "status": "success",
            "filename": filename,
            "chunks": result["chunks"],
            "document_id": result["document_id"],
        }

    except Exception as exc:
        from app.middleware.metrics import ACTIVE_TASKS, INGESTION_COUNT
        ACTIVE_TASKS.dec()
        INGESTION_COUNT.labels(status="error").inc()

        logger.exception("Background ingestion failed: %s", filename)

        # Store failed state
        try:
            async def _mark_failed():
                from app.db.session import async_session
                from app.db.models import Document
                from sqlalchemy import select

                async with async_session() as db:
                    stmt = select(Document).where(Document.filename == filename)
                    result = await db.execute(stmt)
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.status = "failed"
                        await db.commit()

            _run_async(_mark_failed())
        except Exception:
            pass

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@celery_app.task(name="app.core.tasks.rebuild_bm25_index")
def rebuild_bm25_index_task() -> dict:
    """Background task: rebuild the BM25 search index."""
    try:
        from app.core.bm25_search import build_bm25_index
        count = build_bm25_index()
        return {"status": "success", "documents_indexed": count}
    except Exception as exc:
        logger.exception("BM25 index rebuild failed")
        return {"status": "error", "detail": str(exc)}


# ── Evaluation tasks ─────────────────────────────────────────

@celery_app.task(name="app.core.tasks.run_periodic_evaluation")
def run_periodic_evaluation() -> dict:
    """Background task: run scheduled evaluation with drift tracking."""
    try:
        from app.core.scheduler import run_scheduled_evaluation
        result = run_scheduled_evaluation(k=5)
        logger.info("Periodic evaluation complete: %s", result)
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.exception("Periodic evaluation failed")
        return {"status": "error", "detail": str(exc)}


# ── Maintenance tasks ────────────────────────────────────────

@celery_app.task(name="app.core.tasks.invalidate_cache")
def invalidate_cache_task() -> dict:
    """Background task: invalidate all cache entries."""
    try:
        from app.core.cache import invalidate_all_cache
        count = invalidate_all_cache()
        return {"status": "success", "invalidated": count}
    except Exception as exc:
        logger.exception("Cache invalidation failed")
        return {"status": "error", "detail": str(exc)}
