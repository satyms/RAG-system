"""Cross-encoder reranking service — ms-marco MiniLM."""

from __future__ import annotations

import logging
import time
from functools import lru_cache

import torch
from sentence_transformers import CrossEncoder

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    """Load and cache the cross-encoder model."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Loading reranker: %s (device=%s)", settings.RERANKER_MODEL, device)
    model = CrossEncoder(settings.RERANKER_MODEL, device=device)
    logger.info("Reranker loaded.")
    return model


def rerank(
    query: str,
    chunks: list[dict],
    top_k: int | None = None,
) -> tuple[list[dict], float]:
    """
    Rerank retrieved chunks using a cross-encoder.

    Args:
        query: The user query.
        chunks: List of chunk dicts (must have 'content' key).
        top_k: Number of top results to return after reranking.

    Returns:
        (reranked_chunks, rerank_latency_ms)
        Each chunk gets an added 'reranker_score' field.
    """
    if not chunks:
        return [], 0.0

    k = top_k or settings.RERANKER_TOP_K

    if not settings.RERANKER_ENABLED:
        logger.debug("Reranker disabled — passing through top %d chunks", k)
        return chunks[:k], 0.0

    model = get_reranker()

    # Build (query, passage) pairs
    pairs = [(query, c["content"]) for c in chunks]

    start = time.perf_counter()
    scores = model.predict(pairs, batch_size=32, show_progress_bar=False)
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    # Attach scores
    for chunk, score in zip(chunks, scores):
        chunk["reranker_score"] = round(float(score), 4)

    # Sort by reranker score descending
    reranked = sorted(chunks, key=lambda c: c.get("reranker_score", 0), reverse=True)
    final = reranked[:k]

    logger.info(
        "Reranked %d → %d chunks (%.0fms). Top score=%.4f",
        len(chunks), len(final), latency_ms,
        final[0]["reranker_score"] if final else 0,
    )
    return final, latency_ms
