"""Document ingestion endpoint — upload files to the RAG pipeline with security & metrics."""

from __future__ import annotations

import shutil
import logging
import hashlib
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ingestion import ingest_file
from app.models.schemas import IngestResponse
from app.utils.helpers import sanitize_filename
from app.db.session import get_db
from app.middleware.auth import require_auth
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Ingestion"])

# Allowed extensions
_ALLOWED_EXT = {".pdf", ".txt", ".md", ".docx"}

# Dangerous file signatures (magic bytes)
_DANGEROUS_SIGNATURES = {
    b"MZ": "Windows executable",
    b"\x7fELF": "Linux executable",
    b"#!": "Script file",
    b"PK\x03\x04": None,  # ZIP — allowed for docx, checked by extension
}


def _scan_file_content(content: bytes, ext: str) -> str | None:
    """Basic file content scanning — returns error message if suspicious."""
    for sig, desc in _DANGEROUS_SIGNATURES.items():
        if content[:len(sig)] == sig and desc is not None:
            # Allow ZIP signature for .docx files
            if sig == b"PK\x03\x04" and ext == ".docx":
                continue
            return f"Suspicious file content detected: {desc}"
    return None


@router.post("/ingest", response_model=IngestResponse)
@limiter.limit(settings.RATE_LIMIT_INGEST)
async def ingest_document(
    request: Request,
    file: UploadFile = File(...),
    background: bool = Query(default=False, description="Process in background via Celery"),
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Upload a document and ingest it into Qdrant + Postgres."""

    from app.middleware.metrics import INGESTION_COUNT, CHUNKS_INGESTED

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    safe_name = sanitize_filename(file.filename)
    ext = Path(safe_name).suffix.lower()

    # Validate extension
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(_ALLOWED_EXT)}",
        )

    dest: Path = settings.UPLOAD_DIR / safe_name

    # Validate file size
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max: {settings.MAX_FILE_SIZE_MB} MB",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Scan file content for malicious signatures
    scan_result = _scan_file_content(content, ext)
    if scan_result:
        logger.warning("File upload blocked: %s — %s", safe_name, scan_result)
        raise HTTPException(status_code=400, detail=scan_result)

    # Save uploaded file to disk
    try:
        with open(dest, "wb") as buf:
            buf.write(content)
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")
    finally:
        await file.close()

    # ── Background processing (Celery) ───────────────────────
    if background:
        try:
            from app.core.tasks import ingest_document_task
            task = ingest_document_task.delay(str(dest), safe_name)
            logger.info("Queued background ingestion: %s (task_id=%s)", safe_name, task.id)
            return IngestResponse(
                filename=safe_name,
                chunks=0,
                document_id="",
                message=f"Queued for background processing (task_id={task.id})",
            )
        except Exception as exc:
            logger.warning("Celery unavailable, falling back to sync ingestion: %s", exc)

    # ── Synchronous ingestion ────────────────────────────────
    try:
        num_chunks, doc_id = await ingest_file(dest, db)
    except ValueError as exc:
        logger.warning("Ingestion validation error: %s", exc)
        INGESTION_COUNT.labels(status="error").inc()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Ingestion failed for %s", safe_name)
        INGESTION_COUNT.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=f"Ingestion error: {exc}")

    # Rebuild BM25 index to include new document
    try:
        from app.core.bm25_search import build_bm25_index
        build_bm25_index()
    except Exception:
        logger.warning("BM25 index rebuild failed after ingest — non-fatal")

    # Invalidate query cache since data changed
    try:
        from app.core.cache import invalidate_query_cache
        invalidate_query_cache()
    except Exception:
        pass

    INGESTION_COUNT.labels(status="success").inc()
    CHUNKS_INGESTED.inc(num_chunks)

    return IngestResponse(
        filename=safe_name,
        chunks=num_chunks,
        document_id=doc_id,
    )

