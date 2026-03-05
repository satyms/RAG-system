"""Query endpoint — hybrid RAG pipeline with caching, security, metrics, and observability."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.retrieval import retrieve_chunks
from app.core.generation import generate_answer
from app.core.prompt_guard import check_prompt_injection, sanitize_query, filter_context_injections
from app.core.cache import get_cached_query, set_cached_query
from app.models.schemas import QueryRequest, QueryResponse, SourceChunk
from app.db.session import get_db
from app.db.models import QueryLog
from app.middleware.auth import require_auth
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Query"])


@router.post("/query", response_model=QueryResponse)
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def query(
    request: Request,
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
    _auth: dict = Depends(require_auth),
):
    """Hybrid retrieval → rerank → generate → evaluate → log.

    When ``use_agents=True`` the request is delegated to the multi-agent
    orchestrator (Phase 4) and the result is returned directly.
    """

    from app.middleware.metrics import (
        QUERY_COUNT, RETRIEVAL_LATENCY, GENERATION_LATENCY,
        TOKEN_USAGE, CONFIDENCE_SCORE, FAITHFULNESS_SCORE,
        PROMPT_INJECTION_BLOCKED,
    )

    total_start = time.perf_counter()

    # ── Phase 4: optional agent delegation ───────────────────
    if getattr(payload, "use_agents", False):
        from app.api.routes.agent_query import agent_query as _agent_query
        return await _agent_query(request, payload, db, _auth)

    # ── 0. Sanitize & check prompt injection ─────────────────
    clean_question = sanitize_query(payload.question)
    injection_result = check_prompt_injection(clean_question)

    if injection_result.blocked:
        PROMPT_INJECTION_BLOCKED.inc()
        QUERY_COUNT.labels(status="blocked").inc()
        logger.warning(
            "Query blocked — prompt injection detected",
            extra={
                "query_preview": clean_question[:100],
                "risk_score": injection_result.risk_score,
                "patterns": len(injection_result.patterns_matched),
            },
        )
        raise HTTPException(
            status_code=400,
            detail="Your query was blocked because it appears to contain a prompt injection attempt.",
        )

    # ── 0b. Check cache ──────────────────────────────────────
    cached = get_cached_query(clean_question, payload.top_k)
    if cached:
        QUERY_COUNT.labels(status="cache_hit").inc()
        logger.info("Returning cached response for: %s", clean_question[:60])
        return QueryResponse(**cached)

    # Allow per-request hybrid weight override
    if payload.hybrid_weight is not None:
        _orig = settings.HYBRID_WEIGHT
        settings.HYBRID_WEIGHT = payload.hybrid_weight

    # ── 1. Hybrid Retrieve + Rerank ──────────────────────────
    try:
        t_ret = time.perf_counter()
        retrieval_result = retrieve_chunks(
            clean_question,
            top_k=payload.top_k,
            source_filter=payload.source_filter,
        )
        chunks = retrieval_result["chunks"]
        ret_meta = retrieval_result["metadata"]
        RETRIEVAL_LATENCY.observe(time.perf_counter() - t_ret)
    except Exception as exc:
        logger.exception("Retrieval failed")
        QUERY_COUNT.labels(status="error").inc()

        # Fallback: try to return cached answer if available
        try:
            from app.core.cache import get_cached_query
            fallback = get_cached_query(clean_question, payload.top_k)
            if fallback:
                logger.info("Serving stale cache after retrieval failure")
                return QueryResponse(**fallback)
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=f"Retrieval error: {exc}")
    finally:
        # Restore original weight if overridden
        if payload.hybrid_weight is not None:
            settings.HYBRID_WEIGHT = _orig  # noqa: F821

    if not chunks:
        logger.warning("No chunks retrieved for query: %s", clean_question[:80])

    # ── 1b. Filter context injections ────────────────────────
    chunks = filter_context_injections(chunks)

    # ── 2. Generate ──────────────────────────────────────────
    try:
        t_gen = time.perf_counter()
        result = generate_answer(clean_question, chunks)
        GENERATION_LATENCY.observe(time.perf_counter() - t_gen)
    except RuntimeError as exc:
        logger.error("Generation config error: %s", exc)
        QUERY_COUNT.labels(status="error").inc()
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("LLM generation failed")
        QUERY_COUNT.labels(status="error").inc()

        # Fallback: return context-only answer
        if chunks:
            logger.info("LLM fallback: returning raw context")
            fallback_answer = "⚠️ LLM unavailable. Here are the most relevant passages:\n\n"
            for i, c in enumerate(chunks[:3], 1):
                fallback_answer += f"**[{i}]** {c['content'][:300]}...\n\n"
            return QueryResponse(
                answer=fallback_answer,
                sources=[SourceChunk(content=c["content"], source=c.get("source", "")) for c in chunks[:3]],
                low_confidence=True,
            )

        raise HTTPException(status_code=500, detail=f"Generation error: {exc}")

    total_ms = round((time.perf_counter() - total_start) * 1000, 1)

    # Track token usage
    if result.get("token_usage"):
        for k, v in result["token_usage"].items():
            if v:
                TOKEN_USAGE.labels(type=k).inc(v)

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
        confidence = round(confidence * (1 - min(variance, 0.5)), 4) if confidence else None

    low_confidence = confidence is not None and confidence < settings.CONFIDENCE_THRESHOLD

    if confidence is not None:
        CONFIDENCE_SCORE.observe(max(0, min(1, confidence)))

    # ── 4. Faithfulness evaluation (async-safe) ──────────────
    faithfulness_score = None
    is_grounded = "unknown"
    try:
        from app.core.faithfulness import evaluate_faithfulness
        faith_result = evaluate_faithfulness(
            question=clean_question,
            answer=result["answer"],
            context_chunks=chunks,
        )
        faithfulness_score = faith_result.get("faithfulness_score")
        is_grounded = faith_result.get("is_grounded", "unknown")
        if faithfulness_score is not None:
            FAITHFULNESS_SCORE.observe(max(0, min(1, faithfulness_score)))
    except Exception:
        logger.debug("Faithfulness evaluation skipped or failed", exc_info=True)

    # ── 5. Log to Postgres ───────────────────────────────────
    latency_breakdown = ret_meta.get("latency", {})
    latency_breakdown["llm_ms"] = result.get("latency_ms", 0)
    latency_breakdown["total_ms"] = total_ms

    try:
        log_entry = QueryLog(
            query_text=clean_question,
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
        QUERY_COUNT.labels(status="low_confidence").inc()
        logger.warning(
            "Low-confidence query (%.4f < %.2f): %s",
            confidence, settings.CONFIDENCE_THRESHOLD, clean_question[:80],
        )
    else:
        QUERY_COUNT.labels(status="success").inc()

    # ── 6. Build response ────────────────────────────────────
    response_data = QueryResponse(
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

    # ── 7. Cache the response ────────────────────────────────
    try:
        set_cached_query(clean_question, payload.top_k, response_data.model_dump())
    except Exception:
        logger.debug("Failed to cache query response", exc_info=True)

    # ── 8. Phase 4: record monitoring metrics ────────────────
    try:
        from app.core.monitoring import record_query_metrics
        record_query_metrics(
            confidence=confidence,
            faithfulness=faithfulness_score,
            latency_ms=total_ms,
            retrieval_count=len(chunks),
        )
    except Exception:
        logger.debug("Monitoring metrics recording skipped", exc_info=True)

    return response_data

