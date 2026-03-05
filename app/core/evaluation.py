"""Retrieval evaluation framework — Precision@K, Recall@K, MRR."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from datetime import datetime, timezone

from app.core.retrieval import retrieve_chunks
from app.config import settings

logger = logging.getLogger(__name__)

EVAL_DIR = settings.BASE_DIR / "evaluation"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# ── Ground truth dataset ─────────────────────────────────────

_GROUND_TRUTH_PATH = EVAL_DIR / "ground_truth.json"


def load_ground_truth() -> list[dict]:
    """
    Load evaluation dataset from JSON.

    Expected format:
    [
        {
            "query": "What is machine learning?",
            "relevant_chunk_ids": ["id1", "id2", "id3"]
        },
        ...
    ]
    """
    if not _GROUND_TRUTH_PATH.exists():
        logger.warning("No ground truth file found at %s", _GROUND_TRUTH_PATH)
        return []
    with open(_GROUND_TRUTH_PATH) as f:
        data = json.load(f)
    logger.info("Loaded %d evaluation queries from ground truth", len(data))
    return data


def save_ground_truth(entries: list[dict]) -> None:
    """Save evaluation dataset to JSON."""
    with open(_GROUND_TRUTH_PATH, "w") as f:
        json.dump(entries, f, indent=2)
    logger.info("Saved %d entries to ground truth", len(entries))


# ── Metrics ──────────────────────────────────────────────────

def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Fraction of retrieved-at-k that are relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant_ids)
    hits = sum(1 for rid in top_k if rid in relevant_set)
    return round(hits / len(top_k), 4)


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Fraction of relevant docs that appear in top-k retrieved."""
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for rid in relevant_ids if rid in top_k)
    return round(hits / len(relevant_ids), 4)


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """Mean Reciprocal Rank — 1/(rank of first relevant result)."""
    relevant_set = set(relevant_ids)
    for i, rid in enumerate(retrieved_ids, 1):
        if rid in relevant_set:
            return round(1.0 / i, 4)
    return 0.0


# ── Evaluation runner ────────────────────────────────────────

def run_evaluation(k: int = 5) -> dict:
    """
    Run retrieval evaluation on all ground truth queries.

    Returns:
        {
            "num_queries": int,
            "avg_precision_at_k": float,
            "avg_recall_at_k": float,
            "avg_mrr": float,
            "per_query": [...],
            "k": int,
            "timestamp": str,
            "config": {...},
        }
    """
    gt = load_ground_truth()
    if not gt:
        return {"error": "No ground truth data. Create evaluation/ground_truth.json first."}

    per_query = []
    total_precision = 0.0
    total_recall = 0.0
    total_mrr = 0.0

    for entry in gt:
        query_text = entry["query"]
        relevant_ids = entry.get("relevant_chunk_ids", [])

        start = time.perf_counter()
        try:
            result = retrieve_chunks(query_text, top_k=k)
            chunks = result["chunks"]
        except Exception as exc:
            logger.error("Eval query failed: %s — %s", query_text[:50], exc)
            per_query.append({
                "query": query_text,
                "error": str(exc),
            })
            continue
        latency = round((time.perf_counter() - start) * 1000, 1)

        retrieved_ids = [c.get("id", "") for c in chunks]

        p = precision_at_k(retrieved_ids, relevant_ids, k)
        r = recall_at_k(retrieved_ids, relevant_ids, k)
        m = mrr(retrieved_ids, relevant_ids)

        total_precision += p
        total_recall += r
        total_mrr += m

        per_query.append({
            "query": query_text,
            "precision_at_k": p,
            "recall_at_k": r,
            "mrr": m,
            "retrieved_ids": retrieved_ids,
            "relevant_ids": relevant_ids,
            "retrieval_latency_ms": latency,
        })

    n = len([q for q in per_query if "error" not in q]) or 1

    results = {
        "num_queries": len(gt),
        "avg_precision_at_k": round(total_precision / n, 4),
        "avg_recall_at_k": round(total_recall / n, 4),
        "avg_mrr": round(total_mrr / n, 4),
        "k": k,
        "per_query": per_query,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "hybrid_weight": settings.HYBRID_WEIGHT,
            "top_k_dense": settings.TOP_K_DENSE,
            "top_k_bm25": settings.TOP_K_BM25,
            "reranker_model": settings.RERANKER_MODEL,
            "reranker_enabled": settings.RERANKER_ENABLED,
            "embedding_model": settings.EMBEDDING_MODEL_NAME,
        },
    }

    # Save results
    out_path = EVAL_DIR / f"eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(
        "Evaluation complete: P@%d=%.4f, R@%d=%.4f, MRR=%.4f — saved to %s",
        k, results["avg_precision_at_k"], k, results["avg_recall_at_k"],
        results["avg_mrr"], out_path,
    )

    return results
