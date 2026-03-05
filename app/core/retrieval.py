"""Hybrid retrieval — dense + BM25 merge → cross-encoder rerank."""

from __future__ import annotations

import logging
import time

from app.config import settings
from app.core.embeddings import embed_text
from app.core.vector_store import search_vectors
from app.core.bm25_search import bm25_search, get_bm25_ready
from app.core.reranker import rerank

logger = logging.getLogger(__name__)


# ── Score normalisation helpers ──────────────────────────────

def _min_max_normalize(values: list[float]) -> list[float]:
    """Normalize a list of floats to [0, 1]. Returns zeros if all equal."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        return [1.0] * len(values)
    return [(v - lo) / span for v in values]


# ── Hybrid merge ─────────────────────────────────────────────

def _merge_results(
    dense_hits: list[dict],
    bm25_hits: list[dict],
    alpha: float,
) -> list[dict]:
    """
    Weighted merge of dense and BM25 results.

    alpha=1 → pure dense, alpha=0 → pure BM25.
    Deduplicates by chunk id, keeping the better combined score.
    """
    # Normalise dense scores
    dense_scores = [h["score"] for h in dense_hits]
    norm_dense = _min_max_normalize(dense_scores)
    for hit, ns in zip(dense_hits, norm_dense):
        hit["dense_score_norm"] = round(ns, 4)

    # Normalise BM25 scores
    bm25_scores = [h["bm25_score"] for h in bm25_hits]
    norm_bm25 = _min_max_normalize(bm25_scores)
    for hit, ns in zip(bm25_hits, norm_bm25):
        hit["bm25_score_norm"] = round(ns, 4)

    # Index by chunk id
    merged: dict[str, dict] = {}

    for hit in dense_hits:
        cid = hit["id"]
        hit["hybrid_score"] = round(alpha * hit.get("dense_score_norm", 0), 4)
        merged[cid] = hit

    for hit in bm25_hits:
        cid = hit["id"]
        bm25_contrib = round((1 - alpha) * hit.get("bm25_score_norm", 0), 4)
        if cid in merged:
            merged[cid]["hybrid_score"] = round(
                merged[cid]["hybrid_score"] + bm25_contrib, 4
            )
            merged[cid]["bm25_score"] = hit.get("bm25_score", 0)
            merged[cid]["bm25_score_norm"] = hit.get("bm25_score_norm", 0)
        else:
            hit["hybrid_score"] = bm25_contrib
            hit.setdefault("score", 0)
            hit.setdefault("dense_score_norm", 0)
            merged[cid] = hit

    results = sorted(merged.values(), key=lambda x: x["hybrid_score"], reverse=True)
    return results


# ── Public API ───────────────────────────────────────────────

def retrieve_chunks(
    query: str,
    top_k: int | None = None,
    source_filter: str | None = None,
) -> dict:
    """
    Full hybrid retrieval pipeline:
      1. Dense (Qdrant) search
      2. BM25 keyword search (if available)
      3. Weighted merge
      4. Cross-encoder rerank
      5. Apply score threshold

    Returns dict with:
        chunks: list[dict]  — final reranked chunks
        metadata: dict      — latency breakdown, pre/post rerank counts, scores
    """
    final_k = top_k or settings.TOP_K
    alpha = settings.HYBRID_WEIGHT

    latency: dict[str, float] = {}

    # ── 1. Dense retrieval ───────────────────────────────────
    t0 = time.perf_counter()
    query_vector = embed_text(query)
    dense_hits = search_vectors(
        query_vector,
        top_k=settings.TOP_K_DENSE,
        source_filter=source_filter,
    )
    latency["dense_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    # ── 2. BM25 retrieval ───────────────────────────────────
    bm25_hits: list[dict] = []
    fallback_reason: str | None = None
    if get_bm25_ready():
        t1 = time.perf_counter()
        try:
            bm25_hits = bm25_search(
                query,
                top_k=settings.TOP_K_BM25,
                source_filter=source_filter,
            )
        except Exception as exc:
            fallback_reason = f"BM25 search error: {exc}"
            logger.warning("BM25 search failed — falling back to dense-only: %s", exc)
            bm25_hits = []
        latency["bm25_ms"] = round((time.perf_counter() - t1) * 1000, 1)
    else:
        latency["bm25_ms"] = 0.0
        fallback_reason = "BM25 index not ready"
        logger.info("BM25 index not ready — using dense-only retrieval")

    # ── 3. Merge ─────────────────────────────────────────────
    if bm25_hits:
        merged = _merge_results(dense_hits, bm25_hits, alpha)
    else:
        # Dense-only fallback — add hybrid_score = dense score
        for h in dense_hits:
            h["hybrid_score"] = h.get("score", 0)
            h["dense_score_norm"] = h.get("score", 0)
            h["bm25_score"] = 0.0
            h["bm25_score_norm"] = 0.0
        merged = dense_hits

    pre_rerank_count = len(merged)

    # ── 4. Rerank ────────────────────────────────────────────
    try:
        reranked, rerank_ms = rerank(query, merged, top_k=final_k)
        latency["rerank_ms"] = rerank_ms
    except Exception as exc:
        if not fallback_reason:
            fallback_reason = f"Reranker failed: {exc}"
        else:
            fallback_reason += f"; Reranker also failed: {exc}"
        logger.warning("Reranker failed, falling back to hybrid order: %s", exc)
        reranked = merged[:final_k]
        latency["rerank_ms"] = 0.0

    # ── 5. Score threshold ───────────────────────────────────
    threshold = settings.SCORE_THRESHOLD
    if threshold > 0:
        reranked = [
            c for c in reranked
            if c.get("hybrid_score", 0) >= threshold
        ]

    latency["total_retrieval_ms"] = round(
        latency["dense_ms"] + latency["bm25_ms"] + latency["rerank_ms"], 1
    )

    if fallback_reason:
        logger.warning("Retrieval fallback active: %s", fallback_reason)

    # Warn if all scores are very low
    if reranked:
        max_hybrid = max(c.get("hybrid_score", 0) for c in reranked)
        if max_hybrid < 0.1:
            logger.warning(
                "All retrieved chunks have very low similarity scores (max=%.4f) for query: %s",
                max_hybrid, query[:80],
            )

    logger.info(
        "Hybrid retrieval: dense=%d, bm25=%d, merged=%d, reranked=%d (%.0fms total)",
        len(dense_hits), len(bm25_hits), pre_rerank_count, len(reranked),
        latency["total_retrieval_ms"],
    )

    return {
        "chunks": reranked,
        "metadata": {
            "dense_count": len(dense_hits),
            "bm25_count": len(bm25_hits),
            "pre_rerank_count": pre_rerank_count,
            "post_rerank_count": len(reranked),
            "dense_scores": [h.get("score", 0) for h in dense_hits[:5]],
            "bm25_scores": [h.get("bm25_score", 0) for h in bm25_hits[:5]],
            "reranker_scores": [c.get("reranker_score") for c in reranked if c.get("reranker_score") is not None],
            "hybrid_scores": [c.get("hybrid_score", 0) for c in reranked],
            "latency": latency,
            "fallback_reason": fallback_reason,
        },
    }


