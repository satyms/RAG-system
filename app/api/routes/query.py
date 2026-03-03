"""Query endpoint — full RAG pipeline with logging to Postgres."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.retrieval import retrieve_chunks
from app.core.generation import generate_answer
from app.models.schemas import QueryRequest, QueryResponse, SourceChunk
from app.db.session import get_db
from app.db.models import QueryLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Query"])


@router.post("/query", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve relevant chunks, generate answer, log everything."""

    total_start = time.perf_counter()

    # ── 1. Retrieve ──────────────────────────────────────────
    try:
        chunks = retrieve_chunks(
            payload.question,
            top_k=payload.top_k,
            source_filter=payload.source_filter,
        )
    except Exception as exc:
        logger.exception("Retrieval failed")
        raise HTTPException(status_code=500, detail=f"Retrieval error: {exc}")

    if not chunks:
        logger.warning("No chunks retrieved for query: %s", payload.question[:80])

    # ── 2. Generate ──────────────────────────────────────────
    try:
        result = generate_answer(payload.question, chunks)
    except RuntimeError as exc:
        # e.g. missing API key
        logger.error("Generation config error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("LLM generation failed")
        raise HTTPException(status_code=500, detail=f"Generation error: {exc}")

    total_ms = round((time.perf_counter() - total_start) * 1000, 1)

    # ── 3. Confidence score (avg similarity) ─────────────────
    scores = [c["score"] for c in chunks if c.get("score") is not None]
    confidence = round(sum(scores) / len(scores), 4) if scores else None

    # ── 4. Log to Postgres ───────────────────────────────────
    try:
        log_entry = QueryLog(
            query_text=payload.question,
            retrieved_chunks=[
                {"id": c.get("id"), "source": c.get("source"), "score": c.get("score")}
                for c in chunks
            ],
            response=result["answer"],
            similarity_scores=scores,
            latency_ms=total_ms,
            token_usage=result.get("token_usage", {}),
            confidence_score=confidence,
        )
        db.add(log_entry)
        await db.commit()
    except Exception:
        logger.exception("Failed to log query — non-fatal, continuing")

    # ── 5. Return response ───────────────────────────────────
    return QueryResponse(
        answer=result["answer"],
        sources=[
            SourceChunk(
                content=c["content"],
                source=c.get("source", ""),
                score=c.get("score"),
                chunk_index=c.get("chunk_index"),
                page_number=c.get("page_number"),
            )
            for c in chunks
        ],
        confidence_score=confidence,
        latency_ms=total_ms,
        token_usage=result.get("token_usage", {}),
    )

