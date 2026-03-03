"""Document ingestion endpoint — upload files to the RAG pipeline."""

from __future__ import annotations

import shutil
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.ingestion import ingest_file
from app.models.schemas import IngestResponse
from app.utils.helpers import sanitize_filename
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Ingestion"])

# Allowed extensions
_ALLOWED_EXT = {".pdf", ".txt", ".md", ".docx"}


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document and ingest it into Qdrant + Postgres."""

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

    # Save uploaded file to disk
    try:
        with open(dest, "wb") as buf:
            buf.write(content)
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")
    finally:
        await file.close()

    # Ingest into Qdrant + Postgres
    try:
        num_chunks, doc_id = await ingest_file(dest, db)
    except ValueError as exc:
        logger.warning("Ingestion validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Ingestion failed for %s", safe_name)
        raise HTTPException(status_code=500, detail=f"Ingestion error: {exc}")

    return IngestResponse(
        filename=safe_name,
        chunks=num_chunks,
        document_id=doc_id,
    )

