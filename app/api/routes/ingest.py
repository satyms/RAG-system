"""Document ingestion endpoint — upload files to the RAG pipeline."""

from __future__ import annotations

import shutil
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from app.config import settings
from app.core.ingestion import ingest_file
from app.models.schemas import IngestResponse
from app.utils.helpers import sanitize_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Ingestion"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...)):
    """Upload a document (PDF / TXT / MD) and ingest it into the vector store."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    safe_name = sanitize_filename(file.filename)
    dest: Path = settings.UPLOAD_DIR / safe_name

    # Save uploaded file to disk
    try:
        with open(dest, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
    except Exception as exc:
        logger.exception("Failed to save uploaded file")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await file.close()

    # Ingest into vector store
    try:
        num_chunks = ingest_file(dest)
    except Exception as exc:
        logger.exception("Ingestion failed for %s", safe_name)
        raise HTTPException(status_code=500, detail=f"Ingestion error: {exc}")

    return IngestResponse(filename=safe_name, chunks=num_chunks)
