"""Phase 4 API routes — agent orchestration query endpoint."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.schemas import QueryRequest, QueryResponse, SourceChunk
from app.db.session import get_db
from app.db.models import QueryLog
from app.middleware.auth import require_auth
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Query V2 (Agents)"])


@router.post("/query", response_model=QueryResponse)
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def agent_query(
    request: Request,
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Multi-agent orchestrated RAG query pipeline."""

    from app.agents.orchestrator import orchestrate
    from app.core.human_review import should_trigger_review, add_to_review_queue
    from app.core.monitoring import record_query_metrics

    try:
        from app.middleware.metrics import (
            QUERY_COUNT, PROMPT_INJECTION_BLOCKED,
        )
    except Exception:
        QUERY_COUNT = PROMPT_INJECTION_BLOCKED = None

    total_start = time.perf_counter()

    # Run the multi-agent pipeline
    result = orchestrate(
        query=payload.question,
        top_k=payload.top_k,
        source_filter=payload.source_filter,
        hybrid_weight=payload.hybrid_weight,
        debug=payload.debug,
    )

    # Handle blocked queries
    if result.get("blocked"):
        if PROMPT_INJECTION_BLOCKED:
            PROMPT_INJECTION_BLOCKED.inc()
        if QUERY_COUNT:
            QUERY_COUNT.labels(status="blocked").inc()
        raise HTTPException(
            status_code=400,
            detail=result.get("block_reason", "Query blocked"),
        )

    total_ms = round((time.perf_counter() - total_start) * 1000, 1)

    # Record monitoring metrics
    record_query_metrics(
        confidence=result.get("confidence_score"),
        faithfulness=result.get("faithfulness_score"),
        latency_ms=total_ms,
        retrieval_count=len(result.get("sources", [])),
    )

    # Human review check
    agent_meta = result.get("agent_metadata", {})
    should_review, review_reason = should_trigger_review(
        query=payload.question,
        answer=result.get("answer", ""),
        confidence=result.get("confidence_score", 0),
        faithfulness_score=result.get("faithfulness_score"),
        is_grounded=result.get("is_grounded", "unknown"),
    )
    if should_review:
        review_id = add_to_review_queue(
            query=payload.question,
            answer=result["answer"],
            context_chunks=result.get("sources", []),
            confidence=result.get("confidence_score", 0),
            trigger_reason=review_reason,
            faithfulness_score=result.get("faithfulness_score"),
            metadata={"agent_metadata": agent_meta},
        )
        agent_meta["review_id"] = review_id
        agent_meta["requires_human_review"] = True
        agent_meta["human_review_reason"] = review_reason

    # Log to Postgres
    if db is not None:
        try:
            log_entry = QueryLog(
                query_text=payload.question,
                retrieved_chunks=[
                    {"source": s.get("source"), "score": s.get("score")}
                    for s in result.get("sources", [])
                ],
                response=result["answer"],
                similarity_scores=[s.get("score", 0) for s in result.get("sources", [])],
                latency_ms=total_ms,
                token_usage=result.get("token_usage", {}),
                confidence_score=result.get("confidence_score"),
                faithfulness_score=result.get("faithfulness_score"),
                is_grounded=result.get("is_grounded"),
                low_confidence="true" if result.get("low_confidence") else "false",
            )
            db.add(log_entry)
            await db.commit()
        except Exception:
            logger.exception("Failed to log query — non-fatal")
    else:
        logger.debug("Database unavailable — skipping query log")

    if QUERY_COUNT:
        status = "low_confidence" if result.get("low_confidence") else "success"
        QUERY_COUNT.labels(status=status).inc()

    # Build response
    return QueryResponse(
        answer=result["answer"],
        sources=[
            SourceChunk(
                content=s.get("content", ""),
                source=s.get("source", ""),
                score=s.get("score"),
                chunk_index=s.get("chunk_index"),
                page_number=s.get("page_number"),
                reranker_score=s.get("reranker_score"),
                hybrid_score=s.get("hybrid_score"),
            )
            for s in result.get("sources", [])
        ],
        confidence_score=result.get("confidence_score"),
        latency_ms=total_ms,
        token_usage=result.get("token_usage", {}),
        retrieval_metadata=result.get("retrieval_metadata", {}),
        faithfulness_score=result.get("faithfulness_score"),
        is_grounded=result.get("is_grounded"),
        low_confidence=result.get("low_confidence", False),
        agent_metadata=agent_meta,
        citations=result.get("citations", []),
        debug=result.get("debug"),
    )
