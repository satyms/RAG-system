"""Query endpoint — hybrid RAG pipeline with full observability logging."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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
    """Hybrid retrieval → rerank → generate → evaluate → log."""

    total_start = time.perf_counter()

    # Allow per-request hybrid weight override
    if payload.hybrid_weight is not None:
        _orig = settings.HYBRID_WEIGHT
        settings.HYBRID_WEIGHT = payload.hybrid_weight

    # ── 1. Hybrid Retrieve + Rerank ──────────────────────────
    try:
        retrieval_result = retrieve_chunks(
            payload.question,
            top_k=payload.top_k,
            source_filter=payload.source_filter,
        )
        chunks = retrieval_result["chunks"]
        ret_meta = retrieval_result["metadata"]
    except Exception as exc:
        logger.exception("Retrieval failed")
        raise HTTPException(status_code=500, detail=f"Retrieval error: {exc}")
    finally:
        # Restore original weight if overridden
        if payload.hybrid_weight is not None:
            settings.HYBRID_WEIGHT = _orig  # noqa: F821

    if not chunks:
        logger.warning("No chunks retrieved for query: %s", payload.question[:80])

    # ── 2. Generate ──────────────────────────────────────────
    try:
        result = generate_answer(payload.question, chunks)
    except RuntimeError as exc:
        logger.error("Generation config error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("LLM generation failed")
        raise HTTPException(status_code=500, detail=f"Generation error: {exc}")

    total_ms = round((time.perf_counter() - total_start) * 1000, 1)

    # ── 3. Confidence score ──────────────────────────────────
    reranker_scores = [c.get("reranker_score") for c in chunks if c.get("reranker_score") is not None]
    dense_scores = [c.get("score", 0) for c in chunks if c.get("score") is not None]

    if reranker_scores:
        confidence = round(sum(reranker_scores) / len(reranker_scores), 4)
    elif dense_scores:
        confidence = round(sum(dense_scores) / len(dense_scores), 4)
    else:
        confidence = None

    # Variance-based confidence penalty
    if reranker_scores and len(reranker_scores) > 1:
        mean = sum(reranker_scores) / len(reranker_scores)
        variance = sum((s - mean) ** 2 for s in reranker_scores) / len(reranker_scores)
        # High variance → less confident
        confidence = round(confidence * (1 - min(variance, 0.5)), 4) if confidence else None

    low_confidence = confidence is not None and confidence < settings.CONFIDENCE_THRESHOLD

    # ── 4. Faithfulness evaluation (async-safe) ──────────────
    faithfulness_score = None
    is_grounded = "unknown"
    try:
        from app.core.faithfulness import evaluate_faithfulness
        faith_result = evaluate_faithfulness(
            question=payload.question,
            answer=result["answer"],
            context_chunks=chunks,
        )
        faithfulness_score = faith_result.get("faithfulness_score")
        is_grounded = faith_result.get("is_grounded", "unknown")
    except Exception:
        logger.debug("Faithfulness evaluation skipped or failed", exc_info=True)

    # ── 5. Log to Postgres ───────────────────────────────────
    latency_breakdown = ret_meta.get("latency", {})
    latency_breakdown["llm_ms"] = result.get("latency_ms", 0)
    latency_breakdown["total_ms"] = total_ms

    try:
        log_entry = QueryLog(
            query_text=payload.question,
            retrieved_chunks=[
                {"id": c.get("id"), "source": c.get("source"), "score": c.get("score")}
                for c in chunks
            ],
            response=result["answer"],
            similarity_scores=dense_scores,
            latency_ms=total_ms,
            token_usage=result.get("token_usage", {}),
            confidence_score=confidence,
            # Phase 2 fields
            dense_scores=ret_meta.get("dense_scores", []),
            bm25_scores=ret_meta.get("bm25_scores", []),
            reranker_scores=ret_meta.get("reranker_scores", []),
            hybrid_scores=ret_meta.get("hybrid_scores", []),
            latency_breakdown=latency_breakdown,
            pre_rerank_count=ret_meta.get("pre_rerank_count"),
            post_rerank_count=ret_meta.get("post_rerank_count"),
            faithfulness_score=faithfulness_score,
            is_grounded=is_grounded,
            low_confidence="true" if low_confidence else "false",
            fallback_reason=ret_meta.get("fallback_reason"),
        )
        db.add(log_entry)
        await db.commit()
    except Exception:
        logger.exception("Failed to log query — non-fatal, continuing")

    if low_confidence:
        logger.warning(
            "Low-confidence query (%.4f < %.2f): %s",
            confidence, settings.CONFIDENCE_THRESHOLD, payload.question[:80],
        )

    # ── 6. Return response ───────────────────────────────────
    return QueryResponse(
        answer=result["answer"],
        sources=[
            SourceChunk(
                content=c["content"],
                source=c.get("source", ""),
                score=c.get("score"),
                chunk_index=c.get("chunk_index"),
                page_number=c.get("page_number"),
                reranker_score=c.get("reranker_score"),
                hybrid_score=c.get("hybrid_score"),
            )
            for c in chunks
        ],
        confidence_score=confidence,
        latency_ms=total_ms,
        token_usage=result.get("token_usage", {}),
        retrieval_metadata={
            "dense_count": ret_meta.get("dense_count", 0),
            "bm25_count": ret_meta.get("bm25_count", 0),
            "pre_rerank_count": ret_meta.get("pre_rerank_count", 0),
            "post_rerank_count": ret_meta.get("post_rerank_count", 0),
            "latency": latency_breakdown,
        },
        faithfulness_score=faithfulness_score,
        is_grounded=is_grounded,
        low_confidence=low_confidence,
    )

