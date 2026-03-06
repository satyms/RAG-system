"""Document management — versioning, reindexing, deletion."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.db.models import Document, Chunk
from app.middleware.auth import require_auth
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Documents"])


class DocumentInfo(BaseModel):
    id: str
    filename: str
    status: str
    version: int = 1
    is_latest: bool = True
    upload_timestamp: str = ""
    file_hash: str = ""
    chunk_count: int = 0


class ReindexRequest(BaseModel):
    document_id: str = Field(..., description="UUID of the document to reindex")


class ReindexResponse(BaseModel):
    document_id: str
    filename: str
    new_chunks: int
    message: str


@router.get("/documents")
@limiter.limit("30/minute")
async def list_documents(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
) -> list[DocumentInfo]:
    """List all documents with versioning info."""
    stmt = select(Document).order_by(Document.upload_timestamp.desc())
    result = await db.execute(stmt)
    docs = result.scalars().all()

    out = []
    for doc in docs:
        # Count chunks
        chunk_stmt = select(Chunk).where(Chunk.document_id == doc.id)
        chunk_result = await db.execute(chunk_stmt)
        chunk_count = len(chunk_result.scalars().all())

        out.append(DocumentInfo(
            id=str(doc.id),
            filename=doc.filename,
            status=doc.status,
            version=doc.version or 1,
            is_latest=doc.is_latest if doc.is_latest is not None else True,
            upload_timestamp=doc.upload_timestamp.isoformat() if doc.upload_timestamp else "",
            file_hash=doc.file_hash or "",
            chunk_count=chunk_count,
        ))

    return out


@router.post("/documents/reindex", response_model=ReindexResponse)
@limiter.limit("5/minute")
async def reindex_document(
    request: Request,
    payload: ReindexRequest,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
) -> ReindexResponse:
    """
    Reindex a document — delete old vectors, re-embed, re-store.

    The document file must still exist in the uploads directory.
    """
    from pathlib import Path
    from app.core.vector_store import delete_document_vectors
    from app.core.ingestion import ingest_file

    # Find existing document
    stmt = select(Document).where(Document.id == payload.document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    file_path = settings.UPLOAD_DIR / doc.filename
    if not file_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Source file not found: {doc.filename}. Cannot reindex without source.",
        )

    logger.info("Reindexing document: %s (id=%s)", doc.filename, doc.id)

    # Delete old vectors from Qdrant
    try:
        deleted = delete_document_vectors(doc.filename)
        logger.info("Deleted %d old vectors for %s", deleted, doc.filename)
    except Exception as exc:
        logger.warning("Failed to delete old vectors: %s", exc)

    # Delete old chunks from Postgres
    chunk_stmt = select(Chunk).where(Chunk.document_id == doc.id)
    chunk_result = await db.execute(chunk_stmt)
    for chunk in chunk_result.scalars().all():
        await db.delete(chunk)
    await db.flush()

    # Mark previous version
    doc.is_latest = False
    old_version = doc.version or 1

    # Create new version
    new_doc = Document(
        filename=doc.filename,
        file_hash=doc.file_hash,
        status="processing",
        version=old_version + 1,
        is_latest=True,
        previous_version_id=doc.id,
    )
    db.add(new_doc)
    await db.flush()

    # Re-ingest
    try:
        num_chunks, new_doc_id = await ingest_file(file_path, db)
        new_doc.status = "indexed"
        new_doc.reindexed_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception as exc:
        new_doc.status = "failed"
        await db.commit()
        logger.exception("Reindex failed for %s", doc.filename)
        raise HTTPException(status_code=500, detail=f"Reindex failed: {exc}")

    # Rebuild BM25
    try:
        from app.core.bm25_search import build_bm25_index
        build_bm25_index()
    except Exception:
        pass

    # Invalidate cache
    try:
        from app.core.cache import invalidate_query_cache
        invalidate_query_cache()
    except Exception:
        pass

    return ReindexResponse(
        document_id=str(new_doc.id),
        filename=doc.filename,
        new_chunks=num_chunks,
        message=f"Reindexed to version {old_version + 1}",
    )


@router.delete("/documents/{document_id}")
@limiter.limit("10/minute")
async def delete_document(
    request: Request,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
) -> dict:
    """Delete a document and all its vectors/chunks."""
    from app.core.vector_store import delete_document_vectors

    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete vectors from Qdrant
    try:
        deleted = delete_document_vectors(doc.filename)
        logger.info("Deleted %d vectors for %s", deleted, doc.filename)
    except Exception as exc:
        logger.warning("Vector deletion failed: %s", exc)

    # Delete from Postgres (cascades to chunks)
    await db.delete(doc)
    await db.commit()

    # Rebuild BM25
    try:
        from app.core.bm25_search import build_bm25_index
        build_bm25_index()
    except Exception:
        pass

    # Invalidate cache
    try:
        from app.core.cache import invalidate_query_cache
        invalidate_query_cache()
    except Exception:
        pass

    return {"deleted": True, "document_id": document_id, "filename": doc.filename}
