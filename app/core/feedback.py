"""Feedback loop — collect ratings, corrections, and expand evaluation dataset."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

FEEDBACK_DIR = settings.BASE_DIR / "evaluation" / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


# ── Feedback types ───────────────────────────────────────────

class FeedbackRating(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class FeedbackEntry:
    """User feedback on a query response."""
    id: str = ""
    query: str = ""
    answer: str = ""
    rating: FeedbackRating = FeedbackRating.NEUTRAL
    correction: str = ""          # User-provided corrected answer
    comment: str = ""
    confidence_score: float = 0.0
    faithfulness_score: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


# ── In-memory store (production: use DB) ─────────────────────

_feedback_store: list[FeedbackEntry] = []


def submit_feedback(
    query: str,
    answer: str,
    rating: str,
    correction: str = "",
    comment: str = "",
    confidence_score: float = 0.0,
    faithfulness_score: float | None = None,
    metadata: dict | None = None,
) -> dict:
    """Submit user feedback for a response."""
    import uuid
    entry = FeedbackEntry(
        id=uuid.uuid4().hex[:16],
        query=query,
        answer=answer,
        rating=FeedbackRating(rating) if rating in [r.value for r in FeedbackRating] else FeedbackRating.NEUTRAL,
        correction=correction,
        comment=comment,
        confidence_score=confidence_score,
        faithfulness_score=faithfulness_score,
        metadata=metadata or {},
    )
    _feedback_store.append(entry)

    # Persist to disk
    _save_feedback_to_disk(entry)

    logger.info("Feedback received: %s (rating=%s)", entry.id, entry.rating.value)
    return _entry_to_dict(entry)


def get_feedback(
    rating: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Get feedback entries, optionally filtered by rating."""
    entries = _feedback_store
    if rating:
        entries = [e for e in entries if e.rating.value == rating]
    entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]
    return [_entry_to_dict(e) for e in entries]


def get_feedback_stats() -> dict:
    """Get feedback statistics."""
    total = len(_feedback_store)
    by_rating = {}
    for r in FeedbackRating:
        by_rating[r.value] = sum(1 for e in _feedback_store if e.rating == r)

    corrections = sum(1 for e in _feedback_store if e.correction)

    return {
        "total": total,
        "by_rating": by_rating,
        "corrections_count": corrections,
        "satisfaction_rate": round(by_rating.get("positive", 0) / max(total, 1), 4),
    }


# ── Dataset expansion ───────────────────────────────────────

def export_corrections_as_eval_data() -> list[dict]:
    """
    Convert user corrections into evaluation dataset entries.

    Returns entries suitable for ground_truth.json expansion.
    """
    corrections = [e for e in _feedback_store if e.correction]
    eval_entries = []
    for corr in corrections:
        eval_entries.append({
            "query": corr.query,
            "expected_answer": corr.correction,
            "original_answer": corr.answer,
            "source": "user_correction",
            "timestamp": corr.timestamp,
        })
    return eval_entries


def expand_ground_truth_from_feedback() -> int:
    """Add user corrections to the ground truth evaluation dataset."""
    from app.core.evaluation import load_ground_truth, save_ground_truth

    gt = load_ground_truth()
    corrections = export_corrections_as_eval_data()

    if not corrections:
        logger.info("No corrections to add to ground truth")
        return 0

    existing_queries = {e.get("query", "").lower() for e in gt}
    added = 0

    for corr in corrections:
        if corr["query"].lower() not in existing_queries:
            gt.append({
                "query": corr["query"],
                "expected_answer": corr["expected_answer"],
                "relevant_chunk_ids": [],  # To be filled manually or via retrieval
                "source": "user_feedback",
            })
            existing_queries.add(corr["query"].lower())
            added += 1

    if added:
        save_ground_truth(gt)
        logger.info("Added %d feedback entries to ground truth", added)

    return added


# ── System tuning suggestions ────────────────────────────────

def suggest_tuning() -> dict:
    """Analyse feedback to suggest system parameter changes."""
    if not _feedback_store:
        return {"suggestion": "No feedback data yet"}

    negative = [e for e in _feedback_store if e.rating == FeedbackRating.NEGATIVE]
    positive = [e for e in _feedback_store if e.rating == FeedbackRating.POSITIVE]
    total = len(_feedback_store)

    suggestions = []

    # High negative rate → suggest adjustments
    neg_rate = len(negative) / max(total, 1)
    if neg_rate > 0.4:
        suggestions.append({
            "parameter": "TOP_K",
            "suggestion": "increase",
            "reason": f"High negative feedback rate ({neg_rate:.0%}). More context may improve answers.",
            "current": settings.TOP_K,
            "recommended": min(settings.TOP_K + 3, 15),
        })

    # Low average confidence in negative feedback
    neg_conf = [e.confidence_score for e in negative if e.confidence_score > 0]
    if neg_conf:
        avg_neg_conf = sum(neg_conf) / len(neg_conf)
        if avg_neg_conf < 0.3:
            suggestions.append({
                "parameter": "HYBRID_WEIGHT",
                "suggestion": "adjust",
                "reason": f"Low avg confidence in negative feedback ({avg_neg_conf:.3f}). Try adjusting hybrid weight.",
                "current": settings.HYBRID_WEIGHT,
                "recommended": round(max(0.5, settings.HYBRID_WEIGHT - 0.1), 2),
            })

    # Low faithfulness in negative feedback
    neg_faith = [e.faithfulness_score for e in negative if e.faithfulness_score is not None]
    if neg_faith:
        avg_faith = sum(neg_faith) / len(neg_faith)
        if avg_faith < 0.5:
            suggestions.append({
                "parameter": "CONFIDENCE_THRESHOLD",
                "suggestion": "increase",
                "reason": f"Low avg faithfulness in negative feedback ({avg_faith:.3f}). Raise threshold to flag more.",
                "current": settings.CONFIDENCE_THRESHOLD,
                "recommended": min(settings.CONFIDENCE_THRESHOLD + 0.1, 0.6),
            })

    if not suggestions:
        suggestions.append({
            "parameter": "none",
            "suggestion": "Current settings appear optimal based on feedback data.",
        })

    return {
        "total_feedback": total,
        "positive_rate": round(len(positive) / max(total, 1), 4),
        "negative_rate": round(neg_rate, 4),
        "suggestions": suggestions,
    }


# ── Helpers ──────────────────────────────────────────────────

def _save_feedback_to_disk(entry: FeedbackEntry) -> None:
    """Append feedback to a JSONL file."""
    path = FEEDBACK_DIR / "feedback.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(_entry_to_dict(entry)) + "\n")


def _entry_to_dict(entry: FeedbackEntry) -> dict:
    return {
        "id": entry.id,
        "query": entry.query,
        "answer": entry.answer,
        "rating": entry.rating.value,
        "correction": entry.correction,
        "comment": entry.comment,
        "confidence_score": entry.confidence_score,
        "faithfulness_score": entry.faithfulness_score,
        "timestamp": entry.timestamp,
        "metadata": entry.metadata,
    }
